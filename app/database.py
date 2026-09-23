"""Engine y sesiones de SQLAlchemy.

Artículo III.1: SQLAlchemy como ORM y Alembic para migraciones; ninguna sentencia SQL
cruda concatenada con strings.
Artículo III.2: SQLite en desarrollo, pero este módulo debe funcionar contra Postgres
sin tocar `services/` ni `routers/`. Por eso `connect_args` solo se aplica cuando la
URL es SQLite: es el único detalle específico del motor y queda encapsulado aquí.

Ninguna otra capa crea engines ni sesiones: los repositorios reciben la `Session`
(Artículo I.3) y los services no conocen nada de esto (Artículo I.2).
"""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import obtener_configuracion


class Base(DeclarativeBase):
    """Base declarativa común a todos los modelos."""


def es_sqlite(url: str) -> bool:
    """Indica si la URL de conexión corresponde a SQLite."""
    return url.startswith("sqlite")


def argumentos_de_conexion(url: str) -> dict[str, Any]:
    """Devuelve los `connect_args` que necesita el motor de esa URL.

    SQLite necesita `check_same_thread=False` porque la app usa la conexión desde
    varios hilos del servidor ASGI. Postgres no admite ese argumento, así que fuera
    de SQLite el diccionario va vacío.
    """
    if es_sqlite(url):
        return {"check_same_thread": False}
    return {}


def crear_engine(url: str | None = None) -> Engine:
    """Crea el engine para `url` (por defecto, la `DATABASE_URL` de configuración)."""
    url_efectiva = url or obtener_configuracion().database_url
    return create_engine(url_efectiva, connect_args=argumentos_de_conexion(url_efectiva))


_engine: Engine | None = None
_fabrica_de_sesiones: sessionmaker[Session] | None = None


def obtener_engine() -> Engine:
    """Devuelve el engine de la aplicación, creándolo la primera vez."""
    global _engine
    if _engine is None:
        _engine = crear_engine()
    return _engine


def obtener_fabrica_de_sesiones() -> sessionmaker[Session]:
    """Devuelve la factoría de sesiones de la aplicación."""
    global _fabrica_de_sesiones
    if _fabrica_de_sesiones is None:
        _fabrica_de_sesiones = sessionmaker(bind=obtener_engine(), autoflush=False, future=True)
    return _fabrica_de_sesiones


def sesiones() -> Iterator[Session]:
    """Generador de sesiones: abre una, la cede y la cierra siempre."""
    sesion = obtener_fabrica_de_sesiones()()
    try:
        yield sesion
    finally:
        sesion.close()
