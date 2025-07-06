import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, abort
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import pandas as pd
import io
from functools import wraps
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import calendar
import locale

# --- Importación específica para PostgreSQL ---
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import create_engine, func, exc, literal_column

# --- Importaciones de la base de datos ---
from database import db_session, Usuario, Pronostico, ProduccionCaptura, ActivityLog, OutputData, init_db

# --- Configuración de la App Flask ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-segura-para-produccion')

# --- Inicialización de la Base de Datos ---
# Llama a la función init_db una vez, dentro del contexto de la aplicación
with app.app_context():
    init_db()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# --- Constantes y Funciones de Utilidad ---
AREAS_IHP = ['Soporte', 'Cuerpos', 'Misceláneos', 'Embobinado', 'ECC', 'ERF', 'Carga', 'Output']
AREAS_FHP = ['Rotores Inyección', 'Rotores ERF', 'Cuerpos', 'Flechas', 'Embobinado', 'Barniz', 'Soporte', 'Pintura', 'Output']
HORAS_TURNO = { 'Turno A': ['10AM', '1PM', '4PM'], 'Turno B': ['7PM', '10PM', '12AM'], 'Turno C': ['3AM', '6AM'] }
NOMBRES_TURNOS = list(HORAS_TURNO.keys())
DIAS_SEMANA = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def to_slug(text):
    return text.replace(' ', '_').replace('.', '').replace('/', '')

app.jinja_env.filters['slug'] = to_slug

def log_activity(action, details="", area_grupo=None):
    try:
        log_entry = ActivityLog(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            username=session.get('username', 'Sistema'),
            action=action,
            details=details,
            area_grupo=area_grupo
        )
        db_session.add(log_entry)
    except Exception as e:
        db_session.rollback()
        print(f"Error al registrar actividad: {e}")

