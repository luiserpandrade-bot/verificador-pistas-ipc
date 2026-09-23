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

from app.schemas.pista import PistaCreate
from app.services.errores import AnchoInsuficienteError, FueraDeRangoError
from app.services.pistas import registrar_pista
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
