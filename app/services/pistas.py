"""Lógica de negocio de pistas: aquí viven R1, R2, R3, R4 y R5.

Artículo I.2: este módulo no importa SQLAlchemy ni `Session`. Solo conoce el contrato
`PistasRepo`.
Artículo I.4: el cálculo del ancho mínimo es una función pura de `app/utils/ipc2221.py`;
lo que vive aquí es la DECISIÓN de aceptar o rechazar con ese resultado.
Artículo II.1: cada validación está en su propia función (`_validar_ancho`), separada de
la orquestación (`registrar_pista`).
Artículo II.3 (innegociable): el repositorio llega por parámetro con valor por defecto,
que es lo que permite testear con un repositorio falso sin `unittest.mock`.
Artículo VIII.3: las constantes de la norma y la tolerancia se importan de `utils/`;
aquí no se redefine ningún valor numérico de IPC-2221.

En esta tarea (T023) están implementadas R1 y R2. R3 llega en T024, y R4/R5 en US3.
"""

from typing import Any

from app.repositories.pistas import PistasRepo, pistas_repo
from app.schemas.pista import PistaCreate
from app.services.errores import AnchoInsuficienteError, FueraDeRangoError
from app.utils.ipc2221 import (
    CORRIENTE_MAX_A,
    CORRIENTE_MIN_A,
    DELTA_T_MAX_C,
    DELTA_T_MIN_C,
    ESPESOR_MAX_OZ,
    ESPESOR_MIN_OZ,
    TOLERANCIA_MM,
    ancho_minimo_mm,
    redondear_mm,
)


def _validar_parametros_norma(datos: PistaCreate) -> None:
    """R2: los parámetros deben caer dentro del rango de validez de IPC-2221.

    Rango declarado en la spec: corriente en `(0, 35]` A, ΔT en `[10, 100]` °C y espesor
    en `[0.5, 3]` oz. Los extremos son válidos. Fuera de rango se rechaza con un error de
    negocio (que el router traduce a 400) y **nunca** se acepta con una advertencia: el
    Artículo VIII.5 prohíbe extrapolar en silencio.

    Los límites se importan de `app/utils/ipc2221.py`; aquí no se escribe ningún número
    de la norma (Artículo VIII.3).
    """
    if not CORRIENTE_MIN_A < datos.corriente_a <= CORRIENTE_MAX_A:
        raise FueraDeRangoError(
            f"la corriente ({datos.corriente_a} A) está fuera del rango de validez de "
            f"IPC-2221: mayor que {CORRIENTE_MIN_A} A y hasta {CORRIENTE_MAX_A} A"
        )

    if not DELTA_T_MIN_C <= datos.delta_t_c <= DELTA_T_MAX_C:
        raise FueraDeRangoError(
            f"la elevación de temperatura ({datos.delta_t_c} °C) está fuera del rango de "
            f"validez de IPC-2221: entre {DELTA_T_MIN_C} y {DELTA_T_MAX_C} °C"
        )

    if not ESPESOR_MIN_OZ <= datos.espesor_oz <= ESPESOR_MAX_OZ:
        raise FueraDeRangoError(
            f"el espesor de cobre ({datos.espesor_oz} oz) está fuera del rango de validez "
            f"de IPC-2221: entre {ESPESOR_MIN_OZ} y {ESPESOR_MAX_OZ} oz"
        )


def _validar_ancho(datos: PistaCreate) -> float:
    """R1: el ancho diseñado debe alcanzar el mínimo de IPC-2221.

    La comparación es `ancho_mm >= minimo_mm - TOLERANCIA_MM`, escrita como su
    complemento para lanzar el error. Un ancho exactamente igual al mínimo se acepta: no
    se exige ningún margen de seguridad adicional, el margen lo decide el diseñador
    eligiendo un ΔT conservador.

    Devuelve el mínimo calculado para que quien orqueste no tenga que recalcularlo.
    """
    minimo_mm = ancho_minimo_mm(
        corriente_a=datos.corriente_a,
        espesor_oz=datos.espesor_oz,
        capa=datos.capa,
        delta_t_c=datos.delta_t_c,
    )

    if datos.ancho_mm < minimo_mm - TOLERANCIA_MM:
        raise AnchoInsuficienteError(
            f"el ancho diseñado ({datos.ancho_mm} mm) es menor que el mínimo que exige "
            f"IPC-2221 ({redondear_mm(minimo_mm)} mm) para {datos.corriente_a} A, "
            f"{datos.espesor_oz} oz, capa {datos.capa.value} y ΔT {datos.delta_t_c} °C"
        )

    return minimo_mm


def _datos_para_persistir(datos: PistaCreate) -> dict[str, Any]:
    """Traduce el schema a los campos que espera el repositorio."""
    persistibles = datos.model_dump()
    persistibles["capa"] = datos.capa.value
    return persistibles


def registrar_pista(
    datos: PistaCreate,
    usuario_id: int,
    repo: PistasRepo = pistas_repo,
) -> Any:
    """Registra una pista si cumple las reglas de la norma, o lanza el error de negocio.

    El `usuario_id` lo aporta quien llama, y siempre sale de la identidad autenticada:
    el router lo toma de `get_current_user` y la tool MCP de `resolver_identidad`
    (Artículo IV.4).

    El rango (R2) se valida antes del ancho (R1): si los parámetros caen fuera del
    dominio del modelo, el mínimo calculado no significaría nada.
    """
    _validar_parametros_norma(datos)
    _validar_ancho(datos)
    return repo.guardar(usuario_id, _datos_para_persistir(datos))
