# Mapeo de reglas de negocio a tests

Este documento existe por el **Artículo VII.3** de la constitución, que exige cobertura de
*reglas* y no solo de líneas: el 100 % de las reglas de negocio explícitas de `spec.md`
debe estar cubierto por al menos un test unitario cada una.

El mapeo se comprueba de forma automática en `tests/test_cobertura_de_reglas.py`. Si una
regla o un caso de error pierde su test en un refactor, esa auditoría falla.

## Pirámide de pruebas (Artículo VII.1)

| Nivel | Directorio | Qué prueba |
|-------|------------|------------|
| Unitarias (mayoría) | `tests/unit/` | Cálculo IPC-2221, reglas de negocio con repositorio falso, schemas, seguridad, configuración |
| Integración | `tests/integration/` | Modelos, repositorios y migraciones contra SQLite real en memoria |
| API | `tests/api/` | Endpoints con `dependency_overrides`, sin servidor real |
| MCP | `tests/mcp/` | Las cuatro tools y la resolución de identidad |

## Reglas de negocio

| Regla | Qué exige | Tests |
|-------|-----------|-------|
| **R1 — Ancho suficiente** | `ancho_mm >= minimo_mm - TOLERANCIA_MM`; la igualdad se acepta, sin margen adicional | `tests/unit/test_services_pistas.py::test_r1_*` (ancho holgado, igualdad exacta, mínimo redondeado, dentro de tolerancia, borde exacto, fuera de tolerancia sin persistir, interna vs externa, mensaje de error, más corriente) |
| **R2 — Rango de validez** | corriente en `(0, 35]` A, ΔT en `[10, 100]` °C, espesor en `[0.5, 3]` oz; fuera de rango se rechaza con 400, nunca con advertencia | `tests/unit/test_services_pistas.py::test_r2_*` (seis extremos válidos, once valores justo por fuera, orden R2 antes de R1, mensaje, límites importados de `utils/`) |
| **R3 — Constante según la capa** | `k` = 0.048 externa / 0.024 interna; cualquier otra capa es inválida | `tests/unit/test_services_pistas.py::test_r3_*` (k por capa verificada por su efecto, ningún condicional por capa, capa no contemplada detenida en el schema, toda capa declarada tiene su `k`) |
| **R4 — Aislamiento por usuario** | solo se leen, modifican o eliminan pistas propias, sin importar el identificador recibido | `tests/unit/test_services_pistas.py::test_r4_*` y `test_eliminar_una_pista_ajena_no_borra_nada`; `tests/api/test_pistas_crud.py` (403 en GET/PATCH/DELETE); `tests/integration/test_repositorio_pistas_crud.py` (el filtro está en la consulta) |
| **R5 — Revalidación al modificar** | al actualizar se revalidan R1, R2 y R3 sobre el resultado; si falla, se rechaza la actualización completa con 400 y la pista conserva sus valores anteriores | `tests/unit/test_services_pistas.py::test_r5_*` (actualización válida, ancho insuficiente, cero escrituras al rechazar, valores intactos, rango R2, capa resultante, PATCH vacío, pista ajena, inexistente, reutilización de validaciones) |

## Casos de error explícitos de `spec.md`

| # | Caso | Test |
|---|------|------|
| 1 | Ancho menor al mínimo de IPC-2221 → 400 | `tests/api/test_pistas_registro.py::test_caso_de_error_1_ancho_insuficiente_devuelve_400` |
| 2 | Parámetros fuera del rango de validez → 400 | `tests/api/test_pistas_registro.py::test_caso_de_error_2_fuera_de_rango_devuelve_400` |
| 3 | Capa distinta de externa/interna → 422 | `tests/api/test_pistas_registro.py::test_caso_de_error_3_capa_invalida_devuelve_422` |
| 4 | Listar o registrar sin token → 401 | `tests/api/test_pistas_registro.py::test_caso_de_error_4_sin_token_devuelve_401` y `tests/api/test_pistas_crud.py::test_caso_de_error_4_sin_token_todo_devuelve_401` |
| 5 | Leer, modificar o eliminar una pista ajena por ID → 403 | `tests/api/test_pistas_crud.py::test_caso_de_error_5_*` (GET, PATCH, DELETE) y `tests/mcp/test_tools_us3.py::test_una_pista_ajena_no_se_borra_ni_con_confirmar` |
| 6 | Operar sobre una pista inexistente → 404 | `tests/api/test_pistas_crud.py::test_caso_de_error_6_*` |
| 7 | `calcular_ancho_minimo` con capa interna devuelve más ancho que con externa | `tests/unit/test_services_calculo.py::test_caso_de_error_7_la_interna_exige_mas_que_la_externa`, `tests/mcp/test_tools.py::test_caso_de_error_7_por_mcp` y `tests/api/test_calculo.py::test_la_capa_interna_devuelve_mas_ancho_que_la_externa` |

## Valores de referencia del cálculo (Artículo VII.7)

Calculados a mano y documentados en `tests/unit/test_ipc2221.py`, con tolerancia declarada
de ±0.001 mm:

| Corriente | ΔT | Espesor | Capa | Ancho |
|-----------|-----|---------|------|-------|
| 1 A | 10 °C | 1 oz | externa | 0.300 mm |
| 1 A | 10 °C | 1 oz | interna | 0.781 mm |
| 5 A | 20 °C | 1 oz | externa | 1.816 mm |
| 35 A | 100 °C | 3 oz | externa | 3.337 mm |

El primero coincide con el valor que cita la propia constitución (≈ 0,30 mm).

## Reglas de las pruebas

- Los tests unitarios de `services/` inyectan el repositorio falso de `tests/fakes.py` por
  parámetro. **`unittest.mock` está prohibido** para eso (Artículo VII.2) y hay una
  auditoría que lo verifica en toda la suite.
- Los tests de integración corren contra SQLite real en memoria, nunca contra el falso
  (Artículo VII.4).
- Los tests de API usan `app.dependency_overrides` y no levantan un servidor real
  (Artículo VII.5).
- Cada tool de MCP tiene al menos un caso exitoso y uno de error de negocio
  (Artículo VII.6).
