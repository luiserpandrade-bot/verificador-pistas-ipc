"""Configuración de logging de la aplicación.

El Artículo IV.1 prohíbe loguear contraseñas y el Artículo IV.3 mantiene los
secretos fuera del código, así que aquí se instala un filtro que redacta los
valores sensibles antes de que lleguen a cualquier handler. El filtro es la última
red de seguridad: lo correcto sigue siendo no pasarle un secreto al logger.

El Artículo IV.5 usa este logging para registrar internamente el detalle de un
error no controlado, del que el cliente solo ve un 500 genérico.
"""

import logging
import re
from typing import Final

FORMATO: Final = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

# Claves cuyo valor nunca debe aparecer en un log, en formato clave=valor,
# "clave": "valor" o clave: valor.
CLAVES_SENSIBLES: Final = (
    "password",
    "contrasena",
    "contraseña",
    "hashed_password",
    "secret_key",
    "access_token",
    "authorization",
)

REDACTADO: Final = "***"

_PATRONES: Final = tuple(
    re.compile(
        rf"(?P<prefijo>[\"']?{clave}[\"']?\s*[=:]\s*)(?P<valor>\"[^\"]*\"|'[^']*'|[^\s,;}}\)]+)",
        re.IGNORECASE,
    )
    for clave in CLAVES_SENSIBLES
    if clave != "authorization"
)

# `authorization` necesita su propio patrón: su valor es `<esquema> <credencial>`
# (por ejemplo `Bearer abc.def.ghi`), así que cortar en el primer espacio redactaría
# solo la palabra `Bearer` y dejaría el token a la vista. Aquí se consume el valor
# completo hasta el final de la línea o el siguiente separador.
_PATRON_AUTORIZACION: Final = re.compile(
    r"(?P<prefijo>[\"']?authorization[\"']?\s*[=:]\s*)(?P<valor>[^,;}\r\n]+)",
    re.IGNORECASE,
)


def redactar(texto: str) -> str:
    """Sustituye por `***` el valor de cualquier clave sensible presente en `texto`."""
    for patron in (*_PATRONES, _PATRON_AUTORIZACION):
        texto = patron.sub(lambda m: f"{m.group('prefijo')}{REDACTADO}", texto)
    return texto


class FiltroDeSecretos(logging.Filter):
    """Redacta valores sensibles en el mensaje y en los argumentos del registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redactar(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    clave: redactar(valor) if isinstance(valor, str) else valor
                    for clave, valor in record.args.items()
                }
            else:
                record.args = tuple(
                    redactar(valor) if isinstance(valor, str) else valor for valor in record.args
                )
        return True


def configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    """Configura el logging raíz con el filtro de secretos y devuelve el logger de la app."""
    manejador = logging.StreamHandler()
    manejador.setFormatter(logging.Formatter(FORMATO))
    manejador.addFilter(FiltroDeSecretos())

    raiz = logging.getLogger()
    raiz.setLevel(nivel)
    for existente in list(raiz.handlers):
        raiz.removeHandler(existente)
    raiz.addHandler(manejador)

    return logging.getLogger("app")
