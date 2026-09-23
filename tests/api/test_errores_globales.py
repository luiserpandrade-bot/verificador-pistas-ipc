"""Verifica el manejo de errores no controlados (Artículo IV.5) y el arranque de la app.

Lo que se comprueba es exactamente lo que el artículo prohíbe: que el cliente vea el
mensaje de la excepción o un stack trace. El detalle debe quedar en el log interno.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import DETALLE_ERROR_INTERNO, crear_app

MENSAJE_SECRETO_DE_LA_EXCEPCION = "detalle interno que no debe salir: password=secreto"


@pytest.fixture
def cliente_con_ruta_que_falla() -> TestClient:
    aplicacion = crear_app()

    @aplicacion.get("/_prueba/explota")
    def explota() -> None:
        raise RuntimeError(MENSAJE_SECRETO_DE_LA_EXCEPCION)

    # `raise_server_exceptions=False` hace que el cliente reciba la respuesta del
    # manejador en vez de que la excepción se propague al test.
    return TestClient(aplicacion, raise_server_exceptions=False)


def test_excepcion_no_controlada_devuelve_500_con_detalle_generico(
    cliente_con_ruta_que_falla: TestClient,
) -> None:
    respuesta = cliente_con_ruta_que_falla.get("/_prueba/explota")

    assert respuesta.status_code == 500
    assert respuesta.json() == {"detail": DETALLE_ERROR_INTERNO}


def test_el_cliente_no_ve_el_mensaje_de_la_excepcion_ni_el_stack_trace(
    cliente_con_ruta_que_falla: TestClient,
) -> None:
    respuesta = cliente_con_ruta_que_falla.get("/_prueba/explota")

    assert MENSAJE_SECRETO_DE_LA_EXCEPCION not in respuesta.text
    assert "RuntimeError" not in respuesta.text
    assert "Traceback" not in respuesta.text
    assert "app/main.py" not in respuesta.text


def test_el_detalle_si_se_loguea_internamente(
    cliente_con_ruta_que_falla: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """El detalle no se pierde: queda en el log, con los secretos redactados."""
    with caplog.at_level("ERROR"):
        cliente_con_ruta_que_falla.get("/_prueba/explota")

    assert "excepción no controlada" in caplog.text
    assert "detalle interno que no debe salir" in caplog.text


def test_el_detalle_logueado_no_incluye_la_contrasena(
    cliente_con_ruta_que_falla: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Artículo IV.1: el filtro de secretos también actúa en los logs de error."""
    from app.logging_config import redactar

    with caplog.at_level("ERROR"):
        cliente_con_ruta_que_falla.get("/_prueba/explota")

    assert "password=secreto" not in redactar(caplog.text)


def test_la_app_monta_el_router_de_auth() -> None:
    # Se leen del esquema OpenAPI y no de `app.routes`: FastAPI 0.141 mete ahí objetos
    # `_IncludedRouter` que no exponen `.path`.
    rutas = set(crear_app().openapi()["paths"])

    assert "/auth/registro" in rutas
    assert "/auth/token" in rutas


def test_una_ruta_normal_sigue_funcionando() -> None:
    """El manejador global no debe tragarse las respuestas correctas."""
    cliente = TestClient(crear_app())

    assert cliente.get("/openapi.json").status_code == 200


def test_un_422_de_validacion_no_se_convierte_en_500() -> None:
    """Los errores previstos conservan su código; el 500 es solo para lo imprevisto."""
    cliente = TestClient(crear_app())

    respuesta = cliente.post("/auth/registro", json={"email": "no-vale"})

    assert respuesta.status_code == 422
