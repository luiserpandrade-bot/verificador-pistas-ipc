"""Verifica el hash de contraseñas (Artículo IV.1) y los JWT HS256 (Artículo IV.2)."""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.utils.seguridad import (
    ALGORITMO,
    TokenInvalido,
    crear_token_de_acceso,
    decodificar_token,
    hashear_contrasena,
    verificar_contrasena,
)

CLAVE = "clave-de-prueba-no-usada-en-produccion"


def test_el_hash_nunca_es_la_contrasena_en_texto_plano() -> None:
    hash_generado = hashear_contrasena("secreto-del-usuario")

    assert hash_generado != "secreto-del-usuario"
    assert "secreto-del-usuario" not in hash_generado
    assert hash_generado.startswith("$2b$")


def test_dos_hashes_de_la_misma_contrasena_son_distintos() -> None:
    """bcrypt usa sal aleatoria: dos hashes iguales delatarían un esquema roto."""
    assert hashear_contrasena("misma") != hashear_contrasena("misma")


def test_verifica_la_contrasena_correcta_y_rechaza_la_incorrecta() -> None:
    hash_generado = hashear_contrasena("correcta")

    assert verificar_contrasena("correcta", hash_generado) is True
    assert verificar_contrasena("incorrecta", hash_generado) is False


def test_un_hash_con_formato_invalido_no_revienta() -> None:
    assert verificar_contrasena("cualquiera", "esto-no-es-un-hash") is False


def test_token_valido_se_decodifica_al_sujeto() -> None:
    token = crear_token_de_acceso("7", CLAVE, minutos_de_expiracion=30)

    assert decodificar_token(token, CLAVE) == "7"


def test_token_lleva_expiracion_finita() -> None:
    token = crear_token_de_acceso("7", CLAVE, minutos_de_expiracion=30)
    contenido = jwt.decode(token, CLAVE, algorithms=[ALGORITMO])

    assert "exp" in contenido
    esperado = datetime.now(UTC) + timedelta(minutes=30)
    assert abs(contenido["exp"] - esperado.timestamp()) < 5


def test_no_se_puede_crear_un_token_sin_expiracion() -> None:
    """Artículo IV.2: la expiración nunca es infinita."""
    for minutos in (0, -1):
        with pytest.raises(ValueError):
            crear_token_de_acceso("7", CLAVE, minutos_de_expiracion=minutos)


def test_token_expirado_se_rechaza() -> None:
    vencido = jwt.encode(
        {
            "sub": "7",
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        CLAVE,
        algorithm=ALGORITMO,
    )

    with pytest.raises(TokenInvalido):
        decodificar_token(vencido, CLAVE)


def test_token_firmado_con_otra_clave_se_rechaza() -> None:
    ajeno = crear_token_de_acceso("7", "otra-clave-distinta", minutos_de_expiracion=30)

    with pytest.raises(TokenInvalido):
        decodificar_token(ajeno, CLAVE)


def test_token_manipulado_se_rechaza() -> None:
    token = crear_token_de_acceso("7", CLAVE, minutos_de_expiracion=30)
    cabecera, cuerpo, firma = token.split(".")
    manipulado = f"{cabecera}.{cuerpo[:-4]}XXXX.{firma}"

    with pytest.raises(TokenInvalido):
        decodificar_token(manipulado, CLAVE)


def test_token_sin_sujeto_se_rechaza() -> None:
    sin_sub = jwt.encode(
        {"exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())},
        CLAVE,
        algorithm=ALGORITMO,
    )

    with pytest.raises(TokenInvalido):
        decodificar_token(sin_sub, CLAVE)


def test_el_algoritmo_es_hs256() -> None:
    assert ALGORITMO == "HS256"
