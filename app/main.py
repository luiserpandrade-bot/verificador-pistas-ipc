"""Arranque de la aplicación: app FastAPI, logging y manejo de errores.

Artículo IV.5: cualquier `Exception` no prevista se convierte en 500 con
`{"detail": "Error interno del servidor"}`. Nunca se devuelve un stack trace ni el
mensaje original al cliente; el detalle se loguea internamente, con el filtro de
secretos de `app/logging_config.py`.

Artículo VII.3: este módulo está en la lista `omit` de cobertura porque es
infraestructura de arranque, no lógica de negocio. La exclusión está declarada en
`pyproject.toml`, no es una omisión silenciosa.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.logging_config import configurar_logging
from app.mcp.server import servidor_mcp
from app.routers.auth import router as router_auth
from app.routers.pistas import router as router_pistas

DETALLE_ERROR_INTERNO = "Error interno del servidor"

#: Prefijo donde se monta el servidor MCP sobre la misma app ASGI.
RUTA_MCP = "/mcp"

logger = configurar_logging()


async def manejar_excepcion_no_controlada(_peticion: Request, error: Exception) -> JSONResponse:
    """Traduce cualquier excepción imprevista a un 500 sin filtrar detalles."""
    logger.exception("excepción no controlada: %s", error)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": DETALLE_ERROR_INTERNO},
    )


def crear_app() -> FastAPI:
    """Construye la aplicación con sus routers, middleware y manejadores."""
    aplicacion = FastAPI(
        title="Verificador de pistas de PCB (IPC-2221)",
        description=(
            "Registra pistas de PCB y verifica si su ancho alcanza el mínimo que exige "
            "IPC-2221 para la corriente que van a conducir."
        ),
        version="0.1.0",
    )

    aplicacion.include_router(router_auth)
    aplicacion.include_router(router_pistas)

    @aplicacion.middleware("http")
    async def registrar_peticiones(
        peticion: Request,
        siguiente: Callable[[Request], Awaitable[object]],
    ):
        """Loguea método, ruta, código y duración de cada petición."""
        inicio = time.perf_counter()
        respuesta = await siguiente(peticion)
        duracion_ms = (time.perf_counter() - inicio) * 1000
        logger.info(
            "%s %s -> %s en %.1f ms",
            peticion.method,
            peticion.url.path,
            getattr(respuesta, "status_code", "?"),
            duracion_ms,
        )
        return respuesta

    aplicacion.add_exception_handler(Exception, manejar_excepcion_no_controlada)

    # El servidor MCP se monta sobre la misma app ASGI, así que REST y MCP comparten
    # proceso y, sobre todo, comparten los mismos services (Artículo VI.1).
    aplicacion.mount(RUTA_MCP, servidor_mcp.http_app())

    return aplicacion


app = crear_app()


def obtener_logger() -> logging.Logger:
    """Logger de la aplicación, expuesto para las demás capas."""
    return logger
