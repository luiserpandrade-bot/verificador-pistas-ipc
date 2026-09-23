# Phase 1 — Data Model: Verificador de pistas de PCB según IPC-2221

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-22

Las entidades son exactamente las dos que declara la spec en Key Entities. No se
añaden atributos, entidades ni estados que la spec no nombre (ver `research.md`
R-011).

---

## Usuario

Tabla `usuarios`, modelo `app/models/usuario.py`.

| Campo | Tipo | Restricciones | Origen |
|-------|------|---------------|--------|
| `id` | Integer | PK, autoincremental | Identificador técnico |
| `email` | String | NOT NULL, UNIQUE, indexado | Entidad Usuario, FR-001 |
| `hashed_password` | String | NOT NULL | Entidad Usuario, Artículo IV.1 |

**Reglas de validación**:

- El email es único: un segundo registro con el mismo email se rechaza con 400
  (FR-001).
- El email se valida en el schema de entrada con `EmailStr` (Artículo IV.6).
- La contraseña se almacena solo como hash bcrypt vía `passlib[bcrypt]`. Nunca se
  guarda en texto plano, nunca se loguea y nunca aparece en una respuesta:
  `UsuarioOut` no incluye `hashed_password` (Artículo IV.1, FR-002).

**Relaciones**: un Usuario tiene muchas Pistas.

---

## Pista

Tabla `pistas`, modelo `app/models/pista.py`.

| Campo | Tipo | Restricciones | Origen |
|-------|------|---------------|--------|
| `id` | Integer | PK, autoincremental | Identificador técnico |
| `usuario_id` | Integer | NOT NULL, FK → `usuarios.id`, indexado | Entidad Pista, Artículo III.3 |
| `nombre_red` | String | NOT NULL | Entidad Pista |
| `proyecto` | String | NOT NULL, texto libre | Entidad Pista |
| `corriente_a` | Float | NOT NULL · rango `> 0` y `<= 35`: **regla de negocio, validada en `services/` → 400** | Entidad Pista, R2 |
| `espesor_oz` | Float | NOT NULL · rango `>= 0.5` y `<= 3`: **regla de negocio, validada en `services/` → 400** | Entidad Pista, R2 |
| `capa` | String (Enum `Capa`) | NOT NULL, `externa` \| `interna`: **validación de schema → 422** | Entidad Pista, R3 |
| `delta_t_c` | Float | NOT NULL · rango `>= 10` y `<= 100`: **regla de negocio, validada en `services/` → 400** | Entidad Pista, R2 |
| `ancho_mm` | Float | NOT NULL, `> 0`: **validación de schema → 422** | Entidad Pista, FR-017 |

**Capa de validación de cada restricción (no intercambiables)**:

- Los **rangos de R2** (`corriente_a`, `espesor_oz`, `delta_t_c`) son regla de
  negocio y se validan en `app/services/pistas.py`, devolviendo `400`
  (`FueraDeRangoError`). **No deben duplicarse como `gt`/`le`/`ge` en los schemas
  Pydantic**: si el schema los rechazara primero, el caso de error 2 de la spec
  pasaría de `400` a `422` y el contrato REST quedaría incumplido.
- `ancho_mm > 0` sí es **validación de schema** (`422`): un ancho nulo o negativo
  es un dato inválido, no una pista fuera de norma IPC-2221. Nunca debe llegar al
  cálculo ni producir `400`.
- `capa` es validación de schema (`422`) mediante el `Enum`, tal como exige el caso
  de error 3.

**Reglas de validación** (todas verificadas antes de persistir):

- **R1 — Ancho suficiente**: se acepta si
  `ancho_mm >= ancho_minimo_mm(...) - TOLERANCIA_MM`, con `TOLERANCIA_MM = 0.001`.
  Un ancho exactamente igual al mínimo se acepta. Si no se cumple → 400
  (`AnchoInsuficienteError`).
