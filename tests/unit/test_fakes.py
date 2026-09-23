"""Verifica que los repositorios falsos se comportan como el contrato real.

Si el falso mintiera, todos los tests unitarios de `services/` mentirían con él. Por eso
se verifica aquí su comportamiento, en particular el filtrado por `usuario_id`
(Artículo III.3), que es lo que sostiene los tests de R4.

La conformidad estructural contra el `Protocol` del repositorio real se comprueba en
`tests/integration/test_repositorio_pistas.py`, cuando ese `Protocol` existe (T014).
"""

import pytest

from tests.fakes import RepositorioPistasFalso, RepositorioUsuariosFalso

DATOS_PISTA = {
    "nombre_red": "VBUS",
    "proyecto": "fuente-5v",
    "corriente_a": 1.0,
    "espesor_oz": 1.0,
    "capa": "externa",
    "delta_t_c": 10.0,
    "ancho_mm": 0.5,
}


def test_no_se_usa_unittest_mock_en_los_falsos() -> None:
    """Artículo VII.2: está prohibido sustituir el repositorio con `unittest.mock`.

    Se inspeccionan los imports con `ast` y no el texto del archivo: mencionar la
    prohibición en un comentario no es usarla.
    """
    import ast

    import tests.fakes as modulo

    assert modulo.__file__ is not None
    arbol = ast.parse(open(modulo.__file__, encoding="utf-8").read())

    importados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module)

    assert not any(nombre.startswith("unittest") for nombre in importados), (
        f"los repositorios falsos no deben importar unittest: {importados}"
    )


def test_usuarios_asigna_identificadores_incrementales() -> None:
    repo = RepositorioUsuariosFalso()

    primero = repo.crear("a@example.com", "$2b$12$a")
    segundo = repo.crear("b@example.com", "$2b$12$b")

    assert (primero.id, segundo.id) == (1, 2)


def test_usuarios_busca_por_email_y_por_id() -> None:
    repo = RepositorioUsuariosFalso()
    creado = repo.crear("a@example.com", "$2b$12$a")

    assert repo.obtener_por_email("a@example.com") == creado
    assert repo.obtener_por_id(creado.id) == creado
    assert repo.obtener_por_email("inexistente@example.com") is None
    assert repo.obtener_por_id(999) is None


def test_pistas_guarda_asociando_al_usuario() -> None:
    repo = RepositorioPistasFalso()

    guardada = repo.guardar(usuario_id=7, datos=dict(DATOS_PISTA))

    assert guardada.id == 1
    assert guardada.usuario_id == 7
    assert guardada.ancho_mm == 0.5
    assert repo.escrituras == ["guardar"]


def test_pistas_lista_solo_las_del_usuario() -> None:
    """Artículo III.3: ninguna consulta de pistas puede omitir el filtro por usuario."""
    repo = RepositorioPistasFalso()
    repo.guardar(usuario_id=1, datos=dict(DATOS_PISTA))
    repo.guardar(usuario_id=2, datos=dict(DATOS_PISTA))
    repo.guardar(usuario_id=1, datos=dict(DATOS_PISTA))

    del_uno = repo.listar_por_usuario(1)

    assert len(del_uno) == 2
    assert {p.usuario_id for p in del_uno} == {1}


def test_pistas_respeta_skip_y_limit() -> None:
    repo = RepositorioPistasFalso()
    for _ in range(5):
        repo.guardar(usuario_id=1, datos=dict(DATOS_PISTA))

    pagina = repo.listar_por_usuario(1, skip=1, limit=2)

    assert [p.id for p in pagina] == [2, 3]


def test_pistas_obtener_por_id_no_filtra_por_usuario() -> None:
    """Deliberado: el service necesita ver la pista para distinguir 403 de 404."""
    repo = RepositorioPistasFalso()
    ajena = repo.guardar(usuario_id=2, datos=dict(DATOS_PISTA))

    assert repo.obtener_por_id(ajena.id) is not None
    assert repo.obtener_por_id(999) is None


def test_pistas_actualiza_y_registra_la_escritura() -> None:
    repo = RepositorioPistasFalso()
    guardada = repo.guardar(usuario_id=1, datos=dict(DATOS_PISTA))

    actualizada = repo.actualizar(guardada.id, {"ancho_mm": 0.9})

    assert actualizada.ancho_mm == 0.9
    assert repo.pistas[guardada.id].ancho_mm == 0.9
    assert repo.escrituras == ["guardar", "actualizar"]


def test_pistas_elimina_y_registra_la_escritura() -> None:
    repo = RepositorioPistasFalso()
    guardada = repo.guardar(usuario_id=1, datos=dict(DATOS_PISTA))

    repo.eliminar(guardada.id)

    assert repo.obtener_por_id(guardada.id) is None
    assert repo.escrituras == ["guardar", "eliminar"]


def test_el_contador_de_escrituras_permite_probar_el_rechazo() -> None:
    """Un rechazo de regla de negocio no debe dejar ninguna escritura registrada."""
    repo = RepositorioPistasFalso()

    assert repo.escrituras == []


def test_las_fixtures_de_conftest_entregan_falsos_vacios(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    assert repo_pistas_falso.pistas == {}
    assert repo_usuarios_falso.usuarios == {}


def test_la_sesion_de_integracion_es_real_y_no_un_falso(sesion) -> None:  # noqa: ANN001
    """Artículo VII.4: integración contra base de datos real, no contra el falso."""
    from sqlalchemy.orm import Session

    assert isinstance(sesion, Session)
    with pytest.raises(AttributeError):
        sesion.escrituras  # noqa: B018
