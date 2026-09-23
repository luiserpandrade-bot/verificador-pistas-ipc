"""Entorno de migraciones de Alembic.

Artículo III.1: las migraciones se gestionan con Alembic, sin SQL crudo concatenado.
Artículo IV.3: la URL de conexión no está escrita en `alembic.ini` (que se versiona);
se toma de la configuración, que a su vez la lee de `.env` o del entorno. Un test puede
sobrescribirla con `set_main_option("sqlalchemy.url", ...)`.

No se usa `fileConfig` a propósito: el logging de la aplicación se configura en
`app/logging_config.py`, que además redacta secretos (Artículo IV.1).
"""

from sqlalchemy import create_engine

from alembic import context
from app.config import obtener_configuracion
from app.database import Base, argumentos_de_conexion

# Los modelos deben importarse para que su metadata quede registrada en `Base`.
from app.models.pista import Pista  # noqa: F401
from app.models.usuario import Usuario  # noqa: F401

config = context.config
target_metadata = Base.metadata


def url_de_conexion() -> str:
    """URL configurada en Alembic si la hay; si no, la de la aplicación."""
    configurada = config.get_main_option("sqlalchemy.url", default=None)
    if configurada:
        return configurada
    return obtener_configuracion().database_url


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base de datos."""
    context.configure(
        url=url_de_conexion(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones contra la base de datos configurada."""
    url = url_de_conexion()
    engine = create_engine(url, connect_args=argumentos_de_conexion(url))

    with engine.connect() as conexion:
        context.configure(
            connection=conexion,
            target_metadata=target_metadata,
            # SQLite no soporta ALTER completo: el modo batch mantiene las migraciones
            # futuras portables entre SQLite y Postgres (Artículo III.2).
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