# --- Decoradores ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') not in allowed_roles:
                flash('No tienes permiso para acceder a esta página.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def csrf_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "POST":
            token = request.form.get("csrf_token") or (request.is_json and request.json.get("csrf_token"))
            if not token or token != session.get("csrf_token"):
                flash("Error de seguridad (CSRF Token inválido). Inténtalo de nuevo.", "danger")
                if request.is_json: return jsonify({'status': 'error', 'message': 'CSRF token missing or incorrect'}), 403
                return redirect(request.url)
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas de Autenticación y Navegación Principal ---
@app.route('/', methods=['GET', 'POST'])
@csrf_required
def login():
    if 'loggedin' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = db_session.query(Usuario).filter(Usuario.username == username).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session['loggedin'] = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['csrf_token'] = secrets.token_hex(16)
            log_activity("Inicio de sesión", f"El usuario '{user.username}' (Rol: {user.role}) ha iniciado sesión.", area_grupo='Sistema')
            db_session.commit()
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    if 'csrf_token' not in session: session['csrf_token'] = secrets.token_hex(16)
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    username = session.get('username', 'Desconocido')
    log_activity("Cierre de sesión", f"El usuario '{username}' ha cerrado la sesión.", area_grupo='Sistema')
    db_session.commit()
    session.clear()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role in ['IHP', 'FHP']: return redirect(url_for('dashboard_group', group=role.lower()))
    if role == 'ADMIN': return redirect(url_for('dashboard_admin'))
    return redirect(url_for('login'))

# --- Funciones de Lógica de Negocio ---
def get_performance_data_from_db(group, date_str):
    areas = [area for area in (AREAS_IHP if group == 'IHP' else AREAS_FHP) if area != 'Output']
    performance_data = {area: {turno: {'pronostico': 0, 'producido': 0} for turno in NOMBRES_TURNOS} for area in areas}
    try:
        pronosticos = db_session.query(Pronostico.area, Pronostico.turno, Pronostico.valor_pronostico).filter(Pronostico.fecha == date_str, Pronostico.grupo == group).all()
        for area, turno, valor in pronosticos:
            if area in performance_data and turno in performance_data[area]:
                performance_data[area][turno]['pronostico'] = valor or 0
        produccion_rows = db_session.query(ProduccionCaptura.area, ProduccionCaptura.hora, ProduccionCaptura.valor_producido).filter(ProduccionCaptura.fecha == date_str, ProduccionCaptura.grupo == group).all()
        for area, hora, valor in produccion_rows:
            for turno, horas in HORAS_TURNO.items():
                if hora in horas:
                    if area in performance_data and turno in performance_data[area]:
                        performance_data[area][turno]['producido'] += valor or 0
                    break
    except exc.SQLAlchemyError as e:
        flash(f"Error al consultar datos de rendimiento: {e}", "danger")
    return performance_data

def get_group_performance(group_name, date_str):
    try:
        total_pronostico = db_session.query(func.sum(Pronostico.valor_pronostico)).filter(Pronostico.fecha == date_str, Pronostico.grupo == group_name).scalar() or 0
        total_producido = db_session.query(func.sum(ProduccionCaptura.valor_producido)).filter(ProduccionCaptura.fecha == date_str, ProduccionCaptura.grupo == group_name).scalar() or 0
        eficiencia = (total_producido / total_pronostico * 100) if total_pronostico > 0 else 0
        return {'pronostico': total_pronostico, 'producido': total_producido, 'eficiencia': round(eficiencia, 2)}
    except exc.SQLAlchemyError as e:
        flash(f"Error al calcular el rendimiento del grupo: {e}", "danger")
        return {'pronostico': 0, 'producido': 0, 'eficiencia': 0}

def get_capture_data(group_name, areas_list, selected_date_str):
    data_to_render = {}
    try:
        for area in areas_list:
            data_to_render[area] = {}
            pronosticos_db = db_session.query(Pronostico).filter_by(fecha=selected_date_str, grupo=group_name, area=area).all()
            pronosticos_data = {p.turno: {'valor': p.valor_pronostico, 'razon': p.razon_desviacion} for p in pronosticos_db}
            produccion_db = db_session.query(ProduccionCaptura).filter_by(fecha=selected_date_str, grupo=group_name, area=area).all()
            produccion_data = {p.hora: p.valor_producido for p in produccion_db}
            total_pronostico_area, total_produccion_area = 0, 0
            for turno, horas in HORAS_TURNO.items():
                turno_slug = to_slug(turno)
                pronostico_info = pronosticos_data.get(turno, {})
                pronostico_valor = pronostico_info.get('valor', '')
                data_to_render[area][f'Pronostico_{turno_slug}'] = pronostico_valor
                total_pronostico_area += int(pronostico_valor or 0)
                produccion_turno, all_hourly_filled = 0, True
                for hora in horas:
                    valor = produccion_data.get(hora, '')
                    data_to_render[area][f'Produccion_{hora}'] = valor
                    if valor == '': all_hourly_filled = False
                    produccion_turno += int(valor or 0)
                data_to_render[area][f'total_produccion_{turno_slug}'] = produccion_turno
                total_produccion_area += produccion_turno
                is_deviation = all_hourly_filled and str(pronostico_valor).isdigit() and len(str(pronostico_valor)) > 0 and produccion_turno < int(pronostico_valor or 0)
                if is_deviation and not pronostico_info.get('razon'):
                    data_to_render[area][f'needs_reason_{turno_slug}'] = True
                if pronostico_info.get('razon'):
                    data_to_render[area][f'razon_desviacion_{turno_slug}'] = True
            data_to_render[area]['total_pronostico_area'] = total_pronostico_area
            data_to_render[area]['total_produccion_area'] = total_produccion_area
    except exc.SQLAlchemyError as e:
        flash(f"Error al obtener datos para captura: {e}", "danger")
    return data_to_render

def get_output_data(group, date_str):
    try:
        output_row = db_session.query(OutputData).filter_by(fecha=date_str, grupo=group).first()
        if output_row: return {'pronostico': output_row.pronostico or '', 'output': output_row.output or ''}
    except exc.SQLAlchemyError as e:
        flash(f"Error al obtener datos de Output: {e}", "danger")
    return {'pronostico': '', 'output': ''}

# --- Rutas de Dashboards ---
@app.route('/dashboard/admin')
@login_required
@role_required(['ADMIN'])
def dashboard_admin():
    today_str = datetime.now().strftime('%Y-%m-%d')
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    ihp_today = get_group_performance('IHP', today_str)
    fhp_today = get_group_performance('FHP', today_str)
    ihp_yesterday = get_group_performance('IHP', yesterday_str)
    fhp_yesterday = get_group_performance('FHP', yesterday_str)
    ihp_today['trend'] = 'up' if ihp_today['producido'] > ihp_yesterday['producido'] else 'down' if ihp_today['producido'] < ihp_yesterday['producido'] else 'stable'
    fhp_today['trend'] = 'up' if fhp_today['producido'] > fhp_yesterday['producido'] else 'down' if fhp_today['producido'] < fhp_yesterday['producido'] else 'stable'
    return render_template('dashboard_admin.html', ihp_data=ihp_today, fhp_data=fhp_today, today=today_str)

@app.route('/dashboard/<group>')
@login_required
def dashboard_group(group):
    group_upper = group.upper()
    if group_upper not in ['IHP', 'FHP']: abort(404)
    if session.get('role') not in [group_upper, 'ADMIN']:
        flash('No tienes permiso para ver este dashboard.', 'danger')
        return redirect(url_for('dashboard'))
    today_str = datetime.now().strftime('%Y-%m-%d')
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    summary_today = get_group_performance(group_upper, today_str)
    summary_yesterday = get_group_performance(group_upper, yesterday_str)
    if summary_today['producido'] > summary_yesterday['producido']: summary_today['trend'] = 'up'
    elif summary_today['producido'] < summary_yesterday['producido']: summary_today['trend'] = 'down'
    else: summary_today['trend'] = 'stable'
    performance_data = get_performance_data_from_db(group_upper, today_str)
    areas_list = [a for a in (AREAS_IHP if group_upper == 'IHP' else AREAS_FHP) if a != 'Output']
    return render_template('dashboard_group.html', production_data=performance_data, summary=summary_today, areas=areas_list, turnos=NOMBRES_TURNOS, today=today_str, group_name=group_upper)


# --- Ruta de Registro ---
@app.route('/registro/<group>')
@login_required
def registro(group):
    group_upper = group.upper()
    if group_upper not in ['IHP', 'FHP']: abort(404)
    if session.get('role') not in [group_upper, 'ADMIN']:
        flash('No tienes permiso para ver este registro.', 'danger')
        return redirect(url_for('dashboard'))
        
    selected_date = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    areas_list = AREAS_IHP if group_upper == 'IHP' else AREAS_FHP
    production_data = get_performance_data_from_db(group_upper, selected_date)
    output_data = get_output_data(group_upper, selected_date)
    
    meta_produccion = 5000 if group_upper == 'FHP' else 879
    
    return render_template('registro_group.html', 
                           selected_date=selected_date, 
                           production_data=production_data, 
                           areas=areas_list, 
                           nombres_turnos=NOMBRES_TURNOS, 
                           output_data=output_data, 
                           group_name=group_upper,
                           meta=meta_produccion)


# --- Lógica de Reportes ---
def get_report_data(group, report_type, year, month=None):
    areas = [area for area in (AREAS_IHP if group == 'IHP' else AREAS_FHP) if area != 'Output']
    
    if report_type == 'yearly':
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        period_label = f"Anual {year}"
    elif report_type == 'monthly':
        start_date = datetime(year, month, 1)
        end_date = start_date.replace(day=calendar.monthrange(year, month)[1])
        month_name = start_date.strftime('%B').capitalize()
        period_label = f"{month_name} {year}"
    else:
        return {}, "Tipo de reporte inválido", [], "stable", 0, 0

    def process_data_for_period(start, end):
        produccion_q = db_session.query(
            ProduccionCaptura.fecha.label('fecha'), 
            ProduccionCaptura.area.label('area'), 
            func.sum(ProduccionCaptura.valor_producido).label('total')
        ).filter(
            ProduccionCaptura.grupo == group,
            ProduccionCaptura.fecha.between(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
        ).group_by(ProduccionCaptura.fecha, ProduccionCaptura.area)

        output_q = db_session.query(
            OutputData.fecha.label('fecha'), 
            literal_column("'Output'").label('area'), 
            func.sum(OutputData.output).label('total')
        ).filter(
            OutputData.grupo == group,
            OutputData.fecha.between(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
        ).group_by(OutputData.fecha)
        
        df = pd.read_sql(produccion_q.union_all(output_q).statement, db_session.bind)
        
        if df.empty: return pd.DataFrame(), 0
        
        df['fecha'] = pd.to_datetime(df['fecha'])
        return df, df['total'].sum()

    df_current, total_current = process_data_for_period(start_date, end_date)

    if df_current.empty:
        pivot = pd.DataFrame(index=areas)
        pivot['Total'] = 0
        return pivot.to_dict('index'), period_label, [], 'stable', 0, 0

    if report_type == 'yearly':
        df_current['month'] = df_current['fecha'].dt.month
        pivot = df_current.pivot_table(index='area', columns='month', values='total', aggfunc='sum').reindex(areas)
        pivot.columns = [calendar.month_name[i].capitalize() for i in pivot.columns]
    
    elif report_type == 'monthly':
        df_current['week_of_month'] = df_current['fecha'].apply(lambda d: (d.day - 1) // 7 + 1)
        pivot = df_current.pivot_table(index='area', columns='week_of_month', values='total', aggfunc='sum').reindex(areas)
        pivot.columns = [f"Semana {i}" for i in pivot.columns]

    pivot = pivot.fillna(0).astype(int)
    pivot['Total'] = pivot.sum(axis=1)
    
    trend = 'stable' if total_current == 0 else 'up'

    return pivot.to_dict('index'), period_label, pivot.columns.tolist(), trend, total_current, 0


# --- Ruta de Reportes ---
@app.route('/reportes')
@login_required
@role_required(['ADMIN', 'IHP', 'FHP'])
def reportes():
    today = datetime.now()
    
    user_role = session.get('role')
    is_admin = user_role == 'ADMIN'
    
    group = request.args.get('group', 'IHP')
    if not is_admin:
        group = user_role

    report_type = request.args.get('type', 'monthly')
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    data, period_label, columns, trend, total_current, total_previous = get_report_data(
        group, report_type, year, month
    )
    
    return render_template('reportes.html',
                           data=data,
                           period_label=period_label,
                           columns=columns,
                           group=group,
                           report_type=report_type,
                           selected_year=year,
                           selected_month=month,
                           trend=trend,
                           total_current=total_current,
                           total_previous=total_previous,
                           is_admin=is_admin)


# --- Ruta de Captura (MODIFICADA PARA POSTGRESQL) ---
@app.route('/captura/<group>', methods=['GET', 'POST'])
@login_required
@csrf_required
def captura(group):
    group_upper = group.upper()
    if group_upper not in ['IHP', 'FHP']: abort(404)
    if session.get('role') not in [group_upper, 'ADMIN']:
        flash('No tienes permiso para capturar datos de este grupo.', 'danger')
        return redirect(url_for('dashboard'))
    
    areas_list = AREAS_IHP if group_upper == 'IHP' else AREAS_FHP
    
    if request.method == 'POST':
        selected_date = request.form.get('fecha')
        if not selected_date:
            flash("No se proporcionó una fecha.", "danger")
            return redirect(url_for('captura', group=group))
        
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        pronosticos_a_guardar, produccion_a_guardar = [], []

        try:
            # Recopilar datos de pronósticos y producción
            for area in [a for a in areas_list if a != 'Output']:
                area_slug = to_slug(area)
                for turno in NOMBRES_TURNOS:
                    new_val = request.form.get(f'pronostico_{area_slug}_{to_slug(turno)}')
                    if new_val and new_val.isdigit():
                        pronosticos_a_guardar.append({'fecha': selected_date, 'grupo': group_upper, 'area': area, 'turno': turno, 'valor_pronostico': int(new_val)})

                for hora in sum(HORAS_TURNO.values(), []):
                    new_val = request.form.get(f'produccion_{area_slug}_{hora}')
                    if new_val and new_val.isdigit():
                        produccion_a_guardar.append({'fecha': selected_date, 'grupo': group_upper, 'area': area, 'hora': hora, 'valor_producido': int(new_val), 'usuario_captura': session.get('username'), 'fecha_captura': now_str})

            # Guardar pronósticos
            if pronosticos_a_guardar:
                stmt = pg_insert(Pronostico).values(pronosticos_a_guardar)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['fecha', 'grupo', 'area', 'turno'],
                    set_=dict(valor_pronostico=stmt.excluded.valor_pronostico)
                )
                db_session.execute(stmt)

            # Guardar producción
            if produccion_a_guardar:
                stmt = pg_insert(ProduccionCaptura).values(produccion_a_guardar)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['fecha', 'grupo', 'area', 'hora'],
                    set_=dict(
                        valor_producido=stmt.excluded.valor_producido,
                        usuario_captura=stmt.excluded.usuario_captura,
                        fecha_captura=stmt.excluded.fecha_captura
                    )
                )
                db_session.execute(stmt)

            # Guardar datos de Output
            new_pronostico_output = request.form.get('pronostico_output')
            new_produccion_output = request.form.get('produccion_output')
            if (new_pronostico_output and new_pronostico_output.isdigit()) or (new_produccion_output and new_produccion_output.isdigit()):
                output_values = {'fecha': selected_date, 'grupo': group_upper, 'pronostico': int(new_pronostico_output or 0), 'output': int(new_produccion_output or 0), 'usuario_captura': session.get('username'), 'fecha_captura': now_str}
                stmt = pg_insert(OutputData).values(output_values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['fecha', 'grupo'],
                    set_=dict(
                        pronostico=stmt.excluded.pronostico,
                        output=stmt.excluded.output,
                        usuario_captura=stmt.excluded.usuario_captura,
                        fecha_captura=stmt.excluded.fecha_captura
                    )
                )
                db_session.execute(stmt)
            
            db_session.commit()
            flash('Cambios guardados exitosamente.', 'success')

        except Exception as e:
            db_session.rollback()
            print(f"ERROR AL GUARDAR EN LA BASE DE DATOS: {e}")
            flash(f"Error al guardar en la base de datos: {e}", 'danger')
            
        return redirect(url_for('captura', group=group, fecha=selected_date))

    # --- Método GET ---
    selected_date = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    data = get_capture_data(group_upper, [a for a in areas_list if a != 'Output'], selected_date)
    output_data = get_output_data(group_upper, selected_date)
    return render_template('captura_group.html', areas=areas_list, horas_turno=HORAS_TURNO, nombres_turnos=NOMBRES_TURNOS, selected_date=selected_date, data=data, output_data=output_data, group_name=group_upper)


@app.route('/submit_reason', methods=['POST'])
@login_required
@csrf_required
def submit_reason():
    try:
        date = request.form.get('date')
        area = request.form.get('area')
        group = request.form.get('group')
        reason = request.form.get('reason')
        turno_name = request.form.get('turno_name')
        username = session.get('username')

        pronostico_entry = db_session.query(Pronostico).filter_by(
            fecha=date,
            grupo=group,
            area=area,
            turno=turno_name
        ).first()

        if pronostico_entry:
            old_reason = pronostico_entry.razon_desviacion
            pronostico_entry.razon_desviacion = reason
            pronostico_entry.usuario_razon = username
            pronostico_entry.fecha_razon = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if old_reason != reason:
                reason_snippet = (reason[:75] + '...') if len(reason) > 75 else reason
                details = f"Fecha: {date}, Área: {area}, Turno: {turno_name}. Se añadió/actualizó la razón a: '{reason_snippet}'"
                log_activity("Registro de Razón", details, area_grupo=group)
            
            db_session.commit()
            return jsonify({'status': 'success', 'message': 'Razón guardada exitosamente.'})
        else:
            return jsonify({'status': 'error', 'message': 'No se encontró el registro de pronóstico para actualizar.'}), 404
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': f'Ocurrió un error inesperado: {e}'}), 500

@app.route('/export_excel/<group>')
@login_required
def export_excel(group):
    group_upper = group.upper()
    if group_upper not in ['IHP', 'FHP']: abort(404)
    if session.get('role') not in [group_upper, 'ADMIN']:
        flash('No tienes permiso para exportar estos datos.', 'danger')
        return redirect(url_for('dashboard'))

    selected_date = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    areas_list = [area for area in (AREAS_IHP if group_upper == 'IHP' else AREAS_FHP) if area != 'Output']
    production_data = get_performance_data_from_db(group_upper, selected_date)
    output_data = get_output_data(group_upper, selected_date)

    records = []
    for area in areas_list:
        area_data = production_data.get(area, {})
        total_pronostico_area = 0; total_producido_area = 0
        record = {'Área': area}
        for turno in NOMBRES_TURNOS:
            turno_data = area_data.get(turno, {}); pronostico = turno_data.get('pronostico', 0); producido = turno_data.get('producido', 0)
            record[f'Pronóstico {turno}'] = pronostico; record[f'Producido {turno}'] = producido
            total_pronostico_area += pronostico; total_producido_area += producido
        record['Pronóstico Total'] = total_pronostico_area; record['Producido Total'] = total_producido_area
        records.append(record)

    if output_data and (output_data.get('pronostico') or output_data.get('output')):
         records.append({'Área': 'Output', 'Pronóstico Total': output_data.get('pronostico', 0), 'Producido Total': output_data.get('output', 0)})

    df = pd.DataFrame(records)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='RegistroProduccion')
        for column in df:
            column_width = max(df[column].astype(str).map(len).max(), len(column)); col_idx = df.columns.get_loc(column)
            writer.sheets['RegistroProduccion'].set_column(col_idx, col_idx, column_width + 2)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f'produccion_{group_upper}_{selected_date}.xlsx')

