"""Integración del CRUD del repositorio de pistas (US3, Artículos I.3, III.3 y VII.4).

La propiedad crítica que fijan estos tests: **ninguna** operación de listado devuelve ni
modifica pistas de otro usuario, ni siquiera cuando el otro usuario existe y tiene datos.
"""

import pytest
from sqlalchemy.orm import Session

from app.models.pista import Pista
from app.models.usuario import Usuario
from app.repositories.pistas import RepositorioPistas

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
def dos_usuarios(sesion: Session) -> tuple[Usuario, Usuario]:
    uno = Usuario(email="uno@example.com", hashed_password="$2b$12$a")
    otro = Usuario(email="otro@example.com", hashed_password="$2b$12$b")
    sesion.add_all([uno, otro])
    sesion.commit()
    sesion.refresh(uno)
    sesion.refresh(otro)
    return uno, otro


def _datos(**cambios: object) -> dict[str, object]:
    datos = dict(DATOS_PISTA)
    datos.update(cambios)
    return datos


# --- Listado ------------------------------------------------------------------------


def test_listar_devuelve_solo_las_del_usuario(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, otro = dos_usuarios
    repo.guardar(uno.id, _datos(nombre_red="MIA-1"))
    repo.guardar(otro.id, _datos(nombre_red="SUYA"))
    repo.guardar(uno.id, _datos(nombre_red="MIA-2"))

    listado = repo.listar_por_usuario(uno.id)

    assert {p.nombre_red for p in listado} == {"MIA-1", "MIA-2"}
    assert all(p.usuario_id == uno.id for p in listado)


def test_listar_de_un_usuario_sin_pistas_devuelve_vacio(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, otro = dos_usuarios
    repo.guardar(otro.id, _datos())

    assert repo.listar_por_usuario(uno.id) == []


def test_listar_respeta_skip_y_limit(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, _ = dos_usuarios
    for indice in range(5):
        repo.guardar(uno.id, _datos(nombre_red=f"RED-{indice}"))

    pagina = repo.listar_por_usuario(uno.id, skip=1, limit=2)

    assert [p.nombre_red for p in pagina] == ["RED-1", "RED-2"]


def test_listar_esta_ordenado_por_identificador(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, _ = dos_usuarios
    for indice in range(4):
        repo.guardar(uno.id, _datos(nombre_red=f"RED-{indice}"))

    identificadores = [p.id for p in repo.listar_por_usuario(uno.id)]

    assert identificadores == sorted(identificadores)


def test_la_paginacion_no_filtra_pistas_ajenas_al_paginar(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    """El offset se aplica sobre las propias, no sobre la tabla entera."""
    uno, otro = dos_usuarios
    for _ in range(3):
        repo.guardar(otro.id, _datos(nombre_red="AJENA"))
    repo.guardar(uno.id, _datos(nombre_red="MIA"))

    assert [p.nombre_red for p in repo.listar_por_usuario(uno.id, skip=0, limit=10)] == ["MIA"]


# --- Lectura ------------------------------------------------------------------------


def test_obtener_por_id_devuelve_la_pista(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, _ = dos_usuarios
    guardada = repo.guardar(uno.id, _datos())

    assert repo.obtener_por_id(guardada.id).id == guardada.id


def test_obtener_por_id_inexistente_devuelve_none(repo: RepositorioPistas) -> None:
    assert repo.obtener_por_id(9999) is None


def test_obtener_por_id_no_filtra_por_usuario(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    """Deliberado: el service necesita verla para distinguir 403 de 404."""
    _, otro = dos_usuarios
    ajena = repo.guardar(otro.id, _datos())

    recuperada = repo.obtener_por_id(ajena.id)

    assert recuperada is not None
    assert recuperada.usuario_id == otro.id


# --- Actualización ------------------------------------------------------------------


def test_actualizar_aplica_solo_los_campos_dados(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, _ = dos_usuarios
    guardada = repo.guardar(uno.id, _datos())

    actualizada = repo.actualizar(guardada.id, {"ancho_mm": 0.9})

    assert actualizada.ancho_mm == 0.9
    assert actualizada.nombre_red == "VBUS"
    assert actualizada.corriente_a == 1.0


def test_actualizar_persiste_de_verdad(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario], sesion: Session
) -> None:
    uno, _ = dos_usuarios
    pista_id = repo.guardar(uno.id, _datos()).id
    repo.actualizar(pista_id, {"capa": "interna", "ancho_mm": 1.5})
    sesion.expunge_all()

    recuperada = sesion.get(Pista, pista_id)
    assert recuperada is not None
    assert recuperada.capa == "interna"
    assert recuperada.ancho_mm == 1.5


def test_actualizar_no_cambia_el_propietario(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, _ = dos_usuarios
    guardada = repo.guardar(uno.id, _datos())

    actualizada = repo.actualizar(guardada.id, {"ancho_mm": 0.9})

    assert actualizada.usuario_id == uno.id


def test_actualizar_una_pista_inexistente_falla(repo: RepositorioPistas) -> None:
    with pytest.raises(KeyError):
        repo.actualizar(9999, {"ancho_mm": 1.0})


# --- Borrado ------------------------------------------------------------------------


def test_eliminar_borra_la_pista(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, _ = dos_usuarios
    guardada = repo.guardar(uno.id, _datos())

    repo.eliminar(guardada.id)

    assert repo.obtener_por_id(guardada.id) is None
    assert repo.listar_por_usuario(uno.id) == []


def test_eliminar_no_toca_las_demas(
    repo: RepositorioPistas, dos_usuarios: tuple[Usuario, Usuario]
) -> None:
    uno, otro = dos_usuarios
    mia = repo.guardar(uno.id, _datos(nombre_red="MIA"))
    ajena = repo.guardar(otro.id, _datos(nombre_red="AJENA"))

    repo.eliminar(mia.id)

    assert repo.obtener_por_id(ajena.id) is not None


def test_eliminar_una_pista_inexistente_falla(repo: RepositorioPistas) -> None:
    with pytest.raises(KeyError):
        repo.eliminar(9999)


# --- Contrato -----------------------------------------------------------------------


def test_el_repositorio_real_y_el_falso_siguen_teniendo_el_mismo_contrato() -> None:
    """Si divergieran, los tests unitarios de R4 y R5 con el falso no probarían nada."""
    import inspect as inspeccion

    from app.repositories.pistas import PistasRepo
    from tests.fakes import RepositorioPistasFalso

    falso = RepositorioPistasFalso()

    for operacion in PistasRepo.__protocol_attrs__:  # type: ignore[attr-defined]
        assert hasattr(falso, operacion), f"al falso le falta {operacion}"
        del_protocolo = [
            p for p in inspeccion.signature(getattr(PistasRepo, operacion)).parameters
            if p != "self"
        ]
        del_falso = list(inspeccion.signature(getattr(falso, operacion)).parameters)
        assert del_falso == del_protocolo, operacion
