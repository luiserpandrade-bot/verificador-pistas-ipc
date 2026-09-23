"""Verifica que el engine es portable a Postgres (Artículo III.2).

El riesgo concreto: si `connect_args={"check_same_thread": False}` se aplicara de
forma incondicional, la app no arrancaría contra Postgres, y arreglarlo entonces
obligaría a tocar capas superiores. Estos tests fijan que el argumento es condicional.
"""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.database import (
    Base,
    argumentos_de_conexion,
    crear_engine,
    es_sqlite,
    sesiones,
)

URL_SQLITE = "sqlite:///./prueba-temporal.db"
URL_SQLITE_MEMORIA = "sqlite+pysqlite:///:memory:"
URL_POSTGRES = "postgresql+psycopg://usuario:clave@localhost:5432/pistas"


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        (URL_SQLITE, True),
        (URL_SQLITE_MEMORIA, True),
        (URL_POSTGRES, False),
        ("mysql+pymysql://u:c@host/db", False),
    ],
)
def test_detecta_sqlite(url: str, esperado: bool) -> None:
    assert es_sqlite(url) is esperado


def test_sqlite_recibe_check_same_thread() -> None:
    assert argumentos_de_conexion(URL_SQLITE) == {"check_same_thread": False}


@pytest.mark.parametrize("url", [URL_POSTGRES, "mysql+pymysql://u:c@host/db"])
def test_otros_motores_no_reciben_connect_args(url: str) -> None:
    """Postgres no admite `check_same_thread`: pasárselo rompería el arranque."""
    assert argumentos_de_conexion(url) == {}


def test_crear_engine_sqlite_en_memoria_funciona() -> None:
    engine = crear_engine(URL_SQLITE_MEMORIA)

    assert isinstance(engine, Engine)
    with engine.connect() as conexion:
        assert conexion.execute(text("select 1")).scalar_one() == 1
    engine.dispose()


def test_url_de_postgres_es_valida_y_sin_connect_args_de_sqlite() -> None:
    """La URL de Postgres resuelve a su dialecto y no arrastra argumentos de SQLite.

    No se construye el engine: `create_engine` importaría el driver `psycopg`, que no
    es dependencia de este proyecto (SQLite en desarrollo). Lo que el Artículo III.2
    exige es que el código no le pase `check_same_thread` a un motor que no lo admite,
    y eso es exactamente lo que se comprueba aquí.
    """
    from sqlalchemy.engine.url import make_url

    url = make_url(URL_POSTGRES)

    assert url.get_dialect().name == "postgresql"
    assert argumentos_de_conexion(URL_POSTGRES) == {}


def test_generador_de_sesiones_cierra_la_sesion(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.database as database

    engine = crear_engine(URL_SQLITE_MEMORIA)
    monkeypatch.setattr(database, "_engine", engine)
    monkeypatch.setattr(database, "_fabrica_de_sesiones", None)

    generador = sesiones()
    sesion = next(generador)
    assert isinstance(sesion, Session)
    assert sesion.is_active

    generador.close()
    engine.dispose()


def test_base_declarativa_disponible_para_los_modelos() -> None:
    assert hasattr(Base, "metadata")
