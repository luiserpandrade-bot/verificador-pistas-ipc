"""Tests de las tools MCP.

Artículo VII.6: cada tool tiene como mínimo un caso exitoso y un caso de error de
negocio.
Artículo VI.1: se verifica además que la tool llama al **mismo** service que el router y
que no reimplementa ninguna regla.
"""

import ast
import asyncio
import inspect as inspeccion

import pytest

from app.mcp.auth import EMAIL_USUARIO_DEMO
from app.mcp.tools.pistas import (
    DESCRIPCION_REGISTRAR_PISTA,
    registrar_pista,
)
from app.utils.seguridad import crear_token_de_acceso
from tests.fakes import RepositorioPistasFalso, RepositorioUsuariosFalso

CLAVE_DE_PRUEBA = "clave-de-prueba-solo-para-tests"

ARGUMENTOS_VALIDOS = {
    "nombre_red": "VBUS",
    "proyecto": "fuente-5v",
    "corriente_a": 1.0,
    "espesor_oz": 1.0,
    "capa": "externa",
    "delta_t_c": 10.0,
    "ancho_mm": 0.5,
}


def _con(**cambios: object) -> dict[str, object]:
    argumentos = dict(ARGUMENTOS_VALIDOS)
    argumentos.update(cambios)
    return argumentos


# --- registrar_pista: caso exitoso y casos de error (Artículo VII.6) -----------------


