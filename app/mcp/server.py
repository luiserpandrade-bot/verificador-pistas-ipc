"""Servidor MCP construido con FastMCP.

Artículo VI.1: las tools que se registren aquí son adaptadores finos sobre
`app/services/`. Este módulo solo crea el servidor y expone su app ASGI para montarla
junto a la API REST; no contiene ninguna regla de negocio.

Las cuatro tools (`registrar_pista`, `calcular_ancho_minimo`, `listar_pistas`,
`eliminar_pista`) se registran en `app/mcp/tools/pistas.py` durante las historias de
usuario: T026 (US1), T030 (US2) y T037 (US3).

Artículo VII.3: módulo en la lista `omit` de cobertura, por ser infraestructura.
"""

from fastmcp import FastMCP

INSTRUCCIONES = (
    "Verificador de pistas de PCB según IPC-2221. Permite registrar pistas, calcular el "
    "ancho mínimo que exige la norma para una corriente dada, listar las pistas del "
    "usuario y eliminarlas con confirmación explícita."
)


def crear_servidor_mcp() -> FastMCP:
    """Crea el servidor MCP con sus tools registradas."""
    servidor = FastMCP(name="verificador-pistas-ipc2221", instructions=INSTRUCCIONES)

    from app.mcp.tools import pistas as tools_pistas

    tools_pistas.registrar_tools(servidor)

    return servidor


servidor_mcp = crear_servidor_mcp()
