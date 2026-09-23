"""Excepciones de dominio, sin ninguna dependencia del framework web.

Decisión R-009: los services lanzan estas excepciones; los routers las traducen a
códigos HTTP (Artículo V.1) y las tools MCP a `{"error": ...}` (Artículo VI.3). Si el
service lanzara `HTTPException`, la tool MCP recibiría un error HTTP que no sabe
interpretar y el Artículo I.2 quedaría roto.

Traducción de cada excepción, fijada en `contracts/rest-api.md`:

===============================  ====  =============================
Excepción                        REST  MCP
===============================  ====  =============================
`EmailYaRegistradoError`         400   —
`CredencialesInvalidasError`     401   —
`AnchoInsuficienteError` (R1)    400   `{"error": ...}`
`FueraDeRangoError` (R2)         400   `{"error": ...}`
`PistaAjenaError` (R4)           403   `{"error": ...}`
`PistaNoEncontradaError`         404   `{"error": ...}`
===============================  ====  =============================
"""


class ErrorDeNegocio(Exception):
    """Raíz de los errores de negocio previstos por la especificación."""


class EmailYaRegistradoError(ErrorDeNegocio):
    """Ya existe un usuario con ese email (FR-001, 400)."""


class CredencialesInvalidasError(ErrorDeNegocio):
    """El email no existe o la contraseña no coincide (FR-003, 401)."""


class AnchoInsuficienteError(ErrorDeNegocio):
    """El ancho diseñado no alcanza el mínimo que exige IPC-2221 (R1, 400)."""


class FueraDeRangoError(ErrorDeNegocio):
    """Algún parámetro cae fuera del rango de validez del modelo (R2, 400).

    Es un error de negocio y no de schema: la especificación exige 400 para el caso de
    error 2, así que los rangos no se replican como validación Pydantic.
    """


class PistaNoEncontradaError(ErrorDeNegocio):
    """No existe ninguna pista con ese identificador (404)."""


class PistaAjenaError(ErrorDeNegocio):
    """La pista existe pero pertenece a otro usuario (R4, 403).

    Se distingue de `PistaNoEncontradaError` porque el Artículo V.1 reserva el 403 a este
    caso exacto: recurso existente, identificado por `id` explícito, de otro dueño.
    """
