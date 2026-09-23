"""Verifica el contrato del Artículo IV.3: `.env.example` versionado y `.env` ignorado.

`.env.example` documenta todas las variables necesarias sin valores reales; `.env`
no se versiona nunca. Un fallo aquí significa que un secreto puede acabar en el
historial de git, así que se comprueba de forma automática y no por inspección.
"""

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / ".env.example"

VARIABLES = ["SECRET_KEY", "DATABASE_URL", "ACCESS_TOKEN_EXPIRE_MINUTES"]


def _lineas_de_asignacion() -> dict[str, str]:
    asignaciones: dict[str, str] = {}
    for linea in EJEMPLO.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, valor = limpia.split("=", 1)
        asignaciones[clave.strip()] = valor.strip()
    return asignaciones


def test_env_example_existe() -> None:
    assert EJEMPLO.is_file(), "falta .env.example y el Artículo IV.3 lo exige versionado"


@pytest.mark.parametrize("variable", VARIABLES)
def test_documenta_la_variable(variable: str) -> None:
    assert variable in _lineas_de_asignacion(), f"{variable} no está documentada"


def test_secretos_sin_valores_reales() -> None:
    asignaciones = _lineas_de_asignacion()
    assert asignaciones["SECRET_KEY"] == "", "SECRET_KEY no debe traer un valor real"
    assert asignaciones["DATABASE_URL"] == "", "DATABASE_URL no debe traer un valor real"


def test_env_esta_ignorado_por_git() -> None:
    resultado = subprocess.run(
        ["git", "check-ignore", ".env"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, ".env no está en .gitignore"


def test_env_real_no_esta_versionado() -> None:
    resultado = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode != 0, ".env está versionado y no debería estarlo"
