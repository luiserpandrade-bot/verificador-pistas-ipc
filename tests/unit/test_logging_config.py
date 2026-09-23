"""Verifica que el logging se configura y que nunca emite secretos (Artículo IV.1)."""

import logging

from app.logging_config import FORMATO, FiltroDeSecretos, configurar_logging, redactar


def test_configurar_logging_instala_un_unico_handler_con_formato() -> None:
    logger = configurar_logging()
    raiz = logging.getLogger()

    assert len(raiz.handlers) == 1
    assert raiz.handlers[0].formatter._fmt == FORMATO
    assert logger.name == "app"


def test_configurar_logging_es_idempotente() -> None:
    configurar_logging()
    configurar_logging()

    assert len(logging.getLogger().handlers) == 1


def test_redacta_password_en_distintos_formatos() -> None:
    # El valor se sustituye junto con sus comillas: lo que importa es que el
    # secreto desaparezca, no conservar la sintaxis del literal.
    assert redactar('password="secreto"') == "password=***"
    assert redactar("password=secreto") == "password=***"
    assert redactar("'contrasena': 'secreto'") == "'contrasena': ***"
    assert redactar("SECRET_KEY=abc123") == "SECRET_KEY=***"
    # El esquema y la credencial se redactan juntos: cortar en el espacio dejaría
    # el token expuesto detrás de la palabra "Bearer".
    assert redactar("Authorization: Bearer abc.def.ghi") == "Authorization: ***"
    assert "abc.def.ghi" not in redactar("authorization=Bearer abc.def.ghi, ruta=/pistas/")


def test_no_redacta_texto_inocente() -> None:
    mensaje = "usuario_id=7 pista_id=3 ancho_mm=0.5"
    assert redactar(mensaje) == mensaje


def test_el_filtro_redacta_el_mensaje_emitido(caplog) -> None:
    filtro = FiltroDeSecretos()
    registro = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='registro de usuario password="secreto" hashed_password="$2b$12$abc"',
        args=(),
        exc_info=None,
    )

    filtro.filter(registro)

    assert "secreto" not in registro.getMessage()
    assert "$2b$12$abc" not in registro.getMessage()
    assert registro.getMessage().count("***") == 2


def test_el_filtro_redacta_los_argumentos() -> None:
    filtro = FiltroDeSecretos()
    registro = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="cuerpo recibido: %s",
        args=('{"email": "a@b.c", "password": "secreto"}',),
        exc_info=None,
    )

    filtro.filter(registro)

    assert "secreto" not in registro.getMessage()
