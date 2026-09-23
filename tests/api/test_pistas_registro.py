"""Tests de API de `POST /pistas/`: los casos de error 1, 2, 3 y 4 de la spec.

Artículo VII.5: se sustituyen `get_db` y `get_current_user` con
`app.dependency_overrides`; no se levanta ningún servidor real.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.main import crear_app
from app.models.usuario import Usuario

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


@pytest.fixture
def usuario(sesion: Session) -> Usuario:
    usuario = Usuario(email="disenador@example.com", hashed_password="$2b$12$hash")
    sesion.add(usuario)
    sesion.commit()
    sesion.refresh(usuario)
    return usuario


@pytest.fixture
def cliente(sesion: Session, usuario: Usuario) -> Iterator[TestClient]:
    """Cliente autenticado como `usuario`."""
    aplicacion = crear_app()
    aplicacion.dependency_overrides[get_db] = lambda: sesion
    aplicacion.dependency_overrides[get_current_user] = lambda: usuario
    with TestClient(aplicacion) as cliente:
        yield cliente
    aplicacion.dependency_overrides.clear()


@pytest.fixture
def cliente_sin_autenticar(sesion: Session) -> Iterator[TestClient]:
    aplicacion = crear_app()
    aplicacion.dependency_overrides[get_db] = lambda: sesion
    with TestClient(aplicacion) as cliente:
        yield cliente
    aplicacion.dependency_overrides.clear()


def test_registro_valido_devuelve_201_con_la_pista(cliente: TestClient) -> None:
    respuesta = cliente.post("/pistas/", json=DATOS_VALIDOS)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["nombre_red"] == "VBUS"
    assert cuerpo["capa"] == "externa"
    assert cuerpo["ancho_mm"] == 0.5
    assert "id" in cuerpo


def test_la_respuesta_no_expone_el_propietario(cliente: TestClient) -> None:
    """Artículo IV.4: `usuario_id` no se publica para que no se acepte como entrada."""
    cuerpo = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    assert "usuario_id" not in cuerpo


def test_la_pista_queda_asociada_al_usuario_del_token(
    cliente: TestClient, usuario: Usuario, sesion: Session
) -> None:
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    from app.models.pista import Pista

    persistida = sesion.get(Pista, creada["id"])
    assert persistida is not None
    assert persistida.usuario_id == usuario.id


def test_caso_de_error_1_ancho_insuficiente_devuelve_400(cliente: TestClient) -> None:
    """Caso 1 de la spec: ancho menor al mínimo de IPC-2221 → 400."""
    respuesta = cliente.post("/pistas/", json=_con(ancho_mm=0.1))

    assert respuesta.status_code == 400
    assert "IPC-2221" in respuesta.json()["detail"]


def test_el_400_de_ancho_insuficiente_no_persiste_la_pista(
    cliente: TestClient, sesion: Session
) -> None:
    cliente.post("/pistas/", json=_con(ancho_mm=0.1))

    from app.models.pista import Pista

    assert sesion.query(Pista).count() == 0


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
def test_caso_de_error_2_fuera_de_rango_devuelve_400(
    cliente: TestClient, campo: str, valor: float
) -> None:
    """Caso 2 de la spec: fuera del rango de validez → 400, NO 422.

    Es el test que protege la corrección B1: si los rangos de R2 se replicaran en el
    schema Pydantic, esto devolvería 422 y el contrato quedaría incumplido.
    """
    respuesta = cliente.post("/pistas/", json=_con(**{campo: valor, "ancho_mm": 50.0}))

    assert respuesta.status_code == 400
    assert "rango de validez" in respuesta.json()["detail"]


@pytest.mark.parametrize("capa", ["superficial", "media", "EXTERNA", ""])
def test_caso_de_error_3_capa_invalida_devuelve_422(cliente: TestClient, capa: str) -> None:
    """Caso 3 de la spec: capa distinta de externa/interna → 422 (error de schema)."""
    assert cliente.post("/pistas/", json=_con(capa=capa)).status_code == 422


@pytest.mark.parametrize("valor", [0, -0.5])
def test_ancho_nulo_o_negativo_devuelve_422(cliente: TestClient, valor: float) -> None:
    """Corrección E1: dato inválido es 422, no una pista fuera de norma (400)."""
    assert cliente.post("/pistas/", json=_con(ancho_mm=valor)).status_code == 422


def test_caso_de_error_4_sin_token_devuelve_401(cliente_sin_autenticar: TestClient) -> None:
    """Caso 4 de la spec: registrar sin token → 401."""
    assert cliente_sin_autenticar.post("/pistas/", json=DATOS_VALIDOS).status_code == 401


def test_sin_token_tampoco_se_persiste_nada(
    cliente_sin_autenticar: TestClient, sesion: Session
) -> None:
    cliente_sin_autenticar.post("/pistas/", json=DATOS_VALIDOS)

    from app.models.pista import Pista

    assert sesion.query(Pista).count() == 0


def test_el_ancho_exactamente_igual_al_minimo_se_acepta(cliente: TestClient) -> None:
    """R1 de punta a punta: 0.300 mm es el mínimo reportado para 1 A / 10 °C / 1 oz."""
    assert cliente.post("/pistas/", json=_con(ancho_mm=0.300)).status_code == 201


def test_el_router_no_contiene_reglas_de_negocio() -> None:
    """Artículo I.1: ni comparaciones de ancho ni constantes de la norma."""
    import inspect

    import app.routers.pistas as modulo

    fuente = inspect.getsource(modulo)

    for prohibido in ("ancho_minimo_mm", "TOLERANCIA_MM", "K_POR_CAPA", "0.048", "0.001"):
        assert prohibido not in fuente