@app.route('/bandeja')
@login_required
@role_required(['ADMIN'])
def bandeja():
    if request.args.get('limpiar'):
        session.pop('bandeja_filtros', None)
        return redirect(url_for('bandeja'))
    if not request.args: filtros = session.get('bandeja_filtros', {})
    else:
        filtros = {'fecha_inicio': request.args.get('fecha_inicio'), 'fecha_fin': request.args.get('fecha_fin'), 'grupo': request.args.get('grupo'), 'area': request.args.get('area'), 'usuario': request.args.get('usuario')}
        session['bandeja_filtros'] = filtros
    query = db_session.query(Pronostico).filter(Pronostico.razon_desviacion != None, Pronostico.razon_desviacion != '')
    if filtros.get('fecha_inicio'): query = query.filter(Pronostico.fecha >= filtros['fecha_inicio'])
    if filtros.get('fecha_fin'): query = query.filter(Pronostico.fecha <= filtros['fecha_fin'])
    if filtros.get('grupo') and filtros.get('grupo') != 'Todos': query = query.filter(Pronostico.grupo == filtros['grupo'])
    if filtros.get('area'): query = query.filter(Pronostico.area.ilike(f"%{filtros['area']}%"))
    if filtros.get('usuario'): query = query.filter(Pronostico.usuario_razon.ilike(f"%{filtros['usuario']}%"))
    razones = query.order_by(Pronostico.fecha.desc(), Pronostico.grupo).all()
    return render_template('bandeja.html', razones=razones, filtros=filtros)

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
@role_required(['ADMIN'])
@csrf_required
def manage_users():
    if request.method == 'POST':
        username, password, role = request.form.get('username'), request.form.get('password'), request.form.get('role')
        if not username or not password or not role: flash('Todos los campos son obligatorios.', 'warning')
        else:
            if db_session.query(Usuario).filter_by(username=username).first():
                flash(f"El nombre de usuario '{username}' ya existe.", 'danger')
            else:
                new_user = Usuario(username=username, password_hash=generate_password_hash(password), role=role)
                db_session.add(new_user)
                log_activity("Creación de usuario", f"Admin '{session.get('username')}' creó el usuario '{username}' con el rol '{role}'.", area_grupo='ADMIN')
                db_session.commit()
                flash(f"Usuario '{username}' creado exitosamente.", 'success')
        return redirect(url_for('manage_users'))
    users = db_session.query(Usuario).all()
    return render_template('manage_users.html', users=users)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@role_required(['ADMIN'])
