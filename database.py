import os
from sqlalchemy import create_engine, Column, Integer, String, Text, UniqueConstraint, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from werkzeug.security import generate_password_hash

# --- CONFIGURACIÓN DE LA BASE DE DATOS SQLITE ---
# SQLite no necesita usuario, contraseña, host o puerto. Solo un nombre de archivo.
DB_NAME = "produccion.db"
DATABASE_URL = f"sqlite:///{DB_NAME}"

# --- ANTERIOR CONFIGURACIÓN MYSQL (Comentada por si se necesita en el futuro) ---
# DB_USER = os.environ.get("DB_USER", "GCL1909")
# DB_PASSWORD = os.environ.get("DB_PASSWORD", "n1D3c$#pro")
# DB_HOST = os.environ.get("DB_HOST", "localhost")
# DB_PORT = os.environ.get("DB_PORT", "3306")
# DB_NAME_MYSQL = os.environ.get("DB_NAME", "produccion")
# DATABASE_URL_MYSQL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME_MYSQL}"

# --- CONFIGURACIÓN DEL MOTOR DE SQLALCHEMY ---
try:
    # El argumento 'connect_args' es CRUCIAL para que SQLite funcione bien con Flask.
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    print(f"Error al conectar con la base de datos SQLite: {e}")
    exit(1)


# --- DEFINICIÓN DE LAS TABLAS (MODELOS) ---
# No es necesario cambiar los modelos. SQLAlchemy se encarga de traducirlos.

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


def reset_database():
    """
    Borra todas las tablas y las vuelve a crear.
    """
    try:
        print("--- INICIANDO REINICIO DE BASE DE DATOS SQLITE ---")
        print("Borrando todas las tablas existentes...")
        Base.metadata.drop_all(bind=engine)
        print("Tablas borradas exitosamente.")
        
        print("Creando nuevas tablas desde cero...")
        Base.metadata.create_all(bind=engine)
        print("Nuevas tablas creadas exitosamente.")
        print(f"Base de datos '{DB_NAME}' creada/reiniciada.")
        print("--- REINICIO COMPLETADO ---")
    except Exception as e:
        print(f"Ocurrió un error durante el reinicio de la base de datos: {e}")


def init_db():
    """
    Reinicia la base de datos y añade los usuarios iniciales.
    """
    # --- PASO 1: Reiniciar la base de datos (borrar y crear tablas) ---
    reset_database()

    # --- PASO 2: Añadir usuarios iniciales ---
    db = SessionLocal()
    try:
        print("\nCreando usuarios iniciales...")
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
        print("¡Usuarios iniciales creados correctamente!")

    except Exception as e:
        print(f"Ocurrió un error durante la creación de usuarios: {e}")
        db.rollback()
    finally:
        db.close()
        print("\n¡Proceso de inicialización finalizado!")


if __name__ == '__main__':
    # Esta sección se ejecuta solo cuando corres el script directamente
    init_db()