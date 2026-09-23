"""Tests de los schemas de pista, con foco en qué capa valida qué.

El riesgo que estos tests cierran es concreto: si alguien añadiera `le=35` a
`corriente_a`, el caso de error 2 de la spec pasaría de 400 a 422 y el contrato REST
quedaría incumplido sin que ningún otro test se enterara.
"""

import pytest
from pydantic import ValidationError

from app.schemas.pista import PistaCreate, PistaOut
from app.utils.ipc2221 import Capa

DATOS_VALIDOS = {
    "nombre_red": "VBUS",
    "proyecto": "fuente-5v",
    "corriente_a": 1.0,
    "espesor_oz": 1.0,
    "capa": "externa",
    "delta_t_c": 10.0,
    "ancho_mm": 0.5,
}


def _con(**cambios: object) -> dict[str, object]:
    datos = dict(DATOS_VALIDOS)
    datos.update(cambios)
    return datos


def test_acepta_una_entrada_valida() -> None:
    pista = PistaCreate(**DATOS_VALIDOS)  # type: ignore[arg-type]

    assert pista.capa is Capa.EXTERNA
    assert pista.ancho_mm == 0.5


@pytest.mark.parametrize("valor", ["externa", "interna"])
def test_acepta_las_dos_capas_de_la_norma(valor: str) -> None:
    assert PistaCreate(**_con(capa=valor)).capa.value == valor  # type: ignore[arg-type]


@pytest.mark.parametrize("valor", ["superficial", "EXTERNA", "media", "", "1"])
def test_capa_distinta_de_las_dos_es_error_de_schema(valor: str) -> None:
    """Caso de error 3 de la spec: 422, no 400 (Artículo IV.6 + R3)."""
    with pytest.raises(ValidationError):
        PistaCreate(**_con(capa=valor))  # type: ignore[arg-type]


@pytest.mark.parametrize("valor", [0, 0.0, -0.1, -5])
def test_ancho_nulo_o_negativo_es_error_de_schema(valor: float) -> None:
    """Decisión de la corrección E1: dato inválido → 422, no pista fuera de norma → 400."""
    with pytest.raises(ValidationError):
        PistaCreate(**_con(ancho_mm=valor))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("corriente_a", 36.0),
        ("corriente_a", 100.0),
        ("delta_t_c", 5.0),
        ("delta_t_c", 150.0),
        ("espesor_oz", 0.1),
        ("espesor_oz", 4.0),
    ],
)
def test_el_schema_no_aplica_los_rangos_de_r2(campo: str, valor: float) -> None:
    """Corrección B1: los rangos de R2 son del service y deben producir 400.

    El schema debe DEJAR PASAR estos valores. Si empezara a rechazarlos, el caso de
    error 2 de la spec devolvería 422 en lugar de 400.
    """
    pista = PistaCreate(**_con(**{campo: valor}))  # type: ignore[arg-type]

    assert getattr(pista, campo) == valor


@pytest.mark.parametrize("campo", ["corriente_a", "espesor_oz", "delta_t_c"])
def test_los_valores_no_positivos_si_se_rechazan_en_el_schema(campo: str) -> None:
    """Guarda mínima para que el cálculo esté definido; no es el rango de R2."""
    with pytest.raises(ValidationError):
        PistaCreate(**_con(**{campo: 0}))  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        PistaCreate(**_con(**{campo: -1}))  # type: ignore[arg-type]


@pytest.mark.parametrize("campo", list(DATOS_VALIDOS))
def test_todos_los_campos_son_obligatorios(campo: str) -> None:
    datos = dict(DATOS_VALIDOS)
    del datos[campo]

    with pytest.raises(ValidationError):
        PistaCreate(**datos)  # type: ignore[arg-type]


@pytest.mark.parametrize("campo", ["nombre_red", "proyecto"])
def test_los_textos_no_pueden_estar_vacios(campo: str) -> None:
    with pytest.raises(ValidationError):
        PistaCreate(**_con(**{campo: ""}))  # type: ignore[arg-type]


def test_pista_out_no_expone_el_usuario(tipo_de_salida: type[PistaOut] = PistaOut) -> None:
    """Artículo IV.4 y V.3: el propietario no se publica para que no se acepte como entrada."""
    campos = set(tipo_de_salida.model_fields)

    assert "usuario_id" not in campos
    assert campos == {
        "id",
        "nombre_red",
        "proyecto",
        "corriente_a",
        "espesor_oz",
        "capa",
        "delta_t_c",
        "ancho_mm",
    }


def test_pista_out_no_expone_campos_derivados() -> None:
    """Decisión R-011: el ancho mínimo no se persiste ni se devuelve en la pista."""
    campos = set(PistaOut.model_fields)

    assert "ancho_minimo_mm" not in campos
    assert "conforme" not in campos


def test_pista_out_se_construye_desde_un_objeto_con_atributos() -> None:
    class PistaDePrueba:
        id = 3
        usuario_id = 7
        nombre_red = "GND"
        proyecto = "fuente-5v"
        corriente_a = 2.0
        espesor_oz = 1.0
        capa = "interna"
        delta_t_c = 20.0
        ancho_mm = 1.2

    salida = PistaOut.model_validate(PistaDePrueba())

    assert salida.id == 3
    assert salida.capa is Capa.INTERNA
    assert "usuario_id" not in salida.model_dump()


def test_la_capa_se_serializa_como_texto_de_la_norma() -> None:
    salida = PistaOut.model_validate(
        {
            "id": 1,
            "nombre_red": "VBUS",
            "proyecto": "p",
            "corriente_a": 1.0,
            "espesor_oz": 1.0,
            "capa": "externa",
            "delta_t_c": 10.0,
            "ancho_mm": 0.5,
        }
    )

    assert salida.model_dump(mode="json")["capa"] == "externa"


def test_el_schema_usa_el_enum_de_utils_y_no_uno_propio() -> None:
    """Artículo VIII.3: las constantes de la norma viven en un único módulo."""
    import app.schemas.pista as modulo

    assert modulo.Capa is Capa
