# Quickstart — Validación del verificador de pistas IPC-2221

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-22

Guía de validación: cómo preparar el entorno y comprobar que la funcionalidad
cumple lo que la spec promete. No contiene código de implementación; los detalles
de forma están en [data-model.md](./data-model.md) y los contratos en
[contracts/](./contracts/).

---

## Prerrequisitos

- Python 3.12 y `uv` instalados.
- Un archivo `.env` creado a partir de `.env.example`, con `SECRET_KEY` generada de
  forma criptográficamente segura (`openssl rand -hex 32` o equivalente) y
  `DATABASE_URL` apuntando al SQLite de desarrollo. `.env` no se versiona
  (Artículo IV.3).

## Preparación

```bash
uv sync                  # instala dependencias declaradas en pyproject.toml
uv run alembic upgrade head   # crea las tablas usuarios y pistas
```

## Arrancar el servicio

```bash
uv run uvicorn app.main:app --reload
```

La documentación interactiva queda en `/docs`. El servidor MCP se monta sobre la
misma app ASGI; para el transporte `stdio` se ejecuta el entry point de
`app/mcp/server.py`.

---

## Escenario 1 — Una pista que cumple la norma (User Story 1, R1)

1. Registrar un usuario en `POST /auth/registro` y obtener un token en
   `POST /auth/token`.
2. Consultar `POST /pistas/calculo` con `corriente_a=1`, `delta_t_c=10`,
   `espesor_oz=1`, `capa=externa`.
   **Esperado**: `ancho_minimo_mm = 0.300`.
3. Registrar en `POST /pistas/` una pista con esos parámetros y `ancho_mm=0.5`.
   **Esperado**: `201` con la pista creada.

## Escenario 2 — Una pista que no cumple (caso de error 1)

Registrar la misma pista con `ancho_mm=0.2`.
**Esperado**: `400` con el detalle de ancho insuficiente, y la pista no aparece en
`GET /pistas/`.

## Escenario 3 — Igualdad y tolerancia (R1, decisión R-010)

1. Registrar con `ancho_mm=0.300` (exactamente el mínimo redondeado).
   **Esperado**: `201` — la igualdad se acepta, sin margen de seguridad adicional.
2. Registrar con `ancho_mm=0.2995` (0.0009 mm por debajo del mínimo).
   **Esperado**: `201` — cae dentro de la tolerancia de 0.001 mm.
3. Registrar con `ancho_mm=0.298`.
   **Esperado**: `400` — fuera de la tolerancia.

## Escenario 4 — Rango de validez (R2, caso de error 2)

1. `corriente_a=35`, `delta_t_c=100`, `espesor_oz=3`, `capa=externa`, ancho
   suficiente (el mínimo es 3.337 mm).
   **Esperado**: `201` — los extremos del rango son válidos.
2. `corriente_a=36` con el resto válido.
   **Esperado**: `400` fuera de rango, nunca `201` con advertencia.
3. `delta_t_c=5` y, por separado, `espesor_oz=4`.
   **Esperado**: `400` en ambos.

## Escenario 5 — Capa inválida (R3, caso de error 3)

Registrar con `capa="superficial"`.
**Esperado**: `422` de validación de schema.

## Escenario 6 — Consulta previa por capa (User Story 2, caso de error 7)

Llamar a `POST /pistas/calculo` dos veces con `corriente_a=1`, `delta_t_c=10`,
`espesor_oz=1`, cambiando solo la capa.
**Esperado**: `interna` → `0.781`; `externa` → `0.300`. La interna exige más ancho.

## Escenario 7 — Aislamiento entre usuarios (R4, casos de error 4, 5 y 6)

1. Llamar a `GET /pistas/` sin token. **Esperado**: `401`.
2. Con el token del usuario A, pedir `GET /pistas/{id}` de una pista del usuario B.
   **Esperado**: `403`.
3. Repetir con `PATCH` y `DELETE` sobre esa pista ajena. **Esperado**: `403` y la
   pista de B intacta.
4. Operar sobre un `id` inexistente. **Esperado**: `404`.
5. `GET /pistas/` con el token de A. **Esperado**: solo pistas de A; nunca `403`.

## Escenario 8 — Revalidación al modificar (R5)

1. Partir de una pista válida con `ancho_mm=0.5` para 1 A.
2. `PATCH` subiendo `corriente_a` a un valor cuyo mínimo supere 0.5 mm.
   **Esperado**: `400`, y un `GET` posterior muestra la pista con sus valores
   anteriores intactos. No existe estado "no conforme".

## Escenario 9 — Paridad MCP (User Story 1 y 2 por MCP, SC-004)

Con el servidor MCP en marcha (MCP Inspector o cliente equivalente):

1. `calcular_ancho_minimo(1, 1, "externa", 10)` → `0.300`, igual que por REST.
2. `registrar_pista(...)` con ancho insuficiente → `{"error": ...}`, mismo veredicto
   que `POST /pistas/` (no una excepción que rompa la sesión).
3. `listar_pistas()` → solo las pistas del usuario de la sesión.
4. `eliminar_pista(id)` sin `confirmar` → no borra y pide confirmación explícita;
   repetido con `confirmar=True` → borra.

---

## Suite de pruebas y cobertura

```bash
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check .
```

**Esperado** (Artículo VII.3): cada una de R1–R5 con al menos un test unitario
propio; cobertura de líneas de `app/services/` ≥ 90%; cobertura global ≥ 70% con la
lista `omit` declarada en `[tool.coverage.run]` de `pyproject.toml` (arranque de la
app, servidor MCP y configuración de logging). Los tests unitarios de services usan
el repositorio falso de `tests/fakes.py` inyectado por parámetro, sin
`unittest.mock` (Artículo VII.2); los de API usan `app.dependency_overrides`
(Artículo VII.5).
