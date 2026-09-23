"""Auditoría de cobertura de *reglas*, no de líneas (Artículo VII.3).

El Artículo VII.3 exige que el 100 % de las reglas de negocio explícitas de `spec.md` esté
cubierto por al menos un test unitario cada una. Un porcentaje de líneas no demuestra eso:
se puede tener 95 % de líneas y haber perdido el test de R5 en un refactor. Este módulo
recorre los nombres de los tests de la suite y falla si una regla o un caso de error se
queda sin test propio.

El mapeo legible para humanos está en `tests/README.md`; aquí está el que se comprueba.
"""

import ast
from pathlib import Path

import pytest

RAIZ_TESTS = Path(__file__).resolve().parent
REGLAS = ("r1", "r2", "r3", "r4", "r5")
CASOS_DE_ERROR = tuple(range(1, 8))


def _nombres_de_test() -> list[str]:
    """Nombres de todas las funciones de test de la suite, sin ejecutarlas."""
    nombres: list[str] = []
    for archivo in sorted(RAIZ_TESTS.rglob("test_*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.FunctionDef) and nodo.name.startswith("test_"):
                nombres.append(nodo.name)
    return nombres


@pytest.fixture(scope="module")
def nombres() -> list[str]:
    return _nombres_de_test()


@pytest.mark.parametrize("regla", REGLAS)
def test_cada_regla_tiene_al_menos_un_test_propio(regla: str, nombres: list[str]) -> None:
    """R1 a R5, identificables por nombre (`test_r1_*`, ...)."""
    propios = [n for n in nombres if n.startswith(f"test_{regla}_")]

    assert propios, f"la regla {regla.upper()} no tiene ningún test propio"


@pytest.mark.parametrize("numero", CASOS_DE_ERROR)
def test_cada_caso_de_error_de_la_spec_esta_cubierto(numero: int, nombres: list[str]) -> None:
    """Los 7 casos de error explícitos de `spec.md`."""
    cubiertos = [n for n in nombres if f"caso_de_error_{numero}" in n]

    assert cubiertos, f"el caso de error {numero} de la spec no tiene test"


def test_las_reglas_se_prueban_con_repositorio_falso_y_sin_mock() -> None:
    """Artículo VII.2: los tests unitarios de services inyectan el falso por parámetro."""
    archivo = RAIZ_TESTS / "unit" / "test_services_pistas.py"
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))

    importados = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }

    assert "tests.fakes" in importados
    assert not any(nombre.startswith("unittest") for nombre in importados)


def test_ninguna_prueba_de_la_suite_usa_unittest_mock() -> None:
    """Artículo VII.2, extendido a toda la suite."""
    culpables: list[str] = []
    for archivo in sorted(RAIZ_TESTS.rglob("test_*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import) and any(
                alias.name.startswith("unittest") for alias in nodo.names
            ):
                culpables.append(archivo.name)
            if isinstance(nodo, ast.ImportFrom) and (nodo.module or "").startswith("unittest"):
                culpables.append(archivo.name)

    assert culpables == [], f"usan unittest.mock: {sorted(set(culpables))}"


def test_el_readme_documenta_el_mapeo_de_las_cinco_reglas() -> None:
    """Si se añade una regla, su fila en el mapeo no puede faltar."""
    readme = (RAIZ_TESTS / "README.md").read_text(encoding="utf-8")

    for regla in REGLAS:
        assert f"**{regla.upper()}" in readme, f"{regla.upper()} no está en tests/README.md"
    for numero in CASOS_DE_ERROR:
        assert f"| {numero} |" in readme, f"el caso de error {numero} no está en el mapeo"


def test_hay_tests_en_los_cuatro_niveles_de_la_piramide() -> None:
    """Artículo VII.1: unitarias, integración, API y MCP."""
    for nivel in ("unit", "integration", "api", "mcp"):
        archivos = list((RAIZ_TESTS / nivel).glob("test_*.py"))
        assert archivos, f"no hay tests en el nivel {nivel}"
