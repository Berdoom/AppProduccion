import os
from sqlalchemy import create_engine, Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base
from werkzeug.security import generate_password_hash

# --- CONFIGURACIÓN DE BASE DE DATOS ---
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///produccion.db')

try:
    if DATABASE_URL.startswith('postgres'):
        engine = create_engine(DATABASE_URL)
    else:
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
        
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    print("Conexión a la base de datos establecida exitosamente.")

except Exception as e:
    print(f"Error al conectar con la base de datos: {e}")
    exit(1)

# --- DEFINICIÓN DE LAS TABLAS (MODELOS) ---
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

# --- INICIALIZACIÓN AUTOMÁTICA DE LA BASE DE DATOS ---
# Este código se ejecuta una vez cuando la aplicación arranca.
def init_db():
    try:
        print("Inicializando esquema de la base de datos...")
        # create_all no sobreescribe tablas existentes, es seguro ejecutarlo siempre.
        Base.metadata.create_all(bind=engine)
        print("Esquema inicializado.")

        # Añade los usuarios iniciales si no existen
        db = SessionLocal()
        print("Verificando usuarios iniciales...")
        initial_users = [
            ('ihp_user', 'ihp_pass', 'IHP'),
            ('fhp_user', 'fhp_pass', 'FHP'),
            ('GCL1909', '1909', 'ADMIN')
        ]

        for username, password, role in initial_users:
            user_exists = db.query(Usuario).filter(Usuario.username == username).first()
            if not user_exists:
                password_hash = generate_password_hash(password)
                new_user = Usuario(username=username, password_hash=password_hash, role=role)
                db.add(new_user)
                print(f"Usuario '{username}' creado.")
        
        db.commit()
        print("Verificación de usuarios completada.")
        db.close()
    except Exception as e:
        print(f"Ocurrió un error durante la inicialización de la base de datos: {e}")

# Llamamos a la función de inicialización aquí para que se ejecute al iniciar la app
init_db()
