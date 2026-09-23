"""Tests unitarios de `calcular_ancho_minimo` (US2, FR-014).

Lo esencial que se fija aquí: la consulta no persiste nada, aplica R2 y devuelve el
mínimo redondeado a 3 decimales.
"""

import inspect as inspeccion

import pytest

from app.schemas.pista import CalculoIn
from app.services.errores import FueraDeRangoError
from app.services.pistas import calcular_ancho_minimo
from tests.fakes import RepositorioPistasFalso


def _entrada(**cambios: object) -> CalculoIn:
    datos: dict[str, object] = {
        "corriente_a": 1.0,
        "espesor_oz": 1.0,
        "capa": "externa",
        "delta_t_c": 10.0,
    }
    datos.update(cambios)
    return CalculoIn(**datos)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("corriente_a", "espesor_oz", "capa", "delta_t_c", "esperado"),
    [
        (1.0, 1.0, "externa", 10.0, 0.300),
        (1.0, 1.0, "interna", 10.0, 0.781),
        (5.0, 1.0, "externa", 20.0, 1.816),
        (35.0, 3.0, "externa", 100.0, 3.337),
    ],
)
def test_devuelve_los_valores_de_referencia_redondeados(
    corriente_a: float, espesor_oz: float, capa: str, delta_t_c: float, esperado: float
) -> None:
    """Los cuatro casos de `research.md` R-002, ya con el redondeo de la API."""
    resultado = calcular_ancho_minimo(
        _entrada(
            corriente_a=corriente_a, espesor_oz=espesor_oz, capa=capa, delta_t_c=delta_t_c
        )
    )

    assert resultado == esperado


def test_el_resultado_tiene_tres_decimales() -> None:
    resultado = calcular_ancho_minimo(_entrada())

    assert resultado == round(resultado, 3)


def test_caso_de_error_7_la_interna_exige_mas_que_la_externa() -> None:
    """Caso de error 7 de la spec, sobre la función que usan REST y MCP."""
    interna = calcular_ancho_minimo(_entrada(capa="interna"))
    externa = calcular_ancho_minimo(_entrada(capa="externa"))

    assert interna > externa


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
def test_fuera_de_rango_se_rechaza(campo: str, valor: float) -> None:
    """R2 también aquí: no se devuelve un ancho extrapolado (Artículo VIII.5)."""
    with pytest.raises(FueraDeRangoError):
        calcular_ancho_minimo(_entrada(**{campo: valor}))


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("corriente_a", 35.0), ("delta_t_c", 10.0), ("delta_t_c", 100.0), ("espesor_oz", 0.5)],
)
def test_los_extremos_del_rango_si_se_calculan(campo: str, valor: float) -> None:
    assert calcular_ancho_minimo(_entrada(**{campo: valor})) > 0


def test_no_persiste_nada(repo_pistas_falso: RepositorioPistasFalso) -> None:
    """FR-014: la consulta informa, no crea.

    La función no recibe repositorio, así que no hay forma de que escriba. Se comprueba
    además que un repositorio disponible en el test sigue intacto.
    """
    calcular_ancho_minimo(_entrada())

    assert repo_pistas_falso.escrituras == []
    assert repo_pistas_falso.pistas == {}


def test_la_funcion_no_recibe_repositorio() -> None:
    """La ausencia es intencional: no hay nada que guardar."""
    parametros = set(inspeccion.signature(calcular_ancho_minimo).parameters)

    assert parametros == {"datos"}
    assert "repo" not in parametros


def test_es_determinista() -> None:
    assert calcular_ancho_minimo(_entrada()) == calcular_ancho_minimo(_entrada())
