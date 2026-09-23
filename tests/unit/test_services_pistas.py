"""Tests unitarios del service de pistas, una regla de negocio por bloque.

Artículo VII.2: el repositorio falso se inyecta por parámetro y `unittest.mock` no
aparece en este archivo.
Artículo VII.3: cada regla explícita de `spec.md` tiene al menos un test propio,
identificable por nombre (`test_r1_*`, `test_r2_*`, ...).

Valores de referencia usados (de `research.md` R-002, verificados en T005):

- 1 A, ΔT 10 °C, 1 oz, capa externa → mínimo 0.300376 mm
- 1 A, ΔT 10 °C, 1 oz, capa interna → mínimo 0.781411 mm
"""

import ast
import inspect as inspeccion

import pytest

from app.schemas.pista import PistaCreate, PistaUpdate
from app.services.errores import (
    AnchoInsuficienteError,
    FueraDeRangoError,
    PistaAjenaError,
    PistaNoEncontradaError,
)
from app.services.pistas import (
    actualizar_pista,
    eliminar_pista,
    listar_pistas,
    obtener_pista,
    registrar_pista,
)
from app.utils.ipc2221 import K_POR_CAPA, TOLERANCIA_MM, Capa, ancho_minimo_mm
from tests.fakes import RepositorioPistasFalso

USUARIO_ID = 7

MINIMO_EXTERNA = ancho_minimo_mm(1.0, 1.0, Capa.EXTERNA, 10.0)  # 0.300376 mm
MINIMO_INTERNA = ancho_minimo_mm(1.0, 1.0, Capa.INTERNA, 10.0)  # 0.781411 mm


def _pista(**cambios: object) -> PistaCreate:
    datos: dict[str, object] = {
        "nombre_red": "VBUS",
        "proyecto": "fuente-5v",
        "corriente_a": 1.0,
        "espesor_oz": 1.0,
        "capa": "externa",
        "delta_t_c": 10.0,
        "ancho_mm": 0.5,
    }
    datos.update(cambios)
    return PistaCreate(**datos)  # type: ignore[arg-type]


# --- R1: ancho suficiente -----------------------------------------------------------


def test_r1_ancho_holgado_se_acepta(repo_pistas_falso: RepositorioPistasFalso) -> None:
    guardada = registrar_pista(_pista(ancho_mm=0.5), USUARIO_ID, repo=repo_pistas_falso)

    assert guardada.usuario_id == USUARIO_ID
    assert guardada.ancho_mm == 0.5
    assert repo_pistas_falso.escrituras == ["guardar"]