- **R2 — Rango de validez**: `corriente_a` en `(0, 35]`, `delta_t_c` en
  `[10, 100]`, `espesor_oz` en `[0.5, 3]`. Los extremos son válidos. Fuera de
  rango → 400 (`FueraDeRangoError`), nunca una advertencia. Este límite es de
  negocio, no de schema: la spec exige 400 para el caso de error 2, así que el
  schema no lo duplica como 422.
- **R3 — Capa**: solo `externa` (k = 0.048) o `interna` (k = 0.024). Cualquier otro
  valor es error de schema → 422 (caso de error 3), resuelto por el `Enum` de
  Pydantic.
- **R4 — Aislamiento**: `usuario_id` se toma siempre del JWT decodificado y nunca
  de la ruta, el body o un query param (Artículo IV.4). Toda consulta al
  repositorio de pistas filtra por `usuario_id` (Artículo III.3).
- **R5 — Revalidación al modificar**: la actualización aplica los campos recibidos
  sobre los valores actuales y revalida R1, R2 y R3 sobre el resultado. Si falla,
  la actualización completa se rechaza con 400 y la fila conserva sus valores
  anteriores.

**Relaciones**: cada Pista pertenece a exactamente un Usuario, por `usuario_id`.

---

## Enumeración `Capa`

Definida una sola vez y compartida por schemas y modelo:

| Valor | `k` |
|-------|-----|
| `externa` | 0.048 |
| `interna` | 0.024 |

El mapa `K_POR_CAPA: dict[Capa, float]` vive en `app/utils/ipc2221.py` junto al
resto de las constantes de la norma (Artículo VIII.3). Añadir una capa futura es
añadir una entrada al `Enum` y al mapa, sin reescribir ningún `if` existente
(Artículo II.2).

---

## Transiciones de estado

No hay máquina de estados. Una Pista existe o no existe: se crea si pasa R1, R2 y
R3; se actualiza solo si el resultado sigue pasándolas; se elimina de forma
definitiva. No existe un estado "no conforme" almacenado (R5, `research.md` R-011).

---

## Esquemas Pydantic (entrada y salida separados, Artículo V.3)

| Schema | Uso | Campos |
|--------|-----|--------|
| `UsuarioCreate` | entrada de `POST /auth/registro` | `email`, `password` |
| `UsuarioOut` | salida de `POST /auth/registro` | `id`, `email` |
| `Token` | salida de `POST /auth/token` | `access_token`, `token_type` |
| `PistaCreate` | entrada de `POST /pistas/` | `nombre_red`, `proyecto`, `corriente_a`, `espesor_oz`, `capa`, `delta_t_c`, `ancho_mm` |
| `PistaUpdate` | entrada de `PATCH /pistas/{id}` | los mismos campos, todos opcionales |
| `PistaOut` | salida de las rutas de pistas | `id`, `nombre_red`, `proyecto`, `corriente_a`, `espesor_oz`, `capa`, `delta_t_c`, `ancho_mm` |
| `CalculoIn` | entrada de `POST /pistas/calculo` | `corriente_a`, `espesor_oz`, `capa`, `delta_t_c` |
| `CalculoOut` | salida de `POST /pistas/calculo` | `ancho_minimo_mm` (3 decimales) |
| `PaginacionParams` | query de `GET /pistas/` | `skip >= 0` (def. 0), `1 <= limit <= 100` (def. 20) |

`PistaOut` no expone `usuario_id`: el propietario ya está implícito en la
identidad autenticada, y exponerlo invitaría a usarlo como entrada, que es
justo lo que prohíbe el Artículo IV.4.

---

## Migración Alembic

Una única migración inicial crea `usuarios` y `pistas` con sus índices
(`usuarios.email` único, `pistas.usuario_id`) y la FK. Sin SQL crudo concatenado
(Artículo III.1). El engine aplica `connect_args` condicional solo para SQLite, de
modo que la misma migración funcione contra Postgres (Artículo III.2).
