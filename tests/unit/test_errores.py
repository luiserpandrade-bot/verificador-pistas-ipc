"""Verifica que las excepciones de dominio no dependen del framework web (R-009).

Si un service lanzara `HTTPException`, la tool MCP recibiría un error HTTP que no sabe
interpretar y el Artículo I.2 quedaría roto. Por eso este módulo no puede importar
FastAPI, y estos tests lo comprueban en vez de confiar en la disciplina de quien edite.
"""

import ast
import inspect as inspeccion

import pytest

from app.services import errores
from app.services.errores import (
    AnchoInsuficienteError,
    CredencialesInvalidasError,
    EmailYaRegistradoError,
    ErrorDeNegocio,
    FueraDeRangoError,
    PistaAjenaError,
    PistaNoEncontradaError,
)

EXCEPCIONES = [
    EmailYaRegistradoError,
    CredencialesInvalidasError,
    AnchoInsuficienteError,
    FueraDeRangoError,
    PistaNoEncontradaError,
    PistaAjenaError,
]


def test_el_modulo_no_importa_nada_del_framework_web() -> None:
    arbol = ast.parse(inspeccion.getsource(errores))
    importados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module)

    assert importados == set(), f"errores.py no debe importar nada: {importados}"


@pytest.mark.parametrize("excepcion", EXCEPCIONES)
def test_toda_excepcion_desciende_de_error_de_negocio(excepcion: type[Exception]) -> None:
    """Permite a un router o a una tool capturar la familia completa si hace falta."""
    assert issubclass(excepcion, ErrorDeNegocio)
    assert issubclass(excepcion, Exception)


@pytest.mark.parametrize("excepcion", EXCEPCIONES)
def test_toda_excepcion_conserva_su_mensaje(excepcion: type[Exception]) -> None:
    mensaje = "motivo concreto del rechazo"

    with pytest.raises(excepcion) as capturada:
        raise excepcion(mensaje)

    assert str(capturada.value) == mensaje


def test_las_seis_excepciones_son_distinguibles() -> None:
    """Cada una mapea a un código distinto, así que no pueden ser la misma clase."""
    assert len({e.__name__ for e in EXCEPCIONES}) == 6


def test_pista_ajena_y_no_encontrada_no_son_la_misma() -> None:
    """Artículo V.1: 403 es "existe pero es de otro"; 404 es "no existe"."""
    assert not issubclass(PistaAjenaError, PistaNoEncontradaError)
    assert not issubclass(PistaNoEncontradaError, PistaAjenaError)


def test_las_cuatro_excepciones_de_pistas_estan_declaradas() -> None:
    """Las que `contracts/rest-api.md` exige para R1, R2, R4 y el 404."""
    for nombre in (
        "AnchoInsuficienteError",
        "FueraDeRangoError",
        "PistaAjenaError",
        "PistaNoEncontradaError",
    ):
        assert hasattr(errores, nombre)
