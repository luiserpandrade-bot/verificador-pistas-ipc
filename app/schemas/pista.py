"""Schemas de entrada y salida de pista.

Artículo V.3: entrada y salida son schemas distintos y nunca se expone el modelo de
SQLAlchemy. `PistaOut` tampoco expone `usuario_id`: el propietario ya está implícito en
la identidad autenticada, y publicarlo invitaría a usarlo como entrada, que es justo lo
que prohíbe el Artículo IV.4.

Artículo IV.6: toda entrada se valida aquí antes de llegar a `services/`.

**Capa de validación** (ver `data-model.md`, "Capa de validación de cada restricción"):

- `capa` distinta de `externa`/`interna` → 422, resuelto por el `Enum` (caso de error 3).
- `ancho_mm > 0` → 422. Un ancho nulo o negativo es un dato inválido, no una pista fuera
  de norma IPC-2221, así que no debe llegar al cálculo ni producir 400.
- Los **rangos de R2** (`corriente_a` ≤ 35 A, `delta_t_c` 10–100 °C, `espesor_oz`
  0.5–3 oz) **NO se replican aquí** como `gt`/`le`/`ge`. Son regla de negocio y los
  comprueba `app/services/pistas.py` devolviendo 400: si el schema los rechazara primero,
  el caso de error 2 de la spec pasaría de 400 a 422.

Se validan solo como número finito y positivo lo estrictamente necesario para que el
cálculo esté definido; el resto es decisión del service.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.utils.ipc2221 import Capa


class PistaCreate(BaseModel):
    """Cuerpo de `POST /pistas/`."""

    nombre_red: str = Field(min_length=1, max_length=120)
    proyecto: str = Field(min_length=1, max_length=120)
    corriente_a: float = Field(
        gt=0, description="Corriente en amperios. El tope de R2 lo aplica el service."
    )
    espesor_oz: float = Field(
        gt=0, description="Espesor de cobre en onzas. El rango de R2 lo aplica el service."
    )
    capa: Capa
    delta_t_c: float = Field(
        gt=0, description="Elevación de temperatura en °C. El rango de R2 lo aplica el service."
    )
    ancho_mm: float = Field(
        gt=0, description="Ancho diseñado en milímetros. Nulo o negativo es 422."
    )


class PistaOut(BaseModel):
    """Pista tal como se devuelve al cliente. Sin `usuario_id` y sin campos derivados."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_red: str
    proyecto: str
    corriente_a: float
    espesor_oz: float
    capa: Capa
    delta_t_c: float
    ancho_mm: float


class CalculoIn(BaseModel):
    """Cuerpo de `POST /pistas/calculo`. No incluye ancho: es lo que se quiere averiguar."""

    corriente_a: float = Field(
        gt=0, description="Corriente en amperios. El tope de R2 lo aplica el service."
    )
    espesor_oz: float = Field(
        gt=0, description="Espesor de cobre en onzas. El rango de R2 lo aplica el service."
    )
    capa: Capa
    delta_t_c: float = Field(
        gt=0, description="Elevación de temperatura en °C. El rango de R2 lo aplica el service."
    )


class CalculoOut(BaseModel):
    """Respuesta de `POST /pistas/calculo`: solo el ancho mínimo, en milímetros."""

    ancho_minimo_mm: float = Field(
        description="Ancho mínimo que exige IPC-2221, en milímetros y con 3 decimales."
    )


class PistaUpdate(BaseModel):
    """Cuerpo de `PATCH /pistas/{id}`: todos los campos son opcionales.

    Los campos ausentes conservan su valor actual. La revalidación de R1, R2 y R3 sobre el
    resultado de la fusión la hace el service (R5), no este schema.
    """

    model_config = ConfigDict(extra="forbid")

    nombre_red: str | None = Field(default=None, min_length=1, max_length=120)
    proyecto: str | None = Field(default=None, min_length=1, max_length=120)
    corriente_a: float | None = Field(default=None, gt=0)
    espesor_oz: float | None = Field(default=None, gt=0)
    capa: Capa | None = None
    delta_t_c: float | None = Field(default=None, gt=0)
    ancho_mm: float | None = Field(default=None, gt=0)

    def cambios(self) -> dict[str, object]:
        """Campos efectivamente enviados, con la capa ya como texto de la norma."""
        enviados = self.model_dump(exclude_unset=True, exclude_none=True)
        if "capa" in enviados and self.capa is not None:
            enviados["capa"] = self.capa.value
        return enviados


class PaginacionParams(BaseModel):
    """Query params de `GET /pistas/` (Artículo V.2, decisión R-005).

    Valores por defecto razonables y un tope superior, para que un listado no degenere en
    una descarga completa. Un valor inválido es error de schema (422), no de negocio.
    """

    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
