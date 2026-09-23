"""Verificación del cálculo de IPC-2221 contra valores calculados a mano.

El Artículo VII.7 exige valores de referencia calculados a mano, documentados en el
propio test y con tolerancia declarada. Los cuatro casos vienen de `research.md`
R-002 y el primero coincide con el valor que cita la constitución (1 A, ΔT 10 °C,
1 oz, capa externa ≈ 0,30 mm).

Derivación del primer caso, paso a paso:

    ΔT^0.44        = 10^0.44        = 2.75423
    k · ΔT^0.44    = 0.048 · 2.75423 = 0.13220
    I / (k·ΔT^0.44) = 1 / 0.13220    = 7.56475
    A              = 7.56475^(1/0.725) = 16.2960 mils²
    ancho_mils     = 16.2960 / (1 · 1.378) = 11.8258 mils
    ancho_mm       = 11.8258 · 0.0254 = 0.300376 mm  → 0.300 mm

Tolerancia declarada para todas las comparaciones: ±0.001 mm (una micra),
coherente con `TOLERANCIA_MM`.
"""

import pytest

from app.utils.ipc2221 import (
    DECIMALES_ANCHO,
    K_POR_CAPA,
    TOLERANCIA_MM,
    Capa,
    ancho_minimo_mm,
    area_minima_mils2,
    redondear_mm,
)

TOLERANCIA = 0.001

# (corriente_a, espesor_oz, capa, delta_t_c, area_mils2, ancho_mm, redondeado)
CASOS_DE_REFERENCIA = [
    (1.0, 1.0, Capa.EXTERNA, 10.0, 16.2960, 0.300376, 0.300),
    (1.0, 1.0, Capa.INTERNA, 10.0, 42.3931, 0.781411, 0.781),
    (5.0, 1.0, Capa.EXTERNA, 20.0, 98.5107, 1.815800, 1.816),
    (35.0, 3.0, Capa.EXTERNA, 100.0, 543.1672, 3.337312, 3.337),
]


@pytest.mark.parametrize(
    ("corriente_a", "espesor_oz", "capa", "delta_t_c", "area", "ancho", "redondeado"),
    CASOS_DE_REFERENCIA,
)
def test_ancho_minimo_contra_valores_calculados_a_mano(
    corriente_a: float,
    espesor_oz: float,
    capa: Capa,
    delta_t_c: float,
    area: float,
    ancho: float,
    redondeado: float,
) -> None:
    assert area_minima_mils2(corriente_a, capa, delta_t_c) == pytest.approx(area, abs=0.001)

    calculado = ancho_minimo_mm(corriente_a, espesor_oz, capa, delta_t_c)
    assert calculado == pytest.approx(ancho, abs=TOLERANCIA)
    assert redondear_mm(calculado) == redondeado


def test_capa_interna_exige_mas_ancho_que_externa() -> None:
    """Caso de error 7 de la spec: misma entrada, la interna necesita más cobre."""
    interna = ancho_minimo_mm(1.0, 1.0, Capa.INTERNA, 10.0)
    externa = ancho_minimo_mm(1.0, 1.0, Capa.EXTERNA, 10.0)

    assert interna > externa


def test_mas_corriente_exige_mas_ancho() -> None:
    assert ancho_minimo_mm(5.0, 1.0, Capa.EXTERNA, 10.0) > ancho_minimo_mm(
        1.0, 1.0, Capa.EXTERNA, 10.0
    )


def test_mas_espesor_exige_menos_ancho() -> None:
    assert ancho_minimo_mm(1.0, 2.0, Capa.EXTERNA, 10.0) < ancho_minimo_mm(
        1.0, 1.0, Capa.EXTERNA, 10.0
    )


def test_mas_delta_t_admisible_exige_menos_ancho() -> None:
    assert ancho_minimo_mm(1.0, 1.0, Capa.EXTERNA, 40.0) < ancho_minimo_mm(
        1.0, 1.0, Capa.EXTERNA, 10.0
    )


def test_es_funcion_pura_resultado_estable() -> None:
    primero = ancho_minimo_mm(7.0, 1.5, Capa.INTERNA, 25.0)
    segundo = ancho_minimo_mm(7.0, 1.5, Capa.INTERNA, 25.0)

    assert primero == segundo


@pytest.mark.parametrize(
    ("corriente_a", "espesor_oz", "delta_t_c"),
    [
        (0.0, 1.0, 10.0),
        (-1.0, 1.0, 10.0),
        (1.0, 0.0, 10.0),
        (1.0, -1.0, 10.0),
        (1.0, 1.0, 0.0),
        (1.0, 1.0, -5.0),
    ],
)
def test_valores_no_positivos_no_se_calculan(
    corriente_a: float, espesor_oz: float, delta_t_c: float
) -> None:
    """Guarda matemática, no regla de negocio: R2 lo decide el service."""
    with pytest.raises(ValueError):
        ancho_minimo_mm(corriente_a, espesor_oz, Capa.EXTERNA, delta_t_c)


def test_constantes_de_la_norma() -> None:
    assert K_POR_CAPA[Capa.EXTERNA] == 0.048
    assert K_POR_CAPA[Capa.INTERNA] == 0.024
    assert set(K_POR_CAPA) == set(Capa), "toda capa declarada necesita su k"
    assert TOLERANCIA_MM == 0.001
    assert DECIMALES_ANCHO == 3


def test_el_modulo_no_conoce_otras_capas() -> None:
    """Artículo I.4: la función pura no puede depender de services, routers ni repos."""
    import app.utils.ipc2221 as modulo

    fuente = modulo.__file__
    assert fuente is not None
    with open(fuente, encoding="utf-8") as archivo:
        contenido = archivo.read()

    for prohibido in ("app.services", "app.routers", "app.repositories", "sqlalchemy", "fastapi"):
        assert prohibido not in contenido, f"ipc2221.py no debe conocer {prohibido}"
