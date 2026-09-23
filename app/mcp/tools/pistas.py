"""Tools MCP de pistas: adaptadores finos sobre `app/services/pistas.py`.

Artículo VI.1: ninguna tool reimplementa lógica de un service. Cada una traduce
argumentos, llama a la **misma** función de service que usa el router equivalente y
convierte el resultado o la excepción de dominio en una estructura serializable.

Artículo IV.4 y VI.4: la identidad la resuelve `app/mcp/auth.py`; el `usuario_id` nunca
es un argumento de la tool.

Las cuatro tools llegan con sus historias de usuario: `registrar_pista` en T026 (US1),
`calcular_ancho_minimo` en T030 (US2), `listar_pistas` y `eliminar_pista` en T037 (US3).
Este módulo ya existe para que el servidor pueda registrarlas sin que su construcción
dependa de qué historia se haya implementado.
"""

from fastmcp import FastMCP


def registrar_tools(servidor: FastMCP) -> FastMCP:
    """Registra en `servidor` las tools de pistas implementadas hasta ahora."""
    return servidor