def test_r1_ancho_exactamente_igual_al_minimo_se_acepta(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """La igualdad se acepta: no se exige margen de seguridad adicional."""
    guardada = registrar_pista(
        _pista(ancho_mm=MINIMO_EXTERNA), USUARIO_ID, repo=repo_pistas_falso
    )

    assert guardada.ancho_mm == MINIMO_EXTERNA


def test_r1_ancho_igual_al_minimo_redondeado_se_acepta(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """0.300 mm es el mínimo que reporta la API; rechazarlo sería un falso rechazo."""
    registrar_pista(_pista(ancho_mm=0.300), USUARIO_ID, repo=repo_pistas_falso)

    assert repo_pistas_falso.escrituras == ["guardar"]


def test_r1_dentro_de_la_tolerancia_se_acepta(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """0.0009 mm por debajo del mínimo: la tolerancia juega a favor del diseñador."""
    registrar_pista(
        _pista(ancho_mm=MINIMO_EXTERNA - 0.0009), USUARIO_ID, repo=repo_pistas_falso
    )

    assert repo_pistas_falso.escrituras == ["guardar"]


def test_r1_justo_en_el_borde_de_la_tolerancia_se_acepta(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    registrar_pista(
        _pista(ancho_mm=MINIMO_EXTERNA - TOLERANCIA_MM), USUARIO_ID, repo=repo_pistas_falso
    )

    assert repo_pistas_falso.escrituras == ["guardar"]


def test_r1_fuera_de_la_tolerancia_se_rechaza(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    with pytest.raises(AnchoInsuficienteError):
        registrar_pista(
            _pista(ancho_mm=MINIMO_EXTERNA - 0.002), USUARIO_ID, repo=repo_pistas_falso
        )


def test_r1_al_rechazar_no_persiste_nada(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Rechazar no es guardar mal: la pista no debe existir después del error."""
    with pytest.raises(AnchoInsuficienteError):
        registrar_pista(_pista(ancho_mm=0.1), USUARIO_ID, repo=repo_pistas_falso)

    assert repo_pistas_falso.escrituras == []
    assert repo_pistas_falso.pistas == {}


def test_r1_capa_interna_rechaza_un_ancho_que_valdria_en_externa(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """0.5 mm sobra en capa externa (0.300) y no llega en interna (0.781)."""
    registrar_pista(_pista(capa="externa", ancho_mm=0.5), USUARIO_ID, repo=repo_pistas_falso)

    with pytest.raises(AnchoInsuficienteError):
        registrar_pista(_pista(capa="interna", ancho_mm=0.5), USUARIO_ID, repo=repo_pistas_falso)


def test_r1_el_mensaje_de_error_indica_el_minimo_exigido(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    with pytest.raises(AnchoInsuficienteError) as error:
        registrar_pista(_pista(capa="interna", ancho_mm=0.5), USUARIO_ID, repo=repo_pistas_falso)

    mensaje = str(error.value)
    assert "0.781" in mensaje
    assert "IPC-2221" in mensaje


def test_r1_mas_corriente_endurece_el_minimo(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Un ancho que valía para 1 A puede no valer para 5 A."""
    registrar_pista(_pista(corriente_a=1.0, ancho_mm=0.5), USUARIO_ID, repo=repo_pistas_falso)

    with pytest.raises(AnchoInsuficienteError):
        registrar_pista(_pista(corriente_a=5.0, ancho_mm=0.5), USUARIO_ID, repo=repo_pistas_falso)


# --- Diseño: DIP, capas y constantes ------------------------------------------------


def test_el_repositorio_es_un_parametro_con_valor_por_defecto() -> None:
    """Artículo II.3, innegociable."""
    parametro = inspeccion.signature(registrar_pista).parameters["repo"]

    assert parametro.default is not inspeccion.Parameter.empty


def test_el_service_no_redefine_la_tolerancia_ni_las_constantes() -> None:
    """Artículo VIII.3: se importan de `utils/`, no se copian."""
    import app.services.pistas as modulo

    fuente = inspeccion.getsource(modulo)

    assert "0.001" not in fuente
    assert "0.048" not in fuente
    assert "0.024" not in fuente
    assert "1.378" not in fuente
    assert "0.0254" not in fuente
    assert "TOLERANCIA_MM" in fuente


def test_el_service_no_conoce_la_persistencia_ni_el_framework_web() -> None:
    """Artículos I.2 y R-009."""
    import app.services.pistas as modulo

    arbol = ast.parse(inspeccion.getsource(modulo))
    importados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module)

    for prohibido in ("sqlalchemy", "fastapi", "app.database", "app.models"):
        assert not any(nombre.startswith(prohibido) for nombre in importados), (
            f"services/pistas.py no debe importar {prohibido}: {importados}"
        )


def test_la_validacion_esta_separada_de_la_orquestacion() -> None:
    """Artículo II.1: `_validar_ancho` es su propia función."""
    import app.services.pistas as modulo

    assert callable(modulo._validar_ancho)


def test_no_se_usa_unittest_mock_en_este_archivo() -> None:
    """Artículo VII.2."""
    arbol = ast.parse(open(__file__, encoding="utf-8").read())
    importados = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }

    assert not any(nombre.startswith("unittest") for nombre in importados)


# --- R2: rango de validez del modelo ------------------------------------------------


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("corriente_a", 0.1),
        ("corriente_a", 35.0),
        ("delta_t_c", 10.0),
        ("delta_t_c", 100.0),
        ("espesor_oz", 0.5),
        ("espesor_oz", 3.0),
    ],
)
def test_r2_los_extremos_del_rango_son_validos(
    repo_pistas_falso: RepositorioPistasFalso, campo: str, valor: float
) -> None:
    """Los límites se aceptan: el rango es cerrado salvo en corriente, que es > 0."""
    registrar_pista(
        _pista(**{campo: valor, "ancho_mm": 50.0}), USUARIO_ID, repo=repo_pistas_falso
    )

    assert repo_pistas_falso.escrituras == ["guardar"]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("corriente_a", 35.001),
        ("corriente_a", 36.0),
        ("corriente_a", 100.0),
        ("delta_t_c", 9.99),
        ("delta_t_c", 5.0),
        ("delta_t_c", 100.01),
        ("delta_t_c", 150.0),
        ("espesor_oz", 0.49),
        ("espesor_oz", 0.1),
        ("espesor_oz", 3.01),
        ("espesor_oz", 4.0),
    ],
)
def test_r2_justo_por_fuera_de_cada_limite_se_rechaza(
    repo_pistas_falso: RepositorioPistasFalso, campo: str, valor: float
) -> None:
    """Artículo VIII.5: fuera de rango se rechaza, nunca se extrapola en silencio."""
    with pytest.raises(FueraDeRangoError):
        registrar_pista(
            _pista(**{campo: valor, "ancho_mm": 50.0}), USUARIO_ID, repo=repo_pistas_falso
        )

    assert repo_pistas_falso.escrituras == []


