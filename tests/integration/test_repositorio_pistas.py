"""Integración del repositorio de pistas contra SQLite en memoria (Artículo VII.4).

Incluye la conformidad estructural del repositorio falso contra el `Protocol` real, que
quedó anotada en T012 porque el `Protocol` nace aquí.
"""

import inspect as inspeccion

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.repositories.pistas import PistasRepo, RepositorioPistas, pistas_repo
from tests.fakes import RepositorioPistasFalso

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
def repo(sesion: Session) -> RepositorioPistas:
    return RepositorioPistas(sesion)


@pytest.fixture
def usuario(sesion: Session) -> Usuario:
    usuario = Usuario(email="disenador@example.com", hashed_password="$2b$12$hash")
    sesion.add(usuario)
    sesion.commit()
    sesion.refresh(usuario)
    return usuario


def test_guardar_asocia_la_pista_a_su_usuario(repo: RepositorioPistas, usuario: Usuario) -> None:
    guardada = repo.guardar(usuario.id, dict(DATOS_PISTA))

    assert guardada.id is not None
    assert guardada.usuario_id == usuario.id
    assert guardada.nombre_red == "VBUS"
    assert guardada.ancho_mm == 0.5


def test_guardar_persiste_de_verdad(
    repo: RepositorioPistas, usuario: Usuario, sesion: Session
) -> None:
    usuario_id = usuario.id
    pista_id = repo.guardar(usuario_id, dict(DATOS_PISTA)).id
    # Se vacía la identity map para leer de la base de datos y no de la caché de sesión.
    sesion.expunge_all()

    from app.models.pista import Pista

    recuperada = sesion.get(Pista, pista_id)
    assert recuperada is not None
    assert recuperada.usuario_id == usuario_id


def test_guardar_con_usuario_inexistente_falla(repo: RepositorioPistas) -> None:
    """Artículo III.3: la clave ajena es obligatoria y la base de datos la hace cumplir."""
    with pytest.raises(IntegrityError):
        repo.guardar(9999, dict(DATOS_PISTA))


def test_dos_usuarios_no_comparten_pistas(
    repo: RepositorioPistas, usuario: Usuario, sesion: Session
) -> None:
    otro = Usuario(email="otro@example.com", hashed_password="$2b$12$b")
    sesion.add(otro)
    sesion.commit()

    mia = repo.guardar(usuario.id, dict(DATOS_PISTA))
    suya = repo.guardar(otro.id, dict(DATOS_PISTA))

    assert mia.usuario_id != suya.usuario_id


def test_el_repositorio_no_contiene_reglas_de_negocio() -> None:
    """Artículo I.3: sin umbrales de la norma ni decisiones de pertenencia."""
    import app.repositories.pistas as modulo

    fuente = inspeccion.getsource(modulo)

    for prohibido in ("ipc2221", "ancho_minimo", "TOLERANCIA", "HTTPException", "app.services"):
        assert prohibido not in fuente


def test_el_falso_cumple_el_protocolo_del_repositorio_real() -> None:
    """Conformidad estructural pendiente de T012: el falso implementa `PistasRepo`."""
    falso = RepositorioPistasFalso()

    for operacion in PistasRepo.__protocol_attrs__:  # type: ignore[attr-defined]
        assert hasattr(falso, operacion), f"al falso le falta {operacion}"
        firma_protocolo = inspeccion.signature(getattr(PistasRepo, operacion))
        firma_falsa = inspeccion.signature(getattr(falso, operacion))
        parametros_protocolo = [p for p in firma_protocolo.parameters if p != "self"]
        assert list(firma_falsa.parameters) == parametros_protocolo, operacion


def test_el_repositorio_real_tambien_cumple_el_protocolo(repo: RepositorioPistas) -> None:
    for operacion in PistasRepo.__protocol_attrs__:  # type: ignore[attr-defined]
        assert callable(getattr(repo, operacion))


def test_el_repositorio_por_defecto_cumple_el_protocolo() -> None:
    """Artículo II.3: hay una instancia por defecto lista para inyectar en el service."""
    for operacion in PistasRepo.__protocol_attrs__:  # type: ignore[attr-defined]
        assert callable(getattr(pistas_repo, operacion))
