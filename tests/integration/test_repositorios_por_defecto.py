"""Integración de los repositorios "por defecto" (Artículo II.3).

`usuarios_repo` y `pistas_repo` son las instancias que los services usan cuando nadie
inyecta otra: abren y cierran su propia sesión. Es el camino que recorre el servidor MCP
por `stdio`, donde no hay petición HTTP ni dependencia de FastAPI que provea una sesión, así
que no puede quedarse sin pruebas aunque la ruta REST no lo use.

Se ejecuta contra un SQLite real en disco temporal (Artículo VII.4): una base en memoria no
serviría, porque cada operación abre su propia conexión.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.repositories.pistas import RepositorioPistasPorDefecto
from app.repositories.usuarios import RepositorioUsuariosPorDefecto

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
def base_de_datos_temporal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Apunta la configuración de la app a un SQLite temporal con las tablas creadas."""
    import app.database as database
    from app.config import obtener_configuracion

    url = f"sqlite:///{(tmp_path / 'por-defecto.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    obtener_configuracion.cache_clear()
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_fabrica_de_sesiones", None)

    engine = database.crear_engine(url)
    database.Base.metadata.create_all(engine)
    engine.dispose()

    yield

    obtener_configuracion.cache_clear()


def test_el_repositorio_de_usuarios_por_defecto_crea_y_busca(
    base_de_datos_temporal: None,
) -> None:
    repo = RepositorioUsuariosPorDefecto()

    creado = repo.crear("disenador@example.com", "$2b$12$hash")

    assert creado.id is not None
    assert repo.obtener_por_email("disenador@example.com") is not None
    assert repo.obtener_por_id(creado.id) is not None
    assert repo.obtener_por_email("nadie@example.com") is None
    assert repo.obtener_por_id(9999) is None


def test_el_repositorio_de_pistas_por_defecto_cubre_el_ciclo_completo(
    base_de_datos_temporal: None,
) -> None:
    repo_usuarios = RepositorioUsuariosPorDefecto()
    repo = RepositorioPistasPorDefecto()
    usuario_id = repo_usuarios.crear("disenador@example.com", "$2b$12$hash").id

    guardada = repo.guardar(usuario_id, dict(DATOS_PISTA))
    assert guardada.id is not None

    assert [p.id for p in repo.listar_por_usuario(usuario_id)] == [guardada.id]
    assert repo.obtener_por_id(guardada.id) is not None

    actualizada = repo.actualizar(guardada.id, {"ancho_mm": 0.9})
    assert actualizada.ancho_mm == 0.9

    repo.eliminar(guardada.id)
    assert repo.obtener_por_id(guardada.id) is None
    assert repo.listar_por_usuario(usuario_id) == []


def test_el_listado_por_defecto_sigue_filtrando_por_usuario(
    base_de_datos_temporal: None,
) -> None:
    """Artículo III.3: el aislamiento no depende de quién provea la sesión."""
    repo_usuarios = RepositorioUsuariosPorDefecto()
    repo = RepositorioPistasPorDefecto()
    uno = repo_usuarios.crear("uno@example.com", "$2b$12$a").id
    otro = repo_usuarios.crear("otro@example.com", "$2b$12$b").id

    repo.guardar(uno, dict(DATOS_PISTA))
    repo.guardar(otro, dict(DATOS_PISTA))

    assert len(repo.listar_por_usuario(uno)) == 1
    assert len(repo.listar_por_usuario(otro)) == 1


def test_el_listado_por_defecto_respeta_la_paginacion(
    base_de_datos_temporal: None,
) -> None:
    repo_usuarios = RepositorioUsuariosPorDefecto()
    repo = RepositorioPistasPorDefecto()
    usuario_id = repo_usuarios.crear("uno@example.com", "$2b$12$a").id
    for indice in range(4):
        datos = dict(DATOS_PISTA)
        datos["nombre_red"] = f"RED-{indice}"
        repo.guardar(usuario_id, datos)

    pagina = repo.listar_por_usuario(usuario_id, skip=1, limit=2)

    assert [p.nombre_red for p in pagina] == ["RED-1", "RED-2"]
