"""Verifica la carga de configuración desde el entorno (Artículos IV.2 y IV.3)."""

import pytest
from pydantic import ValidationError

from app.config import Configuracion, obtener_configuracion

VARIABLES = ("SECRET_KEY", "DATABASE_URL", "ACCESS_TOKEN_EXPIRE_MINUTES")


@pytest.fixture
def entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla el test del `.env` del repositorio y de variables ya presentes."""
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    return None


def _configuracion_sin_env_file(**variables: str) -> Configuracion:
    """Construye la configuración ignorando el archivo `.env` del repositorio."""
    return Configuracion(_env_file=None, **variables)  # type: ignore[call-arg]


def test_carga_las_tres_variables(entorno_limpio: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave-de-prueba")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prueba.db")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "45")

    configuracion = Configuracion(_env_file=None)  # type: ignore[call-arg]

    assert configuracion.secret_key == "clave-de-prueba"
    assert configuracion.database_url == "sqlite:///./prueba.db"
    assert configuracion.access_token_expire_minutes == 45


def test_expiracion_tiene_valor_por_defecto_finito(
    entorno_limpio: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prueba.db")

    configuracion = Configuracion(_env_file=None)  # type: ignore[call-arg]

    assert configuracion.access_token_expire_minutes == 30


def test_falta_secret_key_falla_con_error_explicito(entorno_limpio: None) -> None:
    with pytest.raises(ValidationError) as error:
        _configuracion_sin_env_file(database_url="sqlite:///./prueba.db")

    assert "secret_key" in str(error.value).lower()


def test_falta_database_url_falla_con_error_explicito(entorno_limpio: None) -> None:
    with pytest.raises(ValidationError) as error:
        _configuracion_sin_env_file(secret_key="clave")

    assert "database_url" in str(error.value).lower()


def test_secret_key_vacia_se_rechaza(entorno_limpio: None) -> None:
    with pytest.raises(ValidationError):
        _configuracion_sin_env_file(secret_key="", database_url="sqlite:///./prueba.db")


@pytest.mark.parametrize("minutos", [0, -1, -30])
def test_expiracion_no_positiva_se_rechaza(entorno_limpio: None, minutos: int) -> None:
    """Artículo IV.2: la expiración nunca puede ser cero ni negativa."""
    with pytest.raises(ValidationError):
        _configuracion_sin_env_file(
            secret_key="clave",
            database_url="sqlite:///./prueba.db",
            access_token_expire_minutes=minutos,
        )


def test_obtener_configuracion_esta_cacheada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "clave")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prueba.db")
    obtener_configuracion.cache_clear()

    primera = obtener_configuracion()
    segunda = obtener_configuracion()

    assert primera is segunda
    obtener_configuracion.cache_clear()