@csrf_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash('No puedes eliminar tu propia cuenta de administrador.', 'danger')
        return redirect(url_for('manage_users'))
    user_to_delete = db_session.query(Usuario).filter_by(id=user_id).first()
    if user_to_delete:
        username_to_delete = user_to_delete.username
        db_session.delete(user_to_delete)
        log_activity("Eliminación de usuario", f"Admin '{session.get('username')}' eliminó al usuario '{username_to_delete}'.", area_grupo='ADMIN')
        db_session.commit()
        flash('Usuario eliminado exitosamente.', 'success')
    else: flash('El usuario no existe.', 'danger')
    return redirect(url_for('manage_users'))

@app.route('/activity_log')
@login_required
@role_required(['ADMIN'])
def activity_log():
    if request.args.get('limpiar'):
        session.pop('activity_log_filtros', None)
        return redirect(url_for('activity_log'))
    if not request.args: filtros = session.get('activity_log_filtros', {})
    else:
        filtros = {'fecha_inicio': request.args.get('fecha_inicio'), 'fecha_fin': request.args.get('fecha_fin'), 'usuario': request.args.get('usuario'), 'area_grupo': request.args.get('area_grupo')}
        session['activity_log_filtros'] = filtros
    try:
        query = db_session.query(ActivityLog)
        if filtros.get('fecha_inicio'):
            start_date = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
            query = query.filter(ActivityLog.timestamp >= start_date)
        if filtros.get('fecha_fin'):
            end_date = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')
            query = query.filter(ActivityLog.timestamp <= end_date)
        if filtros.get('usuario'): query = query.filter(ActivityLog.username.ilike(f"%{filtros['usuario']}%"))
        if filtros.get('area_grupo') and filtros.get('area_grupo') != 'Todos':
            query = query.filter(ActivityLog.area_grupo == filtros['area_grupo'])
        logs = query.order_by(ActivityLog.timestamp.desc()).limit(500).all()
    except exc.SQLAlchemyError as e:
        logs = []; flash(f"No se pudo cargar el log de actividad: {e}", "danger")
    return render_template('activity_log.html', logs=logs, filtros=filtros)
