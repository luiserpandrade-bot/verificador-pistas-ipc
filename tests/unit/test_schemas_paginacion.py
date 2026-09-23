"""Tests de `PistaUpdate` y `PaginacionParams` (US3)."""

import pytest
from pydantic import ValidationError

from app.schemas.pista import PaginacionParams, PistaUpdate
from app.utils.ipc2221 import Capa

# --- PaginacionParams (Artículo V.2, decisión R-005) --------------------------------


def test_los_valores_por_defecto_son_0_y_20() -> None:
    params = PaginacionParams()

    assert params.skip == 0
    assert params.limit == 20


@pytest.mark.parametrize(("skip", "limit"), [(0, 1), (0, 100), (500, 50)])
def test_acepta_valores_validos(skip: int, limit: int) -> None:
    params = PaginacionParams(skip=skip, limit=limit)

    assert (params.skip, params.limit) == (skip, limit)


@pytest.mark.parametrize("skip", [-1, -100])
def test_skip_negativo_es_error_de_schema(skip: int) -> None:
    """Artículo V.2: valores inválidos son 422, no 400."""
    with pytest.raises(ValidationError):
        PaginacionParams(skip=skip)


@pytest.mark.parametrize("limit", [0, -1, 101, 1000])
def test_limit_fuera_de_1_a_100_es_error_de_schema(limit: int) -> None:
    with pytest.raises(ValidationError):
        PaginacionParams(limit=limit)


def test_limit_no_numerico_es_error_de_schema() -> None:
    with pytest.raises(ValidationError):
        PaginacionParams(limit="veinte")  # type: ignore[arg-type]


# --- PistaUpdate --------------------------------------------------------------------


def test_update_vacio_es_valido_y_no_declara_cambios() -> None:
    actualizacion = PistaUpdate()

    assert actualizacion.cambios() == {}


def test_solo_declara_los_campos_enviados() -> None:
    """Un PATCH no debe tocar lo que no se envió."""
    actualizacion = PistaUpdate(ancho_mm=0.9)

    assert actualizacion.cambios() == {"ancho_mm": 0.9}


def test_la_capa_se_declara_como_texto_de_la_norma() -> None:
    actualizacion = PistaUpdate(capa=Capa.INTERNA)

    assert actualizacion.cambios() == {"capa": "interna"}


def test_acepta_varios_campos_a_la_vez() -> None:
    actualizacion = PistaUpdate(corriente_a=5.0, ancho_mm=2.0)

    assert actualizacion.cambios() == {"corriente_a": 5.0, "ancho_mm": 2.0}


@pytest.mark.parametrize("capa", ["superficial", "EXTERNA", ""])
def test_capa_invalida_es_error_de_schema(capa: str) -> None:
    with pytest.raises(ValidationError):
        PistaUpdate(capa=capa)  # type: ignore[arg-type]


@pytest.mark.parametrize("campo", ["corriente_a", "espesor_oz", "delta_t_c", "ancho_mm"])
def test_valores_no_positivos_son_error_de_schema(campo: str) -> None:
    with pytest.raises(ValidationError):
        PistaUpdate(**{campo: 0})  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        PistaUpdate(**{campo: -1})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("corriente_a", 36.0), ("delta_t_c", 150.0), ("espesor_oz", 4.0)],
)
def test_el_update_no_aplica_los_rangos_de_r2(campo: str, valor: float) -> None:
    """Corrección B1 también en PATCH: R5 revalida R2 en el service y devuelve 400."""
    actualizacion = PistaUpdate(**{campo: valor})  # type: ignore[arg-type]

    assert actualizacion.cambios() == {campo: valor}


def test_no_se_puede_cambiar_el_propietario() -> None:
    """Artículo IV.4: `usuario_id` no es un campo aceptado, ni siquiera por error."""
    assert "usuario_id" not in PistaUpdate.model_fields

    with pytest.raises(ValidationError):
        PistaUpdate(usuario_id=99)  # type: ignore[call-arg]


def test_no_se_pueden_enviar_campos_desconocidos() -> None:
    with pytest.raises(ValidationError):
        PistaUpdate(inventado="x")  # type: ignore[call-arg]
