"""Cálculo del ancho mínimo de una pista de PCB según IPC-2221.

Se usa **IPC-2221** y no IPC-2152. IPC-2152 es la norma vigente y más precisa, pero
se basa en gráficas sin ecuación cerrada, así que no es implementable como función
determinista sin tabular e interpolar sus curvas. La decisión queda declarada aquí y
en `spec.md`, nunca implícita (Artículo VIII.2).

Ecuación de capacidad de corriente de conductores::

    I = k · ΔT^0.44 · A^0.725

con `I` en amperios, `ΔT` en °C y `A` (área de sección) en mils². Despejando el
área y pasando a ancho::

    A = (I / (k · ΔT^0.44))^(1/0.725)
    ancho_mils = A / (espesor_oz · 1.378)
    ancho_mm   = ancho_mils · 0.0254

Este módulo es la **única** sede de las constantes de la norma (Artículo VIII.3) y
contiene solo funciones puras: mismo input, mismo output, sin efectos secundarios y
sin importar nada de `services/`, `routers/` ni `repositories/` (Artículo I.4).

La DECISIÓN de aceptar o rechazar una pista con estos resultados NO vive aquí: vive
en `app/services/pistas.py`. Este módulo tampoco aplica el rango de validez (R2);
solo publica sus límites como constantes para que el service los use.
"""

from enum import Enum
from typing import Final


class Capa(Enum):
    """Capa del conductor. Determina la constante `k` de la ecuación (R3)."""

    EXTERNA = "externa"
    INTERNA = "interna"


# --- Constantes de la norma IPC-2221 (Artículos VIII.1 y VIII.3) ---

#: Constante `k` por capa. Añadir una capa futura es añadir una entrada aquí y en
#: `Capa`, nunca reescribir un `if` existente (Artículo II.2).
K_POR_CAPA: Final[dict[Capa, float]] = {
    Capa.EXTERNA: 0.048,
    Capa.INTERNA: 0.024,
}

EXPONENTE_DELTA_T: Final = 0.44
EXPONENTE_AREA: Final = 0.725
FACTOR_OZ_A_MILS: Final = 1.378
MM_POR_MIL: Final = 0.0254

# --- Rango de validez del modelo (R2). El service decide qué hacer fuera de él ---

CORRIENTE_MIN_A: Final = 0.0  # exclusivo: la corriente debe ser > 0
CORRIENTE_MAX_A: Final = 35.0
DELTA_T_MIN_C: Final = 10.0
DELTA_T_MAX_C: Final = 100.0
ESPESOR_MIN_OZ: Final = 0.5
ESPESOR_MAX_OZ: Final = 3.0

# --- Comparación y presentación ---

#: Tolerancia absoluta en milímetros, a favor del diseñador, para comparar el ancho
#: diseñado contra el mínimo calculado y evitar falsos rechazos por redondeo.
#: La comparación que la usa vive en el service.
TOLERANCIA_MM: Final = 0.001

#: Decimales con los que se reporta el ancho mínimo.
DECIMALES_ANCHO: Final = 3


def area_minima_mils2(corriente_a: float, capa: Capa, delta_t_c: float) -> float:
    """Área de sección mínima en mils² para conducir `corriente_a` con ese `delta_t_c`.

    Despeje de `A` en `I = k · ΔT^0.44 · A^0.725`.
    """
    if corriente_a <= 0:
        raise ValueError("la corriente debe ser mayor que 0 A")
    if delta_t_c <= 0:
        raise ValueError("la elevación de temperatura debe ser mayor que 0 °C")

    k = K_POR_CAPA[capa]
    return (corriente_a / (k * delta_t_c**EXPONENTE_DELTA_T)) ** (1 / EXPONENTE_AREA)


def ancho_minimo_mm(
    corriente_a: float,
    espesor_oz: float,
    capa: Capa,
    delta_t_c: float,
) -> float:
    """Ancho mínimo en milímetros que exige IPC-2221 para esos parámetros.

    Función pura. Los mils son un detalle interno: la frontera del sistema trabaja
    siempre en milímetros (Artículo VIII.4).

    Lanza `ValueError` solo cuando la ecuación no está definida (valores no
    positivos). El rango de validez del modelo (R2) es una regla de negocio y se
    comprueba en `app/services/pistas.py`, no aquí.
    """
    if espesor_oz <= 0:
        raise ValueError("el espesor de cobre debe ser mayor que 0 oz")

    area_mils2 = area_minima_mils2(corriente_a, capa, delta_t_c)
    ancho_mils = area_mils2 / (espesor_oz * FACTOR_OZ_A_MILS)
    return ancho_mils * MM_POR_MIL


def redondear_mm(valor_mm: float) -> float:
    """Redondea un ancho en milímetros a los decimales con que se reporta."""
    return round(valor_mm, DECIMALES_ANCHO)
