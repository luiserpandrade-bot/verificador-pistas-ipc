"""Tests de las tools MCP de US3: `listar_pistas` y `eliminar_pista`.

Artículo VII.6: cada tool con su caso exitoso y su caso de error de negocio.
Artículo VI.5: la confirmación de la tool destructiva la gestiona el servidor, y eso es lo
que estos tests fijan con más cuidado: sin `confirmar=True` no se borra nada, y la
comprobación de pertenencia ocurre ANTES del paso de confirmación, para que ese paso no
filtre datos de pistas ajenas.
"""

import asyncio
import inspect as inspeccion

import pytest

from app.mcp.tools.pistas import eliminar_pista, listar_pistas
from app.utils.seguridad import crear_token_de_acceso
from tests.fakes import PistaFalsa, RepositorioPistasFalso, RepositorioUsuariosFalso

CLAVE_DE_PRUEBA = "clave-de-prueba-solo-para-tests"

DATOS_PISTA = {
    "nombre_red": "VBUS",
    "proyecto": "fuente-5v",
    "corriente_a": 1.0,
    "espesor_oz": 1.0,
    "capa": "externa",
    "delta_t_c": 10.0,
    "ancho_mm": 0.5,
}


@pytest.fixture
def usuario_con_token(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> tuple[RepositorioUsuariosFalso, int, str]:
    """Usuario real en el repositorio falso, con su token JWT."""
    usuario = repo_usuarios_falso.crear("disenador@example.com", "$2b$12$hash")
    token = crear_token_de_acceso(str(usuario.id), CLAVE_DE_PRUEBA, minutos_de_expiracion=30)
    return repo_usuarios_falso, usuario.id, token


def _guardar(repo: RepositorioPistasFalso, usuario_id: int, nombre_red: str = "VBUS") -> PistaFalsa:
    datos = dict(DATOS_PISTA)
    datos["nombre_red"] = nombre_red
    return repo.guardar(usuario_id, datos)


# --- listar_pistas ------------------------------------------------------------------


def test_listar_pistas_exitoso_devuelve_solo_las_propias(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    repo_usuarios, usuario_id, token = usuario_con_token
    _guardar(repo_pistas_falso, usuario_id, "MIA")
    _guardar(repo_pistas_falso, 999, "AJENA")

    resultado = listar_pistas(
        token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert [p["nombre_red"] for p in resultado["pistas"]] == ["MIA"]
    assert resultado["usuario_demo"] is False


def test_listar_pistas_de_un_usuario_sin_pistas_devuelve_lista_vacia(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    """R4 y Artículo V.1: un listado filtra, nunca deniega."""
    repo_usuarios, _, token = usuario_con_token
    _guardar(repo_pistas_falso, 999, "AJENA")

    resultado = listar_pistas(
        token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert resultado["pistas"] == []
    assert "error" not in resultado


def test_listar_pistas_respeta_la_paginacion(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    repo_usuarios, usuario_id, token = usuario_con_token
    for indice in range(5):
        _guardar(repo_pistas_falso, usuario_id, f"RED-{indice}")

    resultado = listar_pistas(
        skip=1, limit=2, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert [p["nombre_red"] for p in resultado["pistas"]] == ["RED-1", "RED-2"]
    assert (resultado["skip"], resultado["limit"]) == (1, 2)


@pytest.mark.parametrize(("skip", "limit"), [(-1, 20), (0, 0), (0, 101)])
def test_listar_pistas_con_paginacion_invalida_devuelve_error(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
    skip: int,
    limit: int,
) -> None:
    """Artículo VI.3: estructura de error, no excepción (equivalente al 422 de REST)."""
    repo_usuarios, _, token = usuario_con_token

    resultado = listar_pistas(
        skip=skip, limit=limit, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert "paginación inválida" in resultado["error"]


def test_listar_pistas_con_token_invalido_devuelve_error(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = listar_pistas(
        token="no-es-un-token", repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "error" in resultado


# --- eliminar_pista: confirmación gestionada por el servidor (Artículo VI.5) ---------


def test_sin_confirmar_no_borra_y_pide_confirmacion(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    """El valor por defecto es `confirmar=False`: omitirlo nunca borra."""
    repo_usuarios, usuario_id, token = usuario_con_token
    mia = _guardar(repo_pistas_falso, usuario_id)
    repo_pistas_falso.escrituras.clear()

    resultado = eliminar_pista(
        mia.id, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert resultado["confirmacion_requerida"] is True
    assert resultado["pista"]["nombre_red"] == "VBUS"
    assert "confirmar=True" in resultado["mensaje"]
    assert repo_pistas_falso.escrituras == []
    assert mia.id in repo_pistas_falso.pistas


def test_con_confirmar_true_borra(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    repo_usuarios, usuario_id, token = usuario_con_token
    mia = _guardar(repo_pistas_falso, usuario_id)

    resultado = eliminar_pista(
        mia.id, confirmar=True, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert resultado == {"eliminada": True, "pista_id": mia.id}
    assert repo_pistas_falso.pistas == {}
    assert "eliminar" in repo_pistas_falso.escrituras


def test_el_flujo_de_dos_pasos_no_guarda_estado_intermedio(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    """Decisión R-003: la segunda llamada revalida todo desde cero, sin token temporal."""
    repo_usuarios, usuario_id, token = usuario_con_token
    mia = _guardar(repo_pistas_falso, usuario_id)

    primera = eliminar_pista(
        mia.id, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )
    segunda = eliminar_pista(
        mia.id, confirmar=True, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert primera["confirmacion_requerida"] is True
    assert segunda["eliminada"] is True
    # Una tercera llamada ya no encuentra la pista: no quedó nada "pendiente".
    tercera = eliminar_pista(
        mia.id, confirmar=True, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )
    assert "error" in tercera


def test_una_pista_ajena_no_se_revela_en_el_paso_de_confirmacion(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    """Artículo IV.4: la pertenencia se comprueba ANTES de confirmar.

    Si el paso de confirmación devolviera los datos de una pista ajena, la confirmación se
    habría convertido en una fuga de información.
    """
    repo_usuarios, _, token = usuario_con_token
    ajena = _guardar(repo_pistas_falso, 999, "AJENA")

    resultado = eliminar_pista(
        ajena.id, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert "error" in resultado
    assert "pista" not in resultado
    assert "AJENA" not in str(resultado)


def test_una_pista_ajena_no_se_borra_ni_con_confirmar(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    """Caso de error 5 de la spec, por MCP."""
    repo_usuarios, _, token = usuario_con_token
    ajena = _guardar(repo_pistas_falso, 999, "AJENA")
    repo_pistas_falso.escrituras.clear()

    resultado = eliminar_pista(
        ajena.id, confirmar=True, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert "error" in resultado
    assert ajena.id in repo_pistas_falso.pistas
    assert repo_pistas_falso.escrituras == []


def test_una_pista_inexistente_devuelve_error(
    repo_pistas_falso: RepositorioPistasFalso,
    usuario_con_token: tuple[RepositorioUsuariosFalso, int, str],
) -> None:
    """Caso de error 6 de la spec, por MCP."""
    repo_usuarios, _, token = usuario_con_token

    resultado = eliminar_pista(
        9999, confirmar=True, token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios
    )

    assert "error" in resultado
    assert repo_pistas_falso.escrituras == []


def test_confirmar_es_false_por_defecto_en_la_firma() -> None:
    """Artículo VI.5: el servidor no puede depender de que el modelo pregunte."""
    parametro = inspeccion.signature(eliminar_pista).parameters["confirmar"]

    assert parametro.default is False


def test_la_tool_expuesta_pide_confirmacion_y_no_identidad() -> None:
    from fastmcp import FastMCP

    from app.mcp.tools.pistas import registrar_tools

    servidor = registrar_tools(FastMCP(name="prueba"))
    tool = asyncio.run(servidor.get_tool("eliminar_pista"))

    assert tool is not None
    parametros = inspeccion.signature(tool.fn).parameters
    assert set(parametros) == {"pista_id", "confirmar"}
    assert parametros["confirmar"].default is False
    assert "token" not in parametros
    assert "usuario_id" not in parametros


# --- Las cuatro tools del contrato --------------------------------------------------


def test_las_cuatro_tools_del_contrato_estan_registradas() -> None:
    from app.mcp.server import crear_servidor_mcp

    tools = asyncio.run(crear_servidor_mcp().list_tools())

    assert {t.name for t in tools} == {
        "registrar_pista",
        "calcular_ancho_minimo",
        "listar_pistas",
        "eliminar_pista",
    }


def test_las_descripciones_de_us3_son_especificas() -> None:
    """Artículo VI.2."""
    from app.mcp.server import crear_servidor_mcp
    from app.mcp.tools.pistas import DESCRIPCION_ELIMINAR_PISTA, DESCRIPCION_LISTAR_PISTAS

    servidor = crear_servidor_mcp()
    listar = asyncio.run(servidor.get_tool("listar_pistas"))
    eliminar = asyncio.run(servidor.get_tool("eliminar_pista"))

    assert listar is not None and eliminar is not None
    assert listar.description == DESCRIPCION_LISTAR_PISTAS
    assert eliminar.description == DESCRIPCION_ELIMINAR_PISTA
    assert "confirmación explícita" in eliminar.description
    assert "Nunca devuelve pistas de otro usuario" in listar.description


def test_las_tools_de_us3_llaman_a_los_mismos_services_que_los_routers() -> None:
    """Artículo VI.1: sin lógica duplicada."""
    import ast

    import app.mcp.tools.pistas as modulo

    arbol = ast.parse(inspeccion.getsource(modulo))
    atributos = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}

    assert {"listar_pistas", "obtener_pista", "eliminar_pista"} <= atributos
