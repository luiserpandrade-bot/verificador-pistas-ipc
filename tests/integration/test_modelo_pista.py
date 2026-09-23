"""Integración del modelo Pista contra SQLite en memoria (Artículo VII.4)."""

import pytest
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, crear_engine
from app.models.pista import Pista
from app.models.usuario import Usuario


@pytest.fixture
def sesion() -> Session:
    engine = crear_engine("sqlite+pysqlite:///:memory:")

    # SQLite no aplica claves ajenas si no se activan por conexión.
    @event.listens_for(engine, "connect")
    def _activar_fk(conexion, _registro) -> None:  # noqa: ANN001
        conexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, autoflush=False, future=True)
    with fabrica() as sesion:
        yield sesion
    engine.dispose()


def _usuario(sesion: Session, email: str = "disenador@example.com") -> Usuario:
    usuario = Usuario(email=email, hashed_password="$2b$12$hash")
    sesion.add(usuario)
    sesion.commit()
    return usuario


def _pista(usuario_id: int, **cambios: object) -> Pista:
    datos = {
        "usuario_id": usuario_id,
        "nombre_red": "VBUS",
        "proyecto": "fuente-5v",
        "corriente_a": 1.0,
        "espesor_oz": 1.0,
        "capa": "externa",
        "delta_t_c": 10.0,
        "ancho_mm": 0.5,
    }
    datos.update(cambios)
    return Pista(**datos)  # type: ignore[arg-type]


def test_la_tabla_pistas_tiene_las_columnas_declaradas(sesion: Session) -> None:
    inspector = inspect(sesion.get_bind())

    assert "pistas" in inspector.get_table_names()
    columnas = {c["name"] for c in inspector.get_columns("pistas")}
    assert columnas == {
        "id",
        "usuario_id",
        "nombre_red",
        "proyecto",
        "corriente_a",
        "espesor_oz",
        "capa",
        "delta_t_c",
        "ancho_mm",
    }


def test_no_hay_columnas_derivadas_ni_estado_de_conformidad(sesion: Session) -> None:
    """Decisión R-011: el ancho mínimo no se persiste y no existe estado "no conforme"."""
    columnas = {c.name for c in Pista.__table__.columns}

    assert "ancho_minimo_mm" not in columnas
    assert "conforme" not in columnas
    assert "estado" not in columnas


def test_la_clave_ajena_apunta_a_usuarios(sesion: Session) -> None:
    ajenas = inspect(sesion.get_bind()).get_foreign_keys("pistas")

    assert len(ajenas) == 1
    assert ajenas[0]["referred_table"] == "usuarios"
    assert ajenas[0]["constrained_columns"] == ["usuario_id"]


def test_usuario_id_esta_indexado(sesion: Session) -> None:
    indices = inspect(sesion.get_bind()).get_indexes("pistas")

    assert any(i["column_names"] == ["usuario_id"] for i in indices)


def test_guarda_y_recupera_una_pista(sesion: Session) -> None:
    usuario = _usuario(sesion)
    sesion.add(_pista(usuario.id))
    sesion.commit()

    recuperada = sesion.query(Pista).one()

    assert recuperada.usuario_id == usuario.id
    assert recuperada.usuario.email == "disenador@example.com"
    assert recuperada.capa == "externa"
    assert recuperada.ancho_mm == 0.5


def test_usuario_id_nulo_se_rechaza(sesion: Session) -> None:
    sesion.add(_pista(usuario_id=None))  # type: ignore[arg-type]

    with pytest.raises(IntegrityError):
        sesion.commit()


def test_usuario_inexistente_viola_la_clave_ajena(sesion: Session) -> None:
    sesion.add(_pista(usuario_id=9999))

    with pytest.raises(IntegrityError):
        sesion.commit()


def test_las_pistas_de_un_usuario_son_accesibles_desde_el(sesion: Session) -> None:
    usuario = _usuario(sesion)
    sesion.add(_pista(usuario.id, nombre_red="GND"))
    sesion.add(_pista(usuario.id, nombre_red="VCC"))
    sesion.commit()

    assert {p.nombre_red for p in usuario.pistas} == {"GND", "VCC"}
