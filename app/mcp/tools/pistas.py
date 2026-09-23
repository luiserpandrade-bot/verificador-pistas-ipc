"""Tools MCP de pistas: adaptadores finos sobre `app/services/pistas.py`.

Artículo VI.1: ninguna tool reimplementa lógica de un service. Cada una traduce
argumentos, llama a la **misma** función de service que usa el router equivalente y
convierte el resultado o la excepción de dominio en una estructura serializable.
`registrar_pista` (tool) y `POST /pistas/` (router) llaman a
`app.services.pistas.registrar_pista()`.

Artículo VI.2: la descripción de cada tool es específica y verificable, nunca genérica.

Artículo VI.3: los errores de negocio se devuelven como `{"error": "..."}`, nunca como
una excepción sin controlar que rompa la sesión del cliente MCP.

Artículo VI.4 y IV.4: la identidad la resuelve `app/mcp/auth.py` a partir del token del
transporte. **La tool no acepta ni `usuario_id` ni `token` como argumento**: pedirle
credenciales al modelo sería exactamente lo que prohíbe el Artículo IV.4.

En esta tarea (T026) se registra `registrar_pista`. `calcular_ancho_minimo` llega en T030,
y `listar_pistas` y `eliminar_pista` en T037.
"""

from typing import Any

from fastmcp import FastMCP
from pydantic import ValidationError

from app.mcp.auth import IdentidadNoDisponible, resolver_identidad
from app.repositories.pistas import PistasRepo, pistas_repo
from app.repositories.usuarios import UsuariosRepo, usuarios_repo
from app.schemas.pista import PistaCreate, PistaOut
from app.services import pistas as servicio_pistas
from app.services.errores import ErrorDeNegocio

DESCRIPCION_REGISTRAR_PISTA = (
    "Registra una pista de PCB con su nombre de red, proyecto, corriente en amperios, "
    "espesor de cobre en onzas, capa (externa o interna), elevación de temperatura "
    "admisible en °C y ancho diseñado en milímetros, y la rechaza si el ancho es menor "
    "al mínimo que exige IPC-2221 para esos parámetros."
)


def token_de_la_sesion() -> str | None:
    """Token JWT del transporte, si lo hay.

    Con transporte HTTP se lee de la cabecera `Authorization`. Con `stdio` no hay
    cabeceras y se devuelve `None`, lo que lleva al fallback de usuario demo documentado
    en `app/mcp/auth.py` (Artículo VI.4).
    """
    try:
        from fastmcp.server.dependencies import get_http_headers

        cabeceras = get_http_headers()
    except Exception:  # noqa: BLE001 - fuera de contexto HTTP no hay cabeceras
        return None

    autorizacion = (cabeceras or {}).get("authorization", "")
    if autorizacion.lower().startswith("bearer "):
        return autorizacion.split(" ", 1)[1].strip() or None
    return None


def _pista_como_dict(pista: Any) -> dict[str, Any]:
    """Serializa la pista con el mismo schema de salida que usa REST (Artículo V.3)."""
    return PistaOut.model_validate(pista).model_dump(mode="json")


def registrar_pista(
    nombre_red: str,
    proyecto: str,
    corriente_a: float,
    espesor_oz: float,
    capa: str,
    delta_t_c: float,
    ancho_mm: float,
    token: str | None = None,
    repo: PistasRepo = pistas_repo,
    repo_usuarios: UsuariosRepo = usuarios_repo,
) -> dict[str, Any]:
    """Implementación de la tool. `token` y los repositorios se inyectan en los tests.

    Los parámetros de dominio son los siete primeros; `token`, `repo` y `repo_usuarios`
    no forman parte de la interfaz que ve el cliente MCP (ver `registrar_tools`).
    """
    try:
        identidad = resolver_identidad(token=token, repo=repo_usuarios)
    except IdentidadNoDisponible as error:
        return {"error": str(error)}

    try:
        datos = PistaCreate(
            nombre_red=nombre_red,
            proyecto=proyecto,
            corriente_a=corriente_a,
            espesor_oz=espesor_oz,
            capa=capa,  # type: ignore[arg-type]
            delta_t_c=delta_t_c,
            ancho_mm=ancho_mm,
        )
    except ValidationError as error:
        # Equivalente al 422 de REST, devuelto como estructura (Artículo VI.3).
        return {
            "error": f"datos inválidos: {error.error_count()} problema(s)",
            "detalle": error.errors(include_url=False),
        }

    try:
        pista = servicio_pistas.registrar_pista(datos, identidad.usuario_id, repo=repo)
    except ErrorDeNegocio as error:
        return {"error": str(error)}

    return {"pista": _pista_como_dict(pista), "usuario_demo": identidad.es_demo}


def registrar_tools(servidor: FastMCP) -> FastMCP:
    """Registra en `servidor` las tools de pistas implementadas hasta ahora."""

    @servidor.tool(name="registrar_pista", description=DESCRIPCION_REGISTRAR_PISTA)
    def _registrar_pista(
        nombre_red: str,
        proyecto: str,
        corriente_a: float,
        espesor_oz: float,
        capa: str,
        delta_t_c: float,
        ancho_mm: float,
    ) -> dict[str, Any]:
        return registrar_pista(
            nombre_red=nombre_red,
            proyecto=proyecto,
            corriente_a=corriente_a,
            espesor_oz=espesor_oz,
            capa=capa,
            delta_t_c=delta_t_c,
            ancho_mm=ancho_mm,
            token=token_de_la_sesion(),
        )

    return servidor
