"""Verifica que el árbol de capas exigido por el Artículo I de la constitución existe.

Las siete carpetas de capa no son una preferencia de estilo: el Artículo I reparte
responsabilidades entre ellas, así que su ausencia rompería el diseño antes de
escribir una sola regla de negocio.
"""

import importlib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

CAPAS = [
    "app.routers",
    "app.services",
    "app.repositories",
    "app.models",
    "app.schemas",
    "app.utils",
    "app.mcp.tools",
]

DIRECTORIOS = [
    "app",
    "app/routers",
    "app/services",
    "app/repositories",
    "app/models",
    "app/schemas",
    "app/utils",
    "app/mcp",
    "app/mcp/tools",
    "alembic/versions",
    "tests/unit",
    "tests/integration",
    "tests/api",
    "tests/mcp",
]


@pytest.mark.parametrize("directorio", DIRECTORIOS)
def test_directorio_existe(directorio: str) -> None:
    assert (RAIZ / directorio).is_dir(), f"falta el directorio {directorio}"


@pytest.mark.parametrize("modulo", CAPAS)
def test_capa_es_importable(modulo: str) -> None:
    assert importlib.import_module(modulo) is not None
