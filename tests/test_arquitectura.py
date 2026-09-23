"""Test de arquitectura: verifica el reparto de capas del Artículo I por sus imports.

La constitución no reparte responsabilidades como recomendación de estilo: si un service
importa SQLAlchemy o una tool de MCP reimplementa una regla, el diseño está roto aunque
todos los demás tests pasen. Esta comprobación es automática para que la regla no dependa
de la disciplina de quien edite el código después.

Se inspecciona el AST de cada módulo y no el texto: mencionar un nombre en un docstring no
es usarlo.
"""

import ast
from pathlib import Path

import pytest

RAIZ_APP = Path(__file__).resolve().parent.parent / "app"


def _modulos_de(subcarpeta: str) -> list[Path]:
    carpeta = RAIZ_APP / subcarpeta
    return [
        archivo
        for archivo in sorted(carpeta.rglob("*.py"))
        if archivo.name != "__init__.py"
    ]


def _arbol(archivo: Path) -> ast.Module:
    return ast.parse(archivo.read_text(encoding="utf-8"))


def _importados(archivo: Path) -> set[str]:
    importados: set[str] = set()
    for nodo in ast.walk(_arbol(archivo)):
        if isinstance(nodo, ast.Import):
            importados.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module)
    return importados


def _identificadores(archivo: Path) -> set[str]:
    arbol = _arbol(archivo)
    return {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)
    }


def _empieza_por(nombres: set[str], prefijo: str) -> bool:
    return any(nombre == prefijo or nombre.startswith(prefijo + ".") for nombre in nombres)


# --- Artículo I.2: los services no conocen la persistencia --------------------------


@pytest.mark.parametrize("modulo", _modulos_de("services"), ids=lambda p: p.name)
def test_los_services_no_importan_sqlalchemy_ni_session(modulo: Path) -> None:
    importados = _importados(modulo)

    assert not _empieza_por(importados, "sqlalchemy"), f"{modulo.name} importa SQLAlchemy"
    assert not _empieza_por(importados, "app.database"), f"{modulo.name} importa app.database"
    assert not _empieza_por(importados, "app.models"), f"{modulo.name} importa app.models"


@pytest.mark.parametrize("modulo", _modulos_de("services"), ids=lambda p: p.name)
def test_los_services_no_importan_el_framework_web(modulo: Path) -> None:
    """Un service debe servir igual a un router y a una tool MCP (decisión R-009)."""
    importados = _importados(modulo)

    assert not _empieza_por(importados, "fastapi"), f"{modulo.name} importa FastAPI"
    assert not _empieza_por(importados, "starlette"), f"{modulo.name} importa Starlette"
    assert not _empieza_por(importados, "fastmcp"), f"{modulo.name} importa FastMCP"


# --- Artículo I.3: solo los repositorios tocan la base de datos ---------------------


def test_solo_los_repositorios_y_database_usan_session() -> None:
    culpables = [
        archivo.relative_to(RAIZ_APP).as_posix()
        for archivo in sorted(RAIZ_APP.rglob("*.py"))
        if _empieza_por(_importados(archivo), "sqlalchemy")
        and archivo.parent.name not in {"repositories", "models"}
        and archivo.name not in {"database.py", "dependencies.py"}
    ]

    assert culpables == [], f"capas que no deberían conocer SQLAlchemy: {culpables}"


# --- Artículo I.1: los routers no contienen reglas de negocio -----------------------


@pytest.mark.parametrize("modulo", _modulos_de("routers"), ids=lambda p: p.name)
def test_los_routers_no_calculan_ni_deciden(modulo: Path) -> None:
    identificadores = _identificadores(modulo)
    importados = _importados(modulo)

    for prohibido in ("ancho_minimo_mm", "TOLERANCIA_MM", "K_POR_CAPA", "redondear_mm"):
        assert prohibido not in identificadores, f"{modulo.name} usa {prohibido}"
    assert not _empieza_por(importados, "app.utils.ipc2221"), (
        f"{modulo.name} no debe conocer el cálculo: eso es del service"
    )


