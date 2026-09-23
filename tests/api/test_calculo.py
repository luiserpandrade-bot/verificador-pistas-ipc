"""Tests de API de `POST /pistas/calculo` (US2).

Verifica los cuatro códigos del contrato y, sobre todo, que la consulta no crea nada.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.main import crear_app
from app.models.usuario import Usuario

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


@pytest.fixture
def usuario(sesion: Session) -> Usuario:
    usuario = Usuario(email="disenador@example.com", hashed_password="$2b$12$hash")
    sesion.add(usuario)
    sesion.commit()
    sesion.refresh(usuario)
    return usuario


@pytest.fixture
def cliente(sesion: Session, usuario: Usuario) -> Iterator[TestClient]:
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


def test_devuelve_200_con_el_ancho_minimo(cliente: TestClient) -> None:
    respuesta = cliente.post("/pistas/calculo", json=DATOS_VALIDOS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ancho_minimo_mm": 0.3}


def test_la_capa_interna_devuelve_mas_ancho_que_la_externa(cliente: TestClient) -> None:
    """Caso de error 7 de la spec, de punta a punta por REST."""
    interna = cliente.post("/pistas/calculo", json=_con(capa="interna")).json()
    externa = cliente.post("/pistas/calculo", json=_con(capa="externa")).json()

    assert interna["ancho_minimo_mm"] == 0.781
    assert externa["ancho_minimo_mm"] == 0.3
    assert interna["ancho_minimo_mm"] > externa["ancho_minimo_mm"]


def test_no_persiste_ninguna_pista(cliente: TestClient, sesion: Session) -> None:
    """FR-014: consultar no crea."""
    from app.models.pista import Pista

    cliente.post("/pistas/calculo", json=DATOS_VALIDOS)
    cliente.post("/pistas/calculo", json=_con(capa="interna"))

    assert sesion.query(Pista).count() == 0


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("corriente_a", 36.0), ("delta_t_c", 5.0), ("espesor_oz", 4.0)],
)
def test_fuera_de_rango_devuelve_400(cliente: TestClient, campo: str, valor: float) -> None:
    respuesta = cliente.post("/pistas/calculo", json=_con(**{campo: valor}))

    assert respuesta.status_code == 400
    assert "rango de validez" in respuesta.json()["detail"]


@pytest.mark.parametrize("capa", ["superficial", "EXTERNA", ""])
def test_capa_invalida_devuelve_422(cliente: TestClient, capa: str) -> None:
    assert cliente.post("/pistas/calculo", json=_con(capa=capa)).status_code == 422


def test_falta_un_campo_devuelve_422(cliente: TestClient) -> None:
    assert cliente.post("/pistas/calculo", json={"corriente_a": 1.0}).status_code == 422


def test_sin_token_devuelve_401(cliente_sin_autenticar: TestClient) -> None:
    """FR-004: la consulta también exige identidad autenticada."""
    assert cliente_sin_autenticar.post("/pistas/calculo", json=DATOS_VALIDOS).status_code == 401


def test_el_endpoint_no_pide_repositorio() -> None:
    """No toca la base de datos, y eso se ve en su firma."""
    import inspect

    from app.routers.pistas import calcular

    assert "repo" not in inspect.signature(calcular).parameters
