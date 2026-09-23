"""Tests de API del CRUD de pistas (US3): casos de error 5 y 6 de la spec.

Se usan dos usuarios reales para comprobar el aislamiento del Artículo IV.4 pasando a mano
el identificador ajeno, que es exactamente el ataque que describe el caso de error 5.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.main import crear_app
from app.models.pista import Pista
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


def _ruta(pista: dict[str, object]) -> str:
    return f"/pistas/{pista['id']}"


@pytest.fixture
def usuarios(sesion: Session) -> tuple[Usuario, Usuario]:
    uno = Usuario(email="uno@example.com", hashed_password="$2b$12$a")
    otro = Usuario(email="otro@example.com", hashed_password="$2b$12$b")
    sesion.add_all([uno, otro])
    sesion.commit()
    sesion.refresh(uno)
    sesion.refresh(otro)
    return uno, otro


@pytest.fixture
def cliente(sesion: Session, usuarios: tuple[Usuario, Usuario]) -> Iterator[TestClient]:
    """Cliente autenticado como el primer usuario."""
    uno, _ = usuarios
    aplicacion = crear_app()
    aplicacion.dependency_overrides[get_db] = lambda: sesion
    aplicacion.dependency_overrides[get_current_user] = lambda: uno
    with TestClient(aplicacion) as cliente:
        yield cliente
    aplicacion.dependency_overrides.clear()


@pytest.fixture
def pista_ajena(sesion: Session, usuarios: tuple[Usuario, Usuario]) -> Pista:
    """Pista que pertenece al segundo usuario."""
    _, otro = usuarios
    pista = Pista(usuario_id=otro.id, **DATOS_VALIDOS)  # type: ignore[arg-type]
    sesion.add(pista)
    sesion.commit()
    sesion.refresh(pista)
    return pista


# --- GET /pistas/ -------------------------------------------------------------------


def test_el_listado_devuelve_solo_las_propias(cliente: TestClient, pista_ajena: Pista) -> None:
    cliente.post("/pistas/", json=_con(nombre_red="MIA"))

    respuesta = cliente.get("/pistas/")

    assert respuesta.status_code == 200
    assert [p["nombre_red"] for p in respuesta.json()] == ["MIA"]


def test_el_listado_nunca_devuelve_403(cliente: TestClient, pista_ajena: Pista) -> None:
    """Artículo V.1: `GET /pistas/` filtra, no deniega."""
    respuesta = cliente.get("/pistas/")

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_el_listado_pagina(cliente: TestClient) -> None:
    for indice in range(5):
        cliente.post("/pistas/", json=_con(nombre_red=f"RED-{indice}"))

    cuerpo = cliente.get("/pistas/", params={"skip": 1, "limit": 2}).json()

    assert [p["nombre_red"] for p in cuerpo] == ["RED-1", "RED-2"]


def test_el_listado_usa_los_valores_por_defecto(cliente: TestClient) -> None:
    for indice in range(3):
        cliente.post("/pistas/", json=_con(nombre_red=f"RED-{indice}"))

    assert len(cliente.get("/pistas/").json()) == 3


@pytest.mark.parametrize(
    "params",
    [{"skip": -1}, {"limit": 0}, {"limit": 101}, {"limit": "veinte"}],
)
def test_paginacion_invalida_devuelve_422(cliente: TestClient, params: dict) -> None:
    """Artículo V.2: los valores inválidos son error de schema, no de negocio."""
    assert cliente.get("/pistas/", params=params).status_code == 422


# --- GET /pistas/{id} ---------------------------------------------------------------


def test_leer_una_pista_propia_devuelve_200(cliente: TestClient) -> None:
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    respuesta = cliente.get(_ruta(creada))

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == creada["id"]


def test_caso_de_error_5_leer_una_pista_ajena_devuelve_403(
    cliente: TestClient, pista_ajena: Pista
) -> None:
    """Caso 5 de la spec: pasar a mano el ID de otro usuario → 403."""
    assert cliente.get(f"/pistas/{pista_ajena.id}").status_code == 403


def test_caso_de_error_6_leer_una_pista_inexistente_devuelve_404(cliente: TestClient) -> None:
    """Caso 6 de la spec: pista inexistente → 404."""
    assert cliente.get("/pistas/9999").status_code == 404


# --- PATCH /pistas/{id} -------------------------------------------------------------


def test_actualizar_una_pista_propia_devuelve_200(cliente: TestClient) -> None:
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    respuesta = cliente.patch(_ruta(creada), json={"ancho_mm": 0.9})

    assert respuesta.status_code == 200
    assert respuesta.json()["ancho_mm"] == 0.9


def test_patch_que_deja_la_pista_fuera_de_norma_devuelve_400(cliente: TestClient) -> None:
    """R5: rechazo completo con 400."""
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    respuesta = cliente.patch(_ruta(creada), json={"corriente_a": 5.0})

    assert respuesta.status_code == 400
    assert "IPC-2221" in respuesta.json()["detail"]


def test_tras_un_patch_rechazado_la_pista_conserva_sus_valores(cliente: TestClient) -> None:
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    cliente.patch(_ruta(creada), json={"corriente_a": 5.0})

    actual = cliente.get(_ruta(creada)).json()
    assert actual["corriente_a"] == 1.0
    assert actual["ancho_mm"] == 0.5


def test_patch_fuera_de_rango_devuelve_400(cliente: TestClient) -> None:
    """R5 revalida R2: el PATCH fuera de rango es 400, como la fila del contrato."""
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    respuesta = cliente.patch(_ruta(creada), json={"corriente_a": 40.0})

    assert respuesta.status_code == 400
    assert "rango de validez" in respuesta.json()["detail"]


def test_caso_de_error_5_actualizar_una_pista_ajena_devuelve_403(
    cliente: TestClient, pista_ajena: Pista, sesion: Session
) -> None:
    respuesta = cliente.patch(f"/pistas/{pista_ajena.id}", json={"ancho_mm": 9.0})

    assert respuesta.status_code == 403
    sesion.refresh(pista_ajena)
    assert pista_ajena.ancho_mm == 0.5


def test_actualizar_una_pista_inexistente_devuelve_404(cliente: TestClient) -> None:
    assert cliente.patch("/pistas/9999", json={"ancho_mm": 1.0}).status_code == 404


def test_patch_con_capa_invalida_devuelve_422(cliente: TestClient) -> None:
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    assert cliente.patch(_ruta(creada), json={"capa": "media"}).status_code == 422


def test_patch_no_puede_cambiar_el_propietario(cliente: TestClient) -> None:
    """Artículo IV.4: `usuario_id` no es un campo aceptado."""
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    assert cliente.patch(_ruta(creada), json={"usuario_id": 99}).status_code == 422


# --- DELETE /pistas/{id} ------------------------------------------------------------


def test_eliminar_una_pista_propia_devuelve_204(cliente: TestClient) -> None:
    creada = cliente.post("/pistas/", json=DATOS_VALIDOS).json()

    respuesta = cliente.delete(_ruta(creada))

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert cliente.get("/pistas/").json() == []


def test_caso_de_error_5_eliminar_una_pista_ajena_devuelve_403(
    cliente: TestClient, pista_ajena: Pista, sesion: Session
) -> None:
    respuesta = cliente.delete(f"/pistas/{pista_ajena.id}")

    assert respuesta.status_code == 403
    assert sesion.get(Pista, pista_ajena.id) is not None


def test_caso_de_error_6_eliminar_una_pista_inexistente_devuelve_404(
    cliente: TestClient,
) -> None:
    assert cliente.delete("/pistas/9999").status_code == 404


# --- Sin autenticar -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("get", "/pistas/"),
        ("get", "/pistas/1"),
        ("patch", "/pistas/1"),
        ("delete", "/pistas/1"),
    ],
)
def test_caso_de_error_4_sin_token_todo_devuelve_401(
    sesion: Session, metodo: str, ruta: str
) -> None:
    """Caso 4 de la spec, extendido a todo el CRUD."""
    aplicacion = crear_app()
    aplicacion.dependency_overrides[get_db] = lambda: sesion
    with TestClient(aplicacion) as cliente:
        # `get` y `delete` de TestClient no aceptan cuerpo; `patch` sí lo necesita.
        extra = {"json": {}} if metodo == "patch" else {}
        respuesta = getattr(cliente, metodo)(ruta, **extra)

    assert respuesta.status_code == 401
    aplicacion.dependency_overrides.clear()


# --- Contrato completo --------------------------------------------------------------


def test_el_contrato_expone_las_rutas_de_la_spec() -> None:
    esquema = crear_app().openapi()["paths"]

    assert set(esquema) >= {
        "/auth/registro",
        "/auth/token",
        "/pistas/",
        "/pistas/{pista_id}",
        "/pistas/calculo",
    }
    assert set(esquema["/pistas/"]) == {"post", "get"}
    assert set(esquema["/pistas/{pista_id}"]) == {"get", "patch", "delete"}