def test_registrar_pista_exitoso_devuelve_la_pista(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = registrar_pista(
        **_con(), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "error" not in resultado
    assert resultado["pista"]["nombre_red"] == "VBUS"
    assert resultado["pista"]["capa"] == "externa"
    assert repo_pistas_falso.escrituras == ["guardar"]


def test_registrar_pista_con_ancho_insuficiente_devuelve_estructura_de_error(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    """Artículo VI.3: error de negocio como `{"error": ...}`, no excepción sin controlar."""
    resultado = registrar_pista(
        **_con(ancho_mm=0.1), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "IPC-2221" in resultado["error"]
    assert repo_pistas_falso.escrituras == []


def test_registrar_pista_fuera_de_rango_devuelve_error(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = registrar_pista(
        **_con(corriente_a=36.0, ancho_mm=50.0),
        repo=repo_pistas_falso,
        repo_usuarios=repo_usuarios_falso,
    )

    assert "rango de validez" in resultado["error"]


def test_registrar_pista_con_capa_invalida_devuelve_error_no_excepcion(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    """El equivalente del 422 de REST, devuelto como estructura."""
    resultado = registrar_pista(
        **_con(capa="superficial"), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "datos inválidos" in resultado["error"]
    assert repo_pistas_falso.escrituras == []


# --- Identidad (Artículos VI.4 y IV.4) ----------------------------------------------


def test_sin_token_opera_como_usuario_demo_y_lo_declara(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = registrar_pista(
        **_con(), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert resultado["usuario_demo"] is True
    assert repo_usuarios_falso.obtener_por_email(EMAIL_USUARIO_DEMO) is not None


def test_con_token_valido_opera_como_ese_usuario(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    usuario = repo_usuarios_falso.crear("disenador@example.com", "$2b$12$hash")
    token = crear_token_de_acceso(str(usuario.id), CLAVE_DE_PRUEBA, minutos_de_expiracion=30)

    resultado = registrar_pista(
        **_con(), token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert resultado["usuario_demo"] is False
    assert repo_pistas_falso.pistas[1].usuario_id == usuario.id


def test_con_token_invalido_devuelve_error_y_no_cae_al_demo(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = registrar_pista(
        **_con(), token="no-es-un-token", repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "error" in resultado
    assert repo_pistas_falso.escrituras == []
    assert repo_usuarios_falso.obtener_por_email(EMAIL_USUARIO_DEMO) is None


def test_la_tool_expuesta_no_acepta_usuario_id_ni_token() -> None:
    """Artículo IV.4: la identidad no se pide al cliente MCP."""
    from fastmcp import FastMCP

    from app.mcp.tools.pistas import registrar_tools

    servidor = registrar_tools(FastMCP(name="prueba"))
    tool = asyncio.run(servidor.get_tool("registrar_pista"))

    assert tool is not None
    parametros = set(inspeccion.signature(tool.fn).parameters)
    assert parametros == {
        "nombre_red",
        "proyecto",
        "corriente_a",
        "espesor_oz",
        "capa",
        "delta_t_c",
        "ancho_mm",
    }
    assert "usuario_id" not in parametros
    assert "token" not in parametros


# --- Registro y descripción ---------------------------------------------------------


def test_la_tool_esta_registrada_en_el_servidor() -> None:
    from app.mcp.server import crear_servidor_mcp

    servidor = crear_servidor_mcp()
    tools = asyncio.run(servidor.list_tools())

    assert "registrar_pista" in {tool.name for tool in tools}


def test_la_descripcion_es_especifica_y_verificable() -> None:
    """Artículo VI.2: nunca genérica como "maneja pistas"."""
    from app.mcp.server import crear_servidor_mcp

    servidor = crear_servidor_mcp()
    tool = asyncio.run(servidor.get_tool("registrar_pista"))

    assert tool is not None
    assert tool.description == DESCRIPCION_REGISTRAR_PISTA
    assert "IPC-2221" in tool.description
    assert "rechaza" in tool.description
    assert len(tool.description) > 80


# --- Reutilización: la tool no reimplementa el service (Artículo VI.1) --------------


def test_la_tool_llama_al_mismo_service_que_el_router() -> None:
    import app.mcp.tools.pistas as modulo_tool
    import app.routers.pistas as modulo_router

    def _importados(modulo: object) -> set[str]:
        arbol = ast.parse(inspeccion.getsource(modulo))  # type: ignore[arg-type]
        nombres: set[str] = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                nombres.add(nodo.module)
        return nombres

    assert "app.services" in _importados(modulo_tool)
    assert "app.services" in _importados(modulo_router)


def test_la_tool_no_reimplementa_ninguna_regla() -> None:
    """Sin cálculo, sin tolerancia y sin constantes de la norma en la capa de tools.

    Se inspeccionan identificadores usados e imports, no el texto del archivo: la cadena
    `"ancho_minimo_mm"` aparece legítimamente como clave de la respuesta de la tool, que es
    muy distinto de llamar a la función pura del cálculo.
    """
    import app.mcp.tools.pistas as modulo

    arbol = ast.parse(inspeccion.getsource(modulo))
    identificadores = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)
    }
    importados = {
        n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module
    }

    for prohibido in ("ancho_minimo_mm", "redondear_mm", "TOLERANCIA_MM", "K_POR_CAPA"):
        assert prohibido not in identificadores, f"la tool no debe usar {prohibido}"
    assert "app.utils.ipc2221" not in importados

    numeros = {
        n.value
        for n in ast.walk(arbol)
        if isinstance(n, ast.Constant) and isinstance(n.value, float)
    }
    assert numeros == set(), f"la tool no debe contener constantes numéricas: {numeros}"


def test_el_token_de_la_sesion_es_none_fuera_de_contexto_http() -> None:
    """Transporte `stdio`: no hay cabeceras, así que no hay token (Artículo VI.4)."""
    from app.mcp.tools.pistas import token_de_la_sesion

    assert token_de_la_sesion() is None


def test_no_se_usa_unittest_mock_en_este_archivo() -> None:
    """Artículo VII.2."""
    arbol = ast.parse(open(__file__, encoding="utf-8").read())
    importados = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }

    assert not any(nombre.startswith("unittest") for nombre in importados)


@pytest.mark.parametrize("campo", ["nombre_red", "proyecto"])
def test_texto_vacio_devuelve_error_de_datos(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
    campo: str,
) -> None:
    resultado = registrar_pista(
        **_con(**{campo: ""}), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "datos inválidos" in resultado["error"]


# --- calcular_ancho_minimo: éxito y error (Artículo VII.6) ---------------------------


def test_calcular_ancho_minimo_exitoso() -> None:
    from app.mcp.tools.pistas import calcular_ancho_minimo

    resultado = calcular_ancho_minimo(
        corriente_a=1.0, espesor_oz=1.0, capa="externa", delta_t_c=10.0
    )

    assert resultado == {"ancho_minimo_mm": 0.3}


def test_calcular_ancho_minimo_fuera_de_rango_devuelve_error() -> None:
    """Artículo VI.3: estructura de error, no excepción (Artículo VIII.5 para R2)."""
    from app.mcp.tools.pistas import calcular_ancho_minimo

    resultado = calcular_ancho_minimo(
        corriente_a=36.0, espesor_oz=1.0, capa="externa", delta_t_c=10.0
    )

    assert "rango de validez" in resultado["error"]


def test_calcular_ancho_minimo_con_capa_invalida_devuelve_error() -> None:
    from app.mcp.tools.pistas import calcular_ancho_minimo

    resultado = calcular_ancho_minimo(
        corriente_a=1.0, espesor_oz=1.0, capa="superficial", delta_t_c=10.0
    )

    assert "datos inválidos" in resultado["error"]


def test_caso_de_error_7_por_mcp() -> None:
    """Caso 7 de la spec: con los mismos parámetros, la interna exige más ancho."""
    from app.mcp.tools.pistas import calcular_ancho_minimo

    interna = calcular_ancho_minimo(
        corriente_a=1.0, espesor_oz=1.0, capa="interna", delta_t_c=10.0
    )
    externa = calcular_ancho_minimo(
        corriente_a=1.0, espesor_oz=1.0, capa="externa", delta_t_c=10.0
    )

    assert interna["ancho_minimo_mm"] == 0.781
    assert externa["ancho_minimo_mm"] == 0.3
    assert interna["ancho_minimo_mm"] > externa["ancho_minimo_mm"]


def test_mcp_y_rest_dan_el_mismo_ancho_minimo() -> None:
    """SC-004: misma entrada, mismo veredicto por las dos interfaces."""
    from app.mcp.tools.pistas import calcular_ancho_minimo
    from app.schemas.pista import CalculoIn
    from app.services.pistas import calcular_ancho_minimo as servicio

    por_mcp = calcular_ancho_minimo(
        corriente_a=5.0, espesor_oz=1.0, capa="externa", delta_t_c=20.0
    )["ancho_minimo_mm"]
    por_servicio = servicio(
        CalculoIn(corriente_a=5.0, espesor_oz=1.0, capa="externa", delta_t_c=20.0)  # type: ignore[arg-type]
    )

    assert por_mcp == por_servicio == 1.816


def test_calcular_ancho_minimo_esta_registrada_con_descripcion_especifica() -> None:
    """Artículo VI.2."""
    from app.mcp.server import crear_servidor_mcp
    from app.mcp.tools.pistas import DESCRIPCION_CALCULAR_ANCHO

    servidor = crear_servidor_mcp()
    tool = asyncio.run(servidor.get_tool("calcular_ancho_minimo"))

    assert tool is not None
    assert tool.description == DESCRIPCION_CALCULAR_ANCHO
    assert "IPC-2221" in tool.description
    assert "sin registrar" in tool.description


def test_la_tool_de_calculo_no_pide_identidad_ni_repositorio() -> None:
    """No hay datos de usuario implicados: no persiste nada (FR-014)."""
    from app.mcp.tools.pistas import calcular_ancho_minimo

    parametros = set(inspeccion.signature(calcular_ancho_minimo).parameters)

    assert parametros == {"corriente_a", "espesor_oz", "capa", "delta_t_c"}


def test_las_dos_tools_estan_registradas() -> None:
    from app.mcp.server import crear_servidor_mcp

    tools = asyncio.run(crear_servidor_mcp().list_tools())

    assert {"registrar_pista", "calcular_ancho_minimo"} <= {t.name for t in tools}
