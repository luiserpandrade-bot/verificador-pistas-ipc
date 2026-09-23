"""Schemas de entrada y salida de usuario.

Artículo V.3: los schemas de entrada y salida son distintos y nunca se expone el modelo
de SQLAlchemy. `UsuarioOut` no incluye `hashed_password`, así que la contraseña no
puede filtrarse por una respuesta ni por descuido (Artículo IV.1, FR-002).
Artículo IV.6: toda entrada de usuario se valida aquí, antes de llegar a `services/`.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UsuarioCreate(BaseModel):
    """Cuerpo de `POST /auth/registro`."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UsuarioOut(BaseModel):
    """Usuario tal como se devuelve al cliente. Sin hash y sin contraseña."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class Token(BaseModel):
    """Respuesta de `POST /auth/token` (OAuth2 password flow)."""

    access_token: str
    token_type: str = "bearer"
