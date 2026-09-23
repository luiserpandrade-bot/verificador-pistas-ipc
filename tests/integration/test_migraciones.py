"""Verifica que las migraciones de Alembic suben y bajan (Artículos III.1 y VII.4).

Se ejecutan contra un SQLite real en disco temporal, no contra un doble: una migración
que solo funciona en teoría no sirve de nada.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from app.database import crear_engine

RAIZ = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def configuracion_alembic(tmp_path: Path) -> tuple[Config, str]:
    url = f"sqlite:///{(tmp_path / 'migraciones.db').as_posix()}"
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.set_main_option("script_location", str(RAIZ / "alembic"))
    configuracion.set_main_option("sqlalchemy.url", url)
    return configuracion, url


def _tablas(url: str) -> set[str]:
    engine = crear_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_head_crea_las_dos_tablas(
    configuracion_alembic: tuple[Config, str],
) -> None:
    configuracion, url = configuracion_alembic

    command.upgrade(configuracion, "head")

    tablas = _tablas(url)
    assert {"usuarios", "pistas"} <= tablas
    assert "alembic_version" in tablas


def test_el_esquema_migrado_coincide_con_los_modelos(
    configuracion_alembic: tuple[Config, str],
) -> None:
    configuracion, url = configuracion_alembic
    command.upgrade(configuracion, "head")

    engine = crear_engine(url)
    try:
        inspector = inspect(engine)
        columnas_pistas = {c["name"] for c in inspector.get_columns("pistas")}
        ajenas = inspector.get_foreign_keys("pistas")
        indices = inspector.get_indexes("pistas")
    finally:
        engine.dispose()

    assert columnas_pistas == {
        "id",
        "usuario_id",
        "nombre_red",
        "proyecto",
        "corriente_a",
        "espesor_oz",
        "capa",
        "delta_t_c",
        "ancho_mm",
    }
    assert ajenas[0]["referred_table"] == "usuarios"
    assert any(i["column_names"] == ["usuario_id"] for i in indices)


def test_email_migrado_tiene_indice_unico(
    configuracion_alembic: tuple[Config, str],
) -> None:
    configuracion, url = configuracion_alembic
    command.upgrade(configuracion, "head")

    engine = crear_engine(url)
    try:
        indices = inspect(engine).get_indexes("usuarios")
    finally:
        engine.dispose()

    indice_email = next(i for i in indices if i["column_names"] == ["email"])
    assert bool(indice_email["unique"]) is True


def test_downgrade_base_deja_el_esquema_vacio(
    configuracion_alembic: tuple[Config, str],
) -> None:
    configuracion, url = configuracion_alembic
    command.upgrade(configuracion, "head")

    command.downgrade(configuracion, "base")

    tablas = _tablas(url)
    assert "usuarios" not in tablas
    assert "pistas" not in tablas


def test_ciclo_completo_es_repetible(
    configuracion_alembic: tuple[Config, str],
) -> None:
    configuracion, url = configuracion_alembic

    command.upgrade(configuracion, "head")
    command.downgrade(configuracion, "base")
    command.upgrade(configuracion, "head")

    assert {"usuarios", "pistas"} <= _tablas(url)