@pytest.mark.parametrize("modulo", _modulos_de("routers"), ids=lambda p: p.name)
def test_los_routers_no_hablan_con_los_modelos_ni_con_la_sesion(modulo: Path) -> None:
    importados = _importados(modulo)

    assert not _empieza_por(importados, "sqlalchemy")
    assert not _empieza_por(importados, "app.models")


# --- Artículos I.5 y VI.1: las tools MCP no reimplementan services -----------------


@pytest.mark.parametrize("modulo", _modulos_de("mcp"), ids=lambda p: p.name)
def test_las_tools_mcp_no_reimplementan_el_calculo(modulo: Path) -> None:
    identificadores = _identificadores(modulo)
    importados = _importados(modulo)

    for prohibido in ("ancho_minimo_mm", "TOLERANCIA_MM", "K_POR_CAPA", "redondear_mm"):
        assert prohibido not in identificadores, f"{modulo.name} usa {prohibido}"
    assert not _empieza_por(importados, "app.utils.ipc2221")
    assert not _empieza_por(importados, "sqlalchemy")


def test_las_tools_mcp_delegan_en_los_services() -> None:
    """Artículo VI.1: si una tool no llama a un service, está duplicando lógica."""
    herramientas = RAIZ_APP / "mcp" / "tools" / "pistas.py"
    importados = _importados(herramientas)

    assert _empieza_por(importados, "app.services")


# --- Artículos I.4 y VIII.3: utils es puro y única sede de las constantes ----------


@pytest.mark.parametrize("modulo", _modulos_de("utils"), ids=lambda p: p.name)
def test_utils_no_depende_de_ninguna_otra_capa(modulo: Path) -> None:
    importados = _importados(modulo)

    for prohibido in ("app.services", "app.routers", "app.repositories", "app.models"):
        assert not _empieza_por(importados, prohibido), f"{modulo.name} importa {prohibido}"
    assert not _empieza_por(importados, "sqlalchemy")
    assert not _empieza_por(importados, "fastapi")


def test_las_constantes_de_la_norma_viven_en_un_solo_modulo() -> None:
    """Artículo VIII.3: `k`, exponentes y factores no se repiten en ningún otro sitio."""
    constantes = ("0.048", "0.024", "1.378", "0.0254", "0.725", "0.44")
    sede = RAIZ_APP / "utils" / "ipc2221.py"

    culpables: dict[str, list[str]] = {}
    for archivo in sorted(RAIZ_APP.rglob("*.py")):
        if archivo == sede:
            continue
        numeros = {
            str(nodo.value)
            for nodo in ast.walk(_arbol(archivo))
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, float)
        }
        repetidas = sorted(numeros & set(constantes))
        if repetidas:
            culpables[archivo.relative_to(RAIZ_APP).as_posix()] = repetidas

    assert culpables == {}, f"constantes de la norma duplicadas: {culpables}"


# --- Estructura general -------------------------------------------------------------


def test_existen_las_siete_capas_del_articulo_i() -> None:
    for capa in (
        "routers",
        "services",
        "repositories",
        "models",
        "schemas",
        "utils",
        "mcp/tools",
    ):
        assert (RAIZ_APP / capa).is_dir(), f"falta la capa {capa}"


def test_no_hay_dependencias_circulares_entre_capas() -> None:
    """Un repositorio no puede importar un service, ni utils un schema."""
    prohibiciones = {
        "repositories": ("app.services", "app.routers", "app.mcp"),
        "utils": ("app.services", "app.routers", "app.repositories", "app.schemas"),
        "models": ("app.services", "app.routers", "app.repositories"),
        "schemas": ("app.services", "app.routers", "app.repositories", "app.models"),
    }

    infracciones: list[str] = []
    for capa, prohibidos in prohibiciones.items():
        for archivo in _modulos_de(capa):
            for prohibido in prohibidos:
                if _empieza_por(_importados(archivo), prohibido):
                    infracciones.append(f"{capa}/{archivo.name} -> {prohibido}")

    assert infracciones == [], f"dependencias invertidas: {infracciones}"