def test_r2_no_se_acepta_con_advertencia(repo_pistas_falso: RepositorioPistasFalso) -> None:
    """La decisión registrada es rechazar, no aceptar avisando."""
    with pytest.raises(FueraDeRangoError):
        registrar_pista(_pista(corriente_a=40.0, ancho_mm=50.0), USUARIO_ID, repo=repo_pistas_falso)

    assert repo_pistas_falso.pistas == {}


def test_r2_se_valida_antes_que_el_ancho(repo_pistas_falso: RepositorioPistasFalso) -> None:
    """Con parámetros fuera de dominio, el mínimo calculado no significaría nada."""
    with pytest.raises(FueraDeRangoError):
        registrar_pista(
            _pista(corriente_a=40.0, ancho_mm=0.001), USUARIO_ID, repo=repo_pistas_falso
        )


def test_r2_el_mensaje_dice_que_parametro_esta_fuera_de_rango(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    with pytest.raises(FueraDeRangoError) as error:
        registrar_pista(_pista(espesor_oz=4.0, ancho_mm=50.0), USUARIO_ID, repo=repo_pistas_falso)

    mensaje = str(error.value)
    assert "espesor" in mensaje
    assert "IPC-2221" in mensaje


def test_r2_los_limites_se_importan_de_utils() -> None:
    """Artículo VIII.3: los números del rango no se escriben en el service."""
    import app.services.pistas as modulo

    fuente = inspeccion.getsource(modulo)

    for numero in ("35", "100", "0.5", "10.0"):
        assert f"= {numero}" not in fuente
    for limite in ("CORRIENTE_MAX_A", "DELTA_T_MIN_C", "ESPESOR_MAX_OZ"):
        assert limite in fuente


# --- R3: constante k según la capa --------------------------------------------------


def test_r3_capa_externa_usa_k_0048(repo_pistas_falso: RepositorioPistasFalso) -> None:
    """Se comprueba por su efecto: el umbral de aceptación es el que da k = 0.048."""
    assert K_POR_CAPA[Capa.EXTERNA] == 0.048

    registrar_pista(
        _pista(capa="externa", ancho_mm=MINIMO_EXTERNA), USUARIO_ID, repo=repo_pistas_falso
    )
    assert repo_pistas_falso.escrituras == ["guardar"]

    with pytest.raises(AnchoInsuficienteError):
        registrar_pista(
            _pista(capa="externa", ancho_mm=MINIMO_EXTERNA - 0.01),
            USUARIO_ID,
            repo=repo_pistas_falso,
        )


def test_r3_capa_interna_usa_k_0024(repo_pistas_falso: RepositorioPistasFalso) -> None:
    assert K_POR_CAPA[Capa.INTERNA] == 0.024

    registrar_pista(
        _pista(capa="interna", ancho_mm=MINIMO_INTERNA), USUARIO_ID, repo=repo_pistas_falso
    )
    assert repo_pistas_falso.escrituras == ["guardar"]

    with pytest.raises(AnchoInsuficienteError):
        registrar_pista(
            _pista(capa="interna", ancho_mm=MINIMO_INTERNA - 0.01),
            USUARIO_ID,
            repo=repo_pistas_falso,
        )


def test_r3_la_interna_siempre_exige_mas_que_la_externa() -> None:
    """Con la mitad de k, la interna necesita más cobre para la misma corriente."""
    assert MINIMO_INTERNA > MINIMO_EXTERNA


@pytest.mark.parametrize("capa_invalida", ["superficial", "media", "EXTERNA", "", None, 3])
def test_r3_una_capa_no_contemplada_no_llega_al_calculo(capa_invalida: object) -> None:
    """Se detiene en el schema (422) y nunca alcanza el service ni la función pura."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _pista(capa=capa_invalida)


def test_r3_el_service_no_tiene_ningun_condicional_por_capa() -> None:
    """Artículo II.2: añadir una capa es añadir una entrada, no reescribir un `if`."""
    import app.services.pistas as modulo

    arbol = ast.parse(inspeccion.getsource(modulo))

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.If):
            fuente_condicion = ast.unparse(nodo.test)
            assert "capa" not in fuente_condicion, f"condicional por capa: {fuente_condicion}"
            for valor in ("externa", "interna", "EXTERNA", "INTERNA"):
                assert valor not in fuente_condicion


def test_r3_la_constante_k_solo_vive_en_utils() -> None:
    """Artículo VIII.3: una sola sede para las constantes de la norma."""
    import app.services.pistas as modulo

    fuente = inspeccion.getsource(modulo)

    assert "K_POR_CAPA" not in fuente, "el service no debe manipular k: lo hace la función pura"
    assert "0.048" not in fuente
    assert "0.024" not in fuente


def test_r3_toda_capa_declarada_tiene_su_k() -> None:
    """Si alguien añade una capa al Enum sin su k, esto falla antes de llegar a producción."""
    assert set(K_POR_CAPA) == set(Capa)


# --- R4: aislamiento por usuario ----------------------------------------------------

OTRO_USUARIO_ID = 99


def _guardar_pista_de(
    repo: RepositorioPistasFalso, usuario_id: int, nombre_red: str = "VBUS"
) -> object:
    return repo.guardar(
        usuario_id,
        {
            "nombre_red": nombre_red,
            "proyecto": "fuente-5v",
            "corriente_a": 1.0,
            "espesor_oz": 1.0,
            "capa": "externa",
            "delta_t_c": 10.0,
            "ancho_mm": 0.5,
        },
    )


def test_r4_el_listado_solo_devuelve_las_propias(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    _guardar_pista_de(repo_pistas_falso, USUARIO_ID, "MIA")
    _guardar_pista_de(repo_pistas_falso, OTRO_USUARIO_ID, "AJENA")

    listado = listar_pistas(USUARIO_ID, repo=repo_pistas_falso)

    assert [p.nombre_red for p in listado] == ["MIA"]


def test_r4_el_listado_nunca_deniega_solo_filtra(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Artículo V.1: `GET /pistas/` no devuelve 403, simplemente no incluye lo ajeno."""
    _guardar_pista_de(repo_pistas_falso, OTRO_USUARIO_ID, "AJENA")

    assert listar_pistas(USUARIO_ID, repo=repo_pistas_falso) == []


def test_r4_el_listado_pagina(repo_pistas_falso: RepositorioPistasFalso) -> None:
    for indice in range(5):
        _guardar_pista_de(repo_pistas_falso, USUARIO_ID, f"RED-{indice}")

    pagina = listar_pistas(USUARIO_ID, skip=1, limit=2, repo=repo_pistas_falso)

    assert [p.nombre_red for p in pagina] == ["RED-1", "RED-2"]


def test_r4_obtener_una_pista_propia_funciona(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    assert obtener_pista(mia.id, USUARIO_ID, repo=repo_pistas_falso).id == mia.id


def test_r4_obtener_una_pista_ajena_lanza_pista_ajena(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Caso de error 5 de la spec: pasar el ID de otro usuario a mano → 403."""
    ajena = _guardar_pista_de(repo_pistas_falso, OTRO_USUARIO_ID)

    with pytest.raises(PistaAjenaError):
        obtener_pista(ajena.id, USUARIO_ID, repo=repo_pistas_falso)


def test_r4_obtener_una_pista_inexistente_lanza_no_encontrada(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Caso de error 6 de la spec: pista inexistente → 404."""
    with pytest.raises(PistaNoEncontradaError):
        obtener_pista(9999, USUARIO_ID, repo=repo_pistas_falso)


def test_r4_ajena_y_no_encontrada_son_errores_distintos(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Artículo V.1 reserva 403 para el recurso existente de otro dueño."""
    ajena = _guardar_pista_de(repo_pistas_falso, OTRO_USUARIO_ID)

    with pytest.raises(PistaAjenaError):
        obtener_pista(ajena.id, USUARIO_ID, repo=repo_pistas_falso)
    with pytest.raises(PistaNoEncontradaError):
        obtener_pista(ajena.id + 1000, USUARIO_ID, repo=repo_pistas_falso)


def test_r4_los_services_de_lectura_reciben_el_repositorio_por_parametro() -> None:
    """Artículo II.3."""
    for funcion in (listar_pistas, obtener_pista):
        parametro = inspeccion.signature(funcion).parameters["repo"]
        assert parametro.default is not inspeccion.Parameter.empty


# --- R5: revalidación al modificar ---------------------------------------------------


def test_r5_una_actualizacion_valida_se_persiste(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    actualizada = actualizar_pista(
        mia.id, PistaUpdate(ancho_mm=0.9), USUARIO_ID, repo=repo_pistas_falso
    )

    assert actualizada.ancho_mm == 0.9
    assert "actualizar" in repo_pistas_falso.escrituras


def test_r5_una_actualizacion_que_deja_el_ancho_insuficiente_se_rechaza(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Subir la corriente sin ensanchar la pista debe rechazarse por completo."""
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    with pytest.raises(AnchoInsuficienteError):
        actualizar_pista(
            mia.id, PistaUpdate(corriente_a=5.0), USUARIO_ID, repo=repo_pistas_falso
        )


def test_r5_al_rechazar_no_llama_a_actualizar_del_repositorio(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """La diferencia entre rechazar y guardar mal: no debe haber escritura."""
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)
    repo_pistas_falso.escrituras.clear()

    with pytest.raises(AnchoInsuficienteError):
        actualizar_pista(mia.id, PistaUpdate(ancho_mm=0.05), USUARIO_ID, repo=repo_pistas_falso)

    assert repo_pistas_falso.escrituras == []


def test_r5_la_pista_conserva_sus_valores_anteriores_tras_un_rechazo(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    with pytest.raises(AnchoInsuficienteError):
        actualizar_pista(mia.id, PistaUpdate(ancho_mm=0.05), USUARIO_ID, repo=repo_pistas_falso)

    intacta = repo_pistas_falso.pistas[mia.id]
    assert intacta.ancho_mm == 0.5
    assert intacta.corriente_a == 1.0


def test_r5_tambien_revalida_el_rango_r2(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """R5 revalida R2, así que un PATCH fuera de rango es 400, no 422."""
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    with pytest.raises(FueraDeRangoError):
        actualizar_pista(
            mia.id, PistaUpdate(corriente_a=40.0), USUARIO_ID, repo=repo_pistas_falso
        )

    assert repo_pistas_falso.pistas[mia.id].corriente_a == 1.0


def test_r5_revalida_con_la_capa_resultante(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Cambiar a capa interna endurece el mínimo: 0.5 mm ya no basta."""
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    with pytest.raises(AnchoInsuficienteError):
        actualizar_pista(
            mia.id, PistaUpdate(capa=Capa.INTERNA), USUARIO_ID, repo=repo_pistas_falso
        )


def test_r5_un_cambio_coherente_de_varios_campos_se_acepta(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Subir corriente y ancho a la vez sí debe pasar."""
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    actualizada = actualizar_pista(
        mia.id,
        PistaUpdate(corriente_a=5.0, delta_t_c=20.0, ancho_mm=2.0),
        USUARIO_ID,
        repo=repo_pistas_falso,
    )

    assert (actualizada.corriente_a, actualizada.ancho_mm) == (5.0, 2.0)


def test_r5_no_existe_estado_no_conforme(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Decisión R-011: se rechaza; no se guarda marcada."""
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    with pytest.raises(AnchoInsuficienteError):
        actualizar_pista(mia.id, PistaUpdate(ancho_mm=0.05), USUARIO_ID, repo=repo_pistas_falso)

    guardada = repo_pistas_falso.pistas[mia.id]
    assert not hasattr(guardada, "conforme")
    assert not hasattr(guardada, "estado")


def test_r5_un_patch_vacio_no_escribe_nada(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)
    repo_pistas_falso.escrituras.clear()

    resultado = actualizar_pista(mia.id, PistaUpdate(), USUARIO_ID, repo=repo_pistas_falso)

    assert resultado.id == mia.id
    assert repo_pistas_falso.escrituras == []


def test_r5_actualizar_una_pista_ajena_se_deniega_antes_de_validar(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Artículo IV.4: la pertenencia se comprueba antes de tocar la pista."""
    ajena = _guardar_pista_de(repo_pistas_falso, OTRO_USUARIO_ID)
    repo_pistas_falso.escrituras.clear()

    with pytest.raises(PistaAjenaError):
        actualizar_pista(ajena.id, PistaUpdate(ancho_mm=9.0), USUARIO_ID, repo=repo_pistas_falso)

    assert repo_pistas_falso.escrituras == []


def test_r5_actualizar_una_pista_inexistente_es_no_encontrada(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    with pytest.raises(PistaNoEncontradaError):
        actualizar_pista(9999, PistaUpdate(ancho_mm=1.0), USUARIO_ID, repo=repo_pistas_falso)


def test_r5_reutiliza_las_mismas_validaciones_que_el_registro() -> None:
    """No hay reglas duplicadas: R5 llama a las funciones de R1 y R2."""
    import app.services.pistas as modulo

    fuente = inspeccion.getsource(modulo.actualizar_pista)

    assert "_validar_parametros_norma" in fuente
    assert "_validar_ancho" in fuente


# --- Borrado (R4 aplicado al eliminar) -----------------------------------------------


def test_eliminar_una_pista_propia_la_borra(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    mia = _guardar_pista_de(repo_pistas_falso, USUARIO_ID)

    eliminar_pista(mia.id, USUARIO_ID, repo=repo_pistas_falso)

    assert repo_pistas_falso.pistas == {}
    assert "eliminar" in repo_pistas_falso.escrituras


def test_eliminar_una_pista_ajena_no_borra_nada(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Caso de error 5: eliminar una pista de otro usuario pasando su ID → 403."""
    ajena = _guardar_pista_de(repo_pistas_falso, OTRO_USUARIO_ID)
    repo_pistas_falso.escrituras.clear()

    with pytest.raises(PistaAjenaError):
        eliminar_pista(ajena.id, USUARIO_ID, repo=repo_pistas_falso)

    assert ajena.id in repo_pistas_falso.pistas
    assert repo_pistas_falso.escrituras == []


def test_eliminar_una_pista_inexistente_es_no_encontrada(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    """Caso de error 6: operar sobre una pista inexistente → 404."""
    with pytest.raises(PistaNoEncontradaError):
        eliminar_pista(9999, USUARIO_ID, repo=repo_pistas_falso)

    assert repo_pistas_falso.escrituras == []


def test_eliminar_solo_borra_la_indicada(
    repo_pistas_falso: RepositorioPistasFalso,
) -> None:
    primera = _guardar_pista_de(repo_pistas_falso, USUARIO_ID, "PRIMERA")
    segunda = _guardar_pista_de(repo_pistas_falso, USUARIO_ID, "SEGUNDA")

    eliminar_pista(primera.id, USUARIO_ID, repo=repo_pistas_falso)

    assert list(repo_pistas_falso.pistas) == [segunda.id]


def test_eliminar_recibe_el_repositorio_por_parametro() -> None:
    """Artículo II.3."""
    parametro = inspeccion.signature(eliminar_pista).parameters["repo"]

    assert parametro.default is not inspeccion.Parameter.empty
