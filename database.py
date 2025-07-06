import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from werkzeug.security import generate_password_hash

# --- CONFIGURACIÓN DE BASE DE DATOS ---
# Lee la variable de entorno 'DATABASE_URL'. Si no existe, usa una base de datos SQLite local.
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///produccion.db')

try:
    # Configuración del motor de la base de datos
    if DATABASE_URL.startswith('postgres'):
        engine = create_engine(DATABASE_URL)
    else:
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
        
    # Crea una fábrica de sesiones y una sesión segura para cada solicitud web
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = scoped_session(session_factory)

    # Base para los modelos declarativos
    Base = declarative_base()
    Base.query = db_session.query_property()
    print("Conexión a la base de datos configurada exitosamente.")

except Exception as e:
    print(f"FATAL: Error al configurar la conexión a la base de datos: {e}")
    exit(1)

# --- DEFINICIÓN DE LAS TABLAS (MODELOS) ---
# (Las clases de las tablas no cambian, se omiten por brevedad pero deben estar aquí)
from sqlalchemy import Column, Integer, String, Text, UniqueConstraint

class Pronostico(Base):
    __tablename__ = 'pronosticos'
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String(10), nullable=False)
    grupo = Column(String(10), nullable=False)
    area = Column(String(50), nullable=False)
    turno = Column(String(20), nullable=False)
    valor_pronostico = Column(Integer)
    razon_desviacion = Column(Text)
    usuario_razon = Column(String(50))
    fecha_razon = Column(String(30))
    __table_args__ = (UniqueConstraint('fecha', 'grupo', 'area', 'turno', name='_fecha_grupo_area_turno_uc'),)

class ProduccionCaptura(Base):
    __tablename__ = 'produccion_capturas'
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String(10), nullable=False)
    grupo = Column(String(10), nullable=False)
    area = Column(String(50), nullable=False)
    hora = Column(String(10), nullable=False)
    valor_producido = Column(Integer)
    usuario_captura = Column(String(50))
    fecha_captura = Column(String(30))
    __table_args__ = (UniqueConstraint('fecha', 'grupo', 'area', 'hora', name='_fecha_grupo_area_hora_uc'),)

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)

class ActivityLog(Base):
    __tablename__ = 'activity_log'
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String(30), nullable=False)
    username = Column(String(80))
    action = Column(String(255), nullable=False)
    area_grupo = Column(String(50), nullable=True)
    details = Column(Text)

class OutputData(Base):
    __tablename__ = 'output_data'
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String(10), nullable=False)
    grupo = Column(String(10), nullable=False)
    pronostico = Column(Integer)
    output = Column(Integer)
    usuario_captura = Column(String(50))
    fecha_captura = Column(String(30))
    __table_args__ = (UniqueConstraint('fecha', 'grupo', name='_fecha_grupo_uc'),)

# --- FUNCIÓN DE INICIALIZACIÓN ---
def init_db():
    try:
        print("Inicializando esquema de la base de datos...")
        Base.metadata.create_all(bind=engine) # Crea tablas si no existen
        db = db_session()
        print("Verificando usuarios iniciales...")
        initial_users = [
            ('ihp_user', 'ihp_pass', 'IHP'),
            ('fhp_user', 'fhp_pass', 'FHP'),
            ('GCL1909', '1909', 'ADMIN')
        ]
        for username, password, role in initial_users:
            if not db.query(Usuario).filter(Usuario.username == username).first():
                db.add(Usuario(username=username, password_hash=generate_password_hash(password), role=role))
                print(f"Usuario '{username}' creado.")
        db.commit()
        print("Base de datos lista.")
    except Exception as e:
        print(f"ERROR durante la inicialización de la base de datos: {e}")
        db.rollback()
    finally:
        db_session.remove()
