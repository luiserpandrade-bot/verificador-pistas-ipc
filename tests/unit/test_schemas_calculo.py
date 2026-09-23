"""Tests de los schemas de la consulta de ancho mínimo (US2).

Se repite aquí la misma disciplina de capas que en `PistaCreate`: los rangos de R2 no se
validan en el schema, porque el caso de error 2 exige 400 y no 422.
"""

import pytest
from pydantic import ValidationError

from app.schemas.pista import CalculoIn, CalculoOut
from app.utils.ipc2221 import Capa

DATOS_VALIDOS = {
    "corriente_a": 1.0,
    "espesor_oz": 1.0,
    "capa": "externa",
    "delta_t_c": 10.0,
}


def _con(**cambios: object) -> dict[str, object]:
    datos = dict(DATOS_VALIDOS)
    datos.update(cambios)
    return datos


def test_acepta_una_entrada_valida() -> None:
    entrada = CalculoIn(**DATOS_VALIDOS)  # type: ignore[arg-type]

    assert entrada.capa is Capa.EXTERNA
    assert entrada.corriente_a == 1.0


def test_no_pide_el_ancho_disenado() -> None:
    """Es justo lo que la consulta devuelve, no algo que el cliente aporte."""
    assert "ancho_mm" not in CalculoIn.model_fields


@pytest.mark.parametrize("campo", list(DATOS_VALIDOS))
def test_todos_los_campos_son_obligatorios(campo: str) -> None:
    datos = dict(DATOS_VALIDOS)
    del datos[campo]

    with pytest.raises(ValidationError):
        CalculoIn(**datos)  # type: ignore[arg-type]


@pytest.mark.parametrize("capa", ["superficial", "EXTERNA", "", "media"])
def test_capa_invalida_es_error_de_schema(capa: str) -> None:
    """R3 + caso de error 3: 422."""
    with pytest.raises(ValidationError):
        CalculoIn(**_con(capa=capa))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("corriente_a", 36.0),
        ("delta_t_c", 5.0),
        ("delta_t_c", 150.0),
        ("espesor_oz", 4.0),
        ("espesor_oz", 0.4),
    ],
)
def test_el_schema_no_aplica_los_rangos_de_r2(campo: str, valor: float) -> None:
    """Corrección B1: estos valores deben llegar al service y producir 400, no 422."""
    entrada = CalculoIn(**_con(**{campo: valor}))  # type: ignore[arg-type]

    assert getattr(entrada, campo) == valor


@pytest.mark.parametrize("campo", ["corriente_a", "espesor_oz", "delta_t_c"])
def test_valores_no_positivos_se_rechazan(campo: str) -> None:
    with pytest.raises(ValidationError):
        CalculoIn(**_con(**{campo: 0}))  # type: ignore[arg-type]


def test_calculo_out_solo_lleva_el_ancho_minimo() -> None:
    """No se devuelven campos de pista: la consulta no crea nada (FR-014)."""
    assert set(CalculoOut.model_fields) == {"ancho_minimo_mm"}

    salida = CalculoOut(ancho_minimo_mm=0.300)
    assert salida.model_dump() == {"ancho_minimo_mm": 0.300}


def test_el_schema_usa_el_enum_de_utils() -> None:
    """Artículo VIII.3: un único Enum de capa en todo el proyecto."""
    assert CalculoIn.model_fields["capa"].annotation is Capa
