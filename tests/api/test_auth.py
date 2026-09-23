"""Tests de API de las rutas de autenticación.

Artículo VII.5: se sustituye `get_db` con `app.dependency_overrides` y no se levanta
ningún servidor real ni se toca la base de datos de desarrollo. La app que se monta aquí
incluye solo el router de auth: `app/main.py` llega en su propia tarea.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Configuracion
from app.dependencies import get_config, get_db
from app.routers.auth import router as router_auth

CLAVE = "clave-de-prueba"
EMAIL = "disenador@example.com"
CONTRASENA = "secreto-largo"


@pytest.fixture
def cliente(sesion: Session) -> Iterator[TestClient]:
    aplicacion = FastAPI()
    aplicacion.include_router(router_auth)
    aplicacion.dependency_overrides[get_db] = lambda: sesion
    aplicacion.dependency_overrides[get_config] = lambda: Configuracion(  # type: ignore[call-arg]
        _env_file=None,
        secret_key=CLAVE,
        database_url="sqlite+pysqlite:///:memory:",
        access_token_expire_minutes=30,
    )
    with TestClient(aplicacion) as cliente:
        yield cliente
    aplicacion.dependency_overrides.clear()


def test_registro_devuelve_201_con_el_usuario(cliente: TestClient) -> None:
    respuesta = cliente.post("/auth/registro", json={"email": EMAIL, "password": CONTRASENA})

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["email"] == EMAIL
    assert "id" in cuerpo


def test_la_respuesta_de_registro_no_expone_la_contrasena(cliente: TestClient) -> None:
    """FR-002 y Artículo IV.1: ni la contraseña ni su hash salen nunca en una respuesta."""
    respuesta = cliente.post("/auth/registro", json={"email": EMAIL, "password": CONTRASENA})

    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "email"}
    assert CONTRASENA not in respuesta.text
    assert "$2b$" not in respuesta.text


def test_email_repetido_devuelve_400(cliente: TestClient) -> None:
    cliente.post("/auth/registro", json={"email": EMAIL, "password": CONTRASENA})

    respuesta = cliente.post(
        "/auth/registro", json={"email": EMAIL, "password": "otra-clave-larga"}
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "El email ya está registrado"


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"email": "no-es-un-email", "password": CONTRASENA},
        {"email": EMAIL},
        {"password": CONTRASENA},
        {"email": EMAIL, "password": "corta"},
    ],
)
def test_cuerpo_invalido_devuelve_422(cliente: TestClient, cuerpo: dict[str, str]) -> None:
    """Artículo IV.6: la validación de schema ocurre antes de llegar al service."""
    assert cliente.post("/auth/registro", json=cuerpo).status_code == 422


def test_token_con_credenciales_correctas_devuelve_200(cliente: TestClient) -> None:
    cliente.post("/auth/registro", json={"email": EMAIL, "password": CONTRASENA})

    respuesta = cliente.post(
        "/auth/token", data={"username": EMAIL, "password": CONTRASENA}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["access_token"]


def test_el_token_emitido_identifica_al_usuario(cliente: TestClient) -> None:
    registro = cliente.post("/auth/registro", json={"email": EMAIL, "password": CONTRASENA})
    token = cliente.post("/auth/token", data={"username": EMAIL, "password": CONTRASENA}).json()[
        "access_token"
    ]

    from app.utils.seguridad import decodificar_token

    assert decodificar_token(token, CLAVE) == str(registro.json()["id"])


def test_contrasena_incorrecta_devuelve_401(cliente: TestClient) -> None:
    cliente.post("/auth/registro", json={"email": EMAIL, "password": CONTRASENA})

    respuesta = cliente.post("/auth/token", data={"username": EMAIL, "password": "incorrecta"})

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Credenciales inválidas"


def test_usuario_inexistente_devuelve_401(cliente: TestClient) -> None:
    respuesta = cliente.post("/auth/token", data={"username": "nadie@example.com", "password": "x"})

    assert respuesta.status_code == 401


def test_formulario_incompleto_devuelve_422(cliente: TestClient) -> None:
    assert cliente.post("/auth/token", data={"username": EMAIL}).status_code == 422


def test_el_router_no_contiene_reglas_de_negocio() -> None:
    """Artículo I.1: el router traduce; las reglas viven en el service."""
    import inspect

    import app.routers.auth as modulo

    fuente = inspect.getsource(modulo)

    for prohibido in ("hashear_contrasena", "verificar_contrasena", "obtener_por_email"):
        assert prohibido not in fuente
