"""Configuración de la aplicación leída del entorno con pydantic-settings.

Artículo IV.3: `SECRET_KEY` y `DATABASE_URL` viven solo en `.env` (nunca versionado)
o en el entorno del proceso; este módulo es el único punto que las lee. `.env.example`
documenta las variables sin valores reales.
Artículo IV.2: `ACCESS_TOKEN_EXPIRE_MINUTES` es configurable y nunca infinito, así que
se valida como entero positivo.

Si falta una variable obligatoria, la app falla al arrancar con un error explícito en
vez de asumir un valor por defecto inseguro.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """Variables de entorno de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    secret_key: str = Field(min_length=1, description="Clave de firma de los JWT (HS256)")
    database_url: str = Field(min_length=1, description="Cadena de conexión de la base de datos")
    access_token_expire_minutes: int = Field(
        default=30,
        gt=0,
        description="Minutos de validez del token. Nunca infinito (Artículo IV.2).",
    )


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Devuelve la configuración, cacheada para no releer el entorno en cada petición."""
    return Configuracion()  # type: ignore[call-arg]
