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

Registradas: `registrar_pista` (T026) y `calcular_ancho_minimo` (T030). `listar_pistas` y
`eliminar_pista` llegan en T037.
"""

from typing import Any

from fastmcp import FastMCP
from pydantic import ValidationError

from app.mcp.auth import IdentidadNoDisponible, resolver_identidad
from app.repositories.pistas import PistasRepo, pistas_repo
from app.repositories.usuarios import UsuariosRepo, usuarios_repo
from app.schemas.pista import CalculoIn, PaginacionParams, PistaCreate, PistaOut
from app.services import pistas as servicio_pistas
from app.services.errores import ErrorDeNegocio

DESCRIPCION_LISTAR_PISTAS = (
    "Lista de forma paginada las pistas de PCB registradas por el usuario autenticado, con "
    "un desplazamiento (skip) y un tamaño de página (limit, máximo 100). Nunca devuelve "
    "pistas de otro usuario."
)

DESCRIPCION_ELIMINAR_PISTA = (
    "Elimina una pista de PCB del usuario autenticado. Requiere confirmación explícita: "
    "sin confirmar=True no borra nada y devuelve qué pista se eliminaría, para que el "
    "usuario pueda revisarla antes de repetir la llamada."
)

DESCRIPCION_CALCULAR_ANCHO = (
    "Calcula el ancho mínimo en milímetros que exige IPC-2221 para una corriente en "
    "amperios, un espesor de cobre en onzas, una capa (externa o interna) y una elevación "
    "de temperatura en °C, sin registrar ninguna pista."
)

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

        # `include={"authorization"}` es imprescindible: por defecto FastMCP **descarta**
        # las cabeceras de credenciales, así que sin esto el token del transporte nunca
        # llegaría y la sesión caería al usuario demo aunque el cliente sí se hubiera
        # autenticado. El Artículo VI.4 exige lo contrario: si hay token verificado, la
        # tool DEBE usar esa identidad.
        cabeceras = get_http_headers(include={"authorization"})
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


def calcular_ancho_minimo(
    corriente_a: float,
    espesor_oz: float,
    capa: str,
    delta_t_c: float,
) -> dict[str, Any]:
    """Implementación de la tool `calcular_ancho_minimo`.

    No resuelve identidad ni recibe repositorio: no persiste nada y no hay datos de
    usuario implicados (FR-014). Llama a la **misma** función de service que
    `POST /pistas/calculo` (Artículo VI.1).
    """
    try:
        datos = CalculoIn(
            corriente_a=corriente_a,
            espesor_oz=espesor_oz,
            capa=capa,  # type: ignore[arg-type]
            delta_t_c=delta_t_c,
        )
    except ValidationError as error:
        return {
            "error": f"datos inválidos: {error.error_count()} problema(s)",
            "detalle": error.errors(include_url=False),
        }

    try:
        minimo_mm = servicio_pistas.calcular_ancho_minimo(datos)
    except ErrorDeNegocio as error:
        return {"error": str(error)}

    return {"ancho_minimo_mm": minimo_mm}


def listar_pistas(
    skip: int = 0,
    limit: int = 20,
    token: str | None = None,
    repo: PistasRepo = pistas_repo,
    repo_usuarios: UsuariosRepo = usuarios_repo,
) -> dict[str, Any]:
    """Implementación de la tool `listar_pistas`.

    Llama a la misma función de service que `GET /pistas/` (Artículo VI.1) y, como ella,
    solo devuelve pistas del usuario de la sesión: filtra, no deniega (R4, Artículo V.1).
    """
    try:
        identidad = resolver_identidad(token=token, repo=repo_usuarios)
    except IdentidadNoDisponible as error:
        return {"error": str(error)}

    try:
        paginacion = PaginacionParams(skip=skip, limit=limit)
    except ValidationError as error:
        return {
            "error": f"paginación inválida: {error.error_count()} problema(s)",
            "detalle": error.errors(include_url=False),
        }

    pistas = servicio_pistas.listar_pistas(
        identidad.usuario_id, skip=paginacion.skip, limit=paginacion.limit, repo=repo
    )
    return {
        "pistas": [_pista_como_dict(pista) for pista in pistas],
        "skip": paginacion.skip,
        "limit": paginacion.limit,
        "usuario_demo": identidad.es_demo,
    }


def eliminar_pista(
    pista_id: int,
    confirmar: bool = False,
    token: str | None = None,
    repo: PistasRepo = pistas_repo,
    repo_usuarios: UsuariosRepo = usuarios_repo,
) -> dict[str, Any]:
    """Implementación de la tool `eliminar_pista`, con confirmación del servidor.

    Artículo VI.5: la confirmación la gestiona **el servidor**, no el modelo. `confirmar`
    vale `False` por defecto, así que una llamada que omita el parámetro nunca borra: el
    servidor se niega y devuelve qué pista se eliminaría.

    Artículo IV.4 y R4: la pertenencia se verifica **antes** de la confirmación, de modo
    que el paso de confirmación no puede convertirse en una fuga de información sobre
    pistas de otros usuarios. Una pista ajena no se muestra ni se borra.

    El borrado efectivo delega en el mismo service que `DELETE /pistas/{id}` (Artículo
    VI.1). No se guarda ningún estado intermedio entre las dos llamadas: la segunda
    revalida todo desde cero (decisión R-003).
    """
    try:
        identidad = resolver_identidad(token=token, repo=repo_usuarios)
    except IdentidadNoDisponible as error:
        return {"error": str(error)}

    try:
        pista = servicio_pistas.obtener_pista(pista_id, identidad.usuario_id, repo=repo)
    except ErrorDeNegocio as error:
        return {"error": str(error)}

    if not confirmar:
        return {
            "confirmacion_requerida": True,
            "pista": _pista_como_dict(pista),
            "mensaje": (
                "Esta llamada no ha eliminado nada. Repite la llamada con confirmar=True "
                "para eliminar esta pista de forma definitiva."
            ),
        }

    try:
        servicio_pistas.eliminar_pista(pista_id, identidad.usuario_id, repo=repo)
    except ErrorDeNegocio as error:
        return {"error": str(error)}

    return {"eliminada": True, "pista_id": pista_id}


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

    @servidor.tool(name="calcular_ancho_minimo", description=DESCRIPCION_CALCULAR_ANCHO)
    def _calcular_ancho_minimo(
        corriente_a: float,
        espesor_oz: float,
        capa: str,
        delta_t_c: float,
    ) -> dict[str, Any]:
        return calcular_ancho_minimo(
            corriente_a=corriente_a,
            espesor_oz=espesor_oz,
            capa=capa,
            delta_t_c=delta_t_c,
        )

    @servidor.tool(name="listar_pistas", description=DESCRIPCION_LISTAR_PISTAS)
    def _listar_pistas(skip: int = 0, limit: int = 20) -> dict[str, Any]:
        return listar_pistas(skip=skip, limit=limit, token=token_de_la_sesion())

    @servidor.tool(name="eliminar_pista", description=DESCRIPCION_ELIMINAR_PISTA)
    def _eliminar_pista(pista_id: int, confirmar: bool = False) -> dict[str, Any]:
        return eliminar_pista(
            pista_id=pista_id, confirmar=confirmar, token=token_de_la_sesion()
        )

    return servidor
