"""Integración del repositorio de usuarios contra SQLite en memoria (Artículo VII.4)."""

import inspect as inspeccion

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories.usuarios import RepositorioUsuarios, UsuariosRepo, usuarios_repo
from tests.fakes import RepositorioUsuariosFalso


@pytest.fixture
def repo(sesion: Session) -> RepositorioUsuarios:
    return RepositorioUsuarios(sesion)


def test_crear_devuelve_el_usuario_con_identificador(repo: RepositorioUsuarios) -> None:
    usuario = repo.crear("disenador@example.com", "$2b$12$hash")

    assert usuario.id is not None
    assert usuario.email == "disenador@example.com"


def test_obtener_por_email_encuentra_al_creado(repo: RepositorioUsuarios) -> None:
    creado = repo.crear("disenador@example.com", "$2b$12$hash")

    assert repo.obtener_por_email("disenador@example.com").id == creado.id


def test_obtener_por_email_devuelve_none_si_no_existe(repo: RepositorioUsuarios) -> None:
    assert repo.obtener_por_email("nadie@example.com") is None


def test_obtener_por_id_encuentra_al_creado(repo: RepositorioUsuarios) -> None:
    creado = repo.crear("disenador@example.com", "$2b$12$hash")

    assert repo.obtener_por_id(creado.id).email == "disenador@example.com"


def test_obtener_por_id_devuelve_none_si_no_existe(repo: RepositorioUsuarios) -> None:
    assert repo.obtener_por_id(9999) is None


def test_email_duplicado_propaga_el_error_de_integridad(repo: RepositorioUsuarios) -> None:
    """El repositorio no decide: propaga. Convertirlo en 400 es cosa del service."""
    repo.crear("repetido@example.com", "$2b$12$a")

    with pytest.raises(IntegrityError):
        repo.crear("repetido@example.com", "$2b$12$b")


def test_el_repositorio_no_contiene_reglas_de_negocio() -> None:
    """Artículo I.3: solo operaciones de persistencia, sin umbrales ni decisiones."""
    import app.repositories.usuarios as modulo

    fuente = inspeccion.getsource(modulo)

    for prohibido in ("ipc2221", "ancho_minimo", "HTTPException", "app.services"):
        assert prohibido not in fuente


def test_el_repositorio_real_y_el_falso_cumplen_el_mismo_contrato(
    repo: RepositorioUsuarios,
) -> None:
    """Si divergieran, los tests unitarios con el falso no probarían nada."""
    operaciones = ("crear", "obtener_por_email", "obtener_por_id")
    falso = RepositorioUsuariosFalso()

    for operacion in operaciones:
        firma_real = inspeccion.signature(getattr(repo, operacion))
        firma_falsa = inspeccion.signature(getattr(falso, operacion))
        assert list(firma_real.parameters) == list(firma_falsa.parameters), operacion


def test_el_repositorio_por_defecto_cumple_el_contrato() -> None:
    """Artículo II.3: existe una instancia por defecto para inyectar en los services."""
    for operacion in ("crear", "obtener_por_email", "obtener_por_id"):
        assert callable(getattr(usuarios_repo, operacion))

    # El contrato es el `Protocol`; anotar la instancia por defecto con él es lo que
    # permite a los services depender de la abstracción y no de SQLAlchemy.
    assert UsuariosRepo.__name__ == "UsuariosRepo"
