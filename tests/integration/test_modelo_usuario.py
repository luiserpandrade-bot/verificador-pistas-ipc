"""Integración del modelo Usuario contra SQLite en memoria (Artículo VII.4)."""

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, crear_engine
from app.models.usuario import Usuario


@pytest.fixture
def sesion() -> Session:
    engine = crear_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, autoflush=False, future=True)
    with fabrica() as sesion:
        yield sesion
    engine.dispose()


def test_la_tabla_usuarios_se_crea_con_sus_columnas(sesion: Session) -> None:
    inspector = inspect(sesion.get_bind())

    assert "usuarios" in inspector.get_table_names()
    columnas = {c["name"]: c for c in inspector.get_columns("usuarios")}
    assert set(columnas) == {"id", "email", "hashed_password"}
    assert columnas["email"]["nullable"] is False
    assert columnas["hashed_password"]["nullable"] is False


def test_email_tiene_indice_unico(sesion: Session) -> None:
    indices = inspect(sesion.get_bind()).get_indexes("usuarios")

    indice_email = next(i for i in indices if i["column_names"] == ["email"])
    # SQLite devuelve 1 en vez de True, así que se compara por verdad, no por identidad.
    assert bool(indice_email["unique"]) is True


def test_guarda_y_recupera_un_usuario(sesion: Session) -> None:
    sesion.add(Usuario(email="disenador@example.com", hashed_password="$2b$12$hash"))
    sesion.commit()

    recuperado = sesion.query(Usuario).filter_by(email="disenador@example.com").one()

    assert recuperado.id is not None
    assert recuperado.hashed_password == "$2b$12$hash"


def test_email_duplicado_viola_la_restriccion_unica(sesion: Session) -> None:
    sesion.add(Usuario(email="repetido@example.com", hashed_password="$2b$12$a"))
    sesion.commit()

    sesion.add(Usuario(email="repetido@example.com", hashed_password="$2b$12$b"))
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_el_modelo_no_tiene_columna_de_contrasena_en_claro() -> None:
    """Artículo IV.1: solo existe el hash; no hay sitio donde guardar el texto plano."""
    columnas = {columna.name for columna in Usuario.__table__.columns}

    assert "password" not in columnas
    assert "contrasena" not in columnas
    assert "hashed_password" in columnas
