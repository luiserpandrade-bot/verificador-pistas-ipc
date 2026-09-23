"""Fixtures compartidas por toda la suite.

Artículo VII.4: los tests de integración corren contra una base de datos real (SQLite
en memoria), nunca contra el repositorio falso.
Artículo VII.5: los tests de API sustituyen `get_db`, `get_pistas_repo`,
`get_usuarios_repo` y `get_current_user` con `app.dependency_overrides`, sin levantar
un servidor real ni tocar la base de datos de desarrollo.
Artículo VII.2: los tests unitarios de `services/` usan los repositorios falsos de
`tests/fakes.py`, inyectados por parámetro; `unittest.mock` está prohibido para eso.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, argumentos_de_conexion
from tests.fakes import RepositorioPistasFalso, RepositorioUsuariosFalso

URL_EN_MEMORIA = "sqlite+pysqlite:///:memory:"

CLAVE_DE_PRUEBA = "clave-de-prueba-solo-para-tests"


@pytest.fixture(autouse=True)
def entorno_de_pruebas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuración mínima para toda la suite.

    La aplicación exige `SECRET_KEY` y `DATABASE_URL` y falla al arrancar si faltan
    (Artículo IV.3). En los tests no hay `.env` —ni debe haberlo—, así que se inyectan
    por entorno valores de prueba y se limpia la caché de configuración.
    """
    from app.config import obtener_configuracion

    monkeypatch.setenv("SECRET_KEY", CLAVE_DE_PRUEBA)
    monkeypatch.setenv("DATABASE_URL", URL_EN_MEMORIA)
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    obtener_configuracion.cache_clear()
    yield
    obtener_configuracion.cache_clear()


@pytest.fixture
def engine_en_memoria() -> Iterator[Engine]:
    """Engine SQLite en memoria con las tablas creadas y claves ajenas activas.

    Se usa `StaticPool` para que todas las conexiones compartan la misma base: SQLite en
    memoria crea una base nueva por conexión, y `TestClient` atiende las peticiones en
    otro hilo, así que sin esto la app vería un esquema vacío. Los `connect_args` siguen
    saliendo de `app.database`, de modo que la lógica condicional del Artículo III.2 se
    ejercita igual.
    """
    engine = create_engine(
        URL_EN_MEMORIA,
        connect_args=argumentos_de_conexion(URL_EN_MEMORIA),
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _activar_claves_ajenas(conexion, _registro) -> None:  # noqa: ANN001
        # SQLite ignora las claves ajenas salvo que se activen en cada conexión.
        conexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sesion(engine_en_memoria: Engine) -> Iterator[Session]:
    """Sesión real contra SQLite en memoria, para tests de integración."""
    fabrica = sessionmaker(bind=engine_en_memoria, autoflush=False, future=True)
    with fabrica() as sesion:
        yield sesion


@pytest.fixture
def repo_usuarios_falso() -> RepositorioUsuariosFalso:
    """Repositorio de usuarios en memoria, para tests unitarios de services."""
    return RepositorioUsuariosFalso()


@pytest.fixture
def repo_pistas_falso() -> RepositorioPistasFalso:
    """Repositorio de pistas en memoria, para tests unitarios de services."""
    return RepositorioPistasFalso()


@pytest.fixture
def cliente_api(sesion: Session):
    """Cliente de API con las dependencias sustituidas (Artículo VII.5).

    Los imports son diferidos a propósito: la app y sus dependencias se construyen en
    T016–T018, y esta fixture solo se usa desde los tests de API (T017 en adelante).
    Así `conftest.py` no obliga a que exista la capa de routers para poder correr los
    tests de capas inferiores.
    """
    from fastapi.testclient import TestClient

    from app.dependencies import get_db
    from app.main import crear_app

    aplicacion = crear_app()
    aplicacion.dependency_overrides[get_db] = lambda: sesion

    with TestClient(aplicacion) as cliente:
        yield cliente

    aplicacion.dependency_overrides.clear()
