# Contract — API REST

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md) | **Date**: 2026-09-22

Los 8 endpoints son exactamente los de la tabla de contrato de la spec. No se
añade ninguna ruta. Los códigos siguen el Artículo V.1 de la constitución, con
`403` reservado a un recurso existente que pertenece a otro usuario e identificado
por `id` en la ruta; `GET /pistas/` nunca devuelve `403`, solo filtra (R4).

Formas de datos en [data-model.md](../data-model.md).

---

## POST /auth/registro

- **Auth**: no
- **Body**: `UsuarioCreate` → `email`, `password`
- **200/201**: `201` con `UsuarioOut` (`id`, `email`). Nunca devuelve el hash ni la
  contraseña (Artículo IV.1, FR-002)
- **Errores**: `400` email ya registrado · `422` schema inválido
- **Service**: `services.auth.registrar_usuario()`

## POST /auth/token

- **Auth**: no. OAuth2 password flow (Artículo IV.2)
- **Body**: `email`, `password` (formulario OAuth2)
- **200**: `Token` → `access_token` (JWT HS256, expiración finita según
  `ACCESS_TOKEN_EXPIRE_MINUTES`), `token_type`
- **Errores**: `401` credenciales inválidas · `422` schema inválido
- **Service**: `services.auth.autenticar_usuario()`

## POST /pistas/

- **Auth**: sí. El propietario se deriva del JWT (Artículo IV.4, R4)
- **Body**: `PistaCreate` → `nombre_red`, `proyecto`, `corriente_a`, `espesor_oz`,
  `capa`, `delta_t_c`, `ancho_mm`
- **201**: `PistaOut`
- **Errores**: `400` ancho insuficiente (R1) · `400` fuera de rango (R2) · `401`
  sin token · `422` schema inválido, incluida una `capa` distinta de
  `externa`/`interna` (R3)
- **Service**: `services.pistas.registrar_pista()` — la misma función que usa la
  tool MCP `registrar_pista` (Artículo VI.1)

## GET /pistas/

- **Auth**: sí
- **Query**: `skip` (def. 0, `>= 0`), `limit` (def. 20, `1..100`) — decisión R-005
- **200**: lista de `PistaOut`, solo del usuario autenticado
- **Errores**: `401` sin token · `422` paginación inválida
- **Nunca** `403`: filtra por el `usuario_id` del JWT y no acepta el de otro
  usuario (Artículo V.1, R4)
- **Service**: `services.pistas.listar_pistas()`

## GET /pistas/{id}

- **Auth**: sí
- **200**: `PistaOut`
- **Errores**: `401` sin token · `403` la pista existe pero es de otro usuario ·
  `404` no existe
- **Service**: `services.pistas.obtener_pista()` — verifica pertenencia antes de
  devolver nada (Artículo IV.4)

## PATCH /pistas/{id}

- **Auth**: sí
- **Body**: `PistaUpdate` (todos los campos opcionales)
- **200**: `PistaOut` con los valores ya actualizados
- **Errores**: `400` ancho insuficiente o fuera de rango tras revalidar R1, R2 y
  R3 sobre el resultado (R5) · `401` · `403` pista de otro usuario · `404` no
  existe · `422` schema inválido
- **Semántica de fallo**: la actualización se rechaza completa y la pista conserva
  sus valores anteriores; no se guarda marcada como no conforme (R5)
- **Service**: `services.pistas.actualizar_pista()`

## DELETE /pistas/{id}

- **Auth**: sí
- **204**: sin cuerpo
- **Errores**: `401` · `403` pista de otro usuario · `404` no existe
- **Service**: `services.pistas.eliminar_pista()`

## POST /pistas/calculo

- **Auth**: sí
- **Body**: `CalculoIn` → `corriente_a`, `espesor_oz`, `capa`, `delta_t_c`
- **200**: `CalculoOut` → `ancho_minimo_mm`, en milímetros y redondeado a 3
  decimales (FR-017, decisión R-010)
- **No persiste nada**
- **Errores**: `400` fuera de rango (R2) · `401` · `422` schema inválido
- **Service**: `services.pistas.calcular_ancho_minimo()` — la misma función que usa
  la tool MCP `calcular_ancho_minimo`

---

## Errores no controlados

Cualquier excepción no prevista se traduce a `500` con
`{"detail": "Error interno del servidor"}`. Nunca se devuelve un stack trace ni el
mensaje original; el detalle se loguea internamente (Artículo IV.5).

## Trazabilidad de errores de negocio

| Excepción de dominio | REST | Regla |
|----------------------|------|-------|
| `AnchoInsuficienteError` | `400` | R1 |
| `FueraDeRangoError` | `400` | R2 |
| `PistaAjenaError` | `403` | R4 |
| `PistaNoEncontradaError` | `404` | — |

Las excepciones se definen sin dependencias de FastAPI, para que la misma
excepción sirva a los routers y a las tools MCP (decisión R-009).
