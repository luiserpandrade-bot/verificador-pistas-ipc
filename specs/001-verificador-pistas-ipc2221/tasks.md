---

description: "Task list template for feature implementation"
---

# Tasks: Verificador de pistas de PCB según IPC-2221

**Input**: Design documents from `/specs/001-verificador-pistas-ipc2221/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: SÍ se incluyen tareas de test. No son opcionales aquí: el Artículo VII.8 de la constitución exige que ninguna tarea se considere terminada sin su test en verde, así que **cada tarea lleva su propio test dentro de la misma tarea**. Las reglas R1–R5 tienen cada una su test unitario nominado, con repositorio falso inyectado por parámetro y **nunca** `unittest.mock` (Artículo VII.2).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Proyecto único de servicio backend, según la decisión de estructura de `plan.md`: código en `app/`, migraciones en `alembic/`, pruebas en `tests/`. Sin frontend.

## Orden de capas (obligatorio)

Dentro de cada fase, las tareas respetan estrictamente: **models → repositories → services → routers → mcp/tools**. Ninguna tarea mezcla dos capas dependientes; `schemas/` y `utils/` se resuelven antes de la capa que los consume. Una tarea de router nunca contiene reglas de negocio (Artículo I.1) y una tool MCP nunca reimplementa un service (Artículo VI.1).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización del proyecto, dependencias con versiones fijadas y configuración de cobertura

- [X] T001 Crear el árbol de directorios de `app/` (`routers/`, `services/`, `repositories/`, `models/`, `schemas/`, `utils/`, `mcp/tools/`), `alembic/` y `tests/` (`unit/`, `integration/`, `api/`, `mcp/`) con sus `__init__.py`, según la estructura de `plan.md`; verificar con `tests/test_estructura.py` que las siete carpetas de capa existen y son importables
- [X] T002 Crear `pyproject.toml` para uv con Python 3.12 y **versiones exactas fijadas**: `fastapi`, `sqlalchemy>=2,<3`, `alembic`, `pydantic>=2,<3`, `pydantic-settings`, `passlib[bcrypt]==1.7.4`, `bcrypt==4.0.1`, `python-jose`, `fastmcp==4.0.5`, `pytest`, `pytest-cov`, `ruff`, `httpx`, `email-validator`, `uvicorn`; incluir `[tool.coverage.run] omit` con `app/main.py`, `app/mcp/server.py`, `app/mcp/auth.py` y `app/logging_config.py` (Artículo VII.3) y la configuración de `ruff` y `pytest`; verificar con `uv sync` + `uv run pytest --cov=app --collect-only` que el entorno resuelve y que la lista `omit` se aplica
- [X] T003 [P] Crear `.env.example` versionado con `SECRET_KEY`, `DATABASE_URL` y `ACCESS_TOKEN_EXPIRE_MINUTES` documentadas y **sin valores reales**, y añadir `.env` a `.gitignore` (Artículo IV.3); verificar con `tests/test_env_example.py` que `.env.example` existe, nombra las tres variables y que `.env` está ignorado por git
- [X] T004 [P] Crear `app/logging_config.py` con la configuración de logging de la aplicación; verificar con `tests/unit/test_logging_config.py` que la configuración se aplica y que no emite ningún valor de `SECRET_KEY` ni contraseñas

**Nota sobre las versiones fijadas (T002)**: `passlib` 1.7.4 lee `bcrypt.__about__.__version__`, atributo eliminado en `bcrypt` 4.1; por eso el par conocido que funciona es `passlib==1.7.4` + `bcrypt==4.0.1` y no la última de `bcrypt` (5.0.0 a fecha de hoy). El paquete MCP se fija en `fastmcp==4.0.5`, la última publicada al 2026-09-22; si se prefiere el SDK oficial, el equivalente es `mcp==2.2.0`. Las tres versiones se consultaron contra PyPI al generar estas tareas y deben reconfirmarse si el entorno resuelve algo distinto.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cálculo de la norma, persistencia, autenticación y arranque. Nada de esto pertenece a una sola historia

**⚠️ CRITICAL**: Ninguna historia de usuario puede empezar hasta que esta fase esté completa

- [X] T005 [P] Implementar `app/utils/ipc2221.py` como función pura `ancho_minimo_mm(corriente_a, espesor_oz, capa, delta_t_c)` con `I = k · ΔT^0.44 · A^0.725`, el `Enum Capa`, `K_POR_CAPA` (`externa` = 0.048, `interna` = 0.024), los exponentes 0.44 y 0.725, el factor 1.378 oz→mils, el 0.0254 mils→mm y `TOLERANCIA_MM = 0.001`, con docstring que declare el uso de IPC-2221 y no IPC-2152 (Artículos I.4, VIII.1, VIII.2, VIII.3); verificar con `tests/unit/test_ipc2221.py` contra los valores calculados a mano de `research.md` R-002 (1 A/10 °C/1 oz externa = 0.300 mm; interna = 0.781 mm; 5 A/20 °C/1 oz externa = 1.816 mm; 35 A/100 °C/3 oz externa = 3.337 mm) con tolerancia declarada de ±0.001 mm
- [X] T006 [P] Implementar `app/utils/seguridad.py` con hash y verificación bcrypt vía `passlib` y firma/verificación de JWT HS256 con expiración finita (Artículos IV.1, IV.2); verificar con `tests/unit/test_seguridad.py` que el hash nunca es igual a la contraseña, que un token válido se decodifica y que uno expirado o manipulado se rechaza
- [X] T007 Implementar `app/config.py` con `pydantic-settings` leyendo `SECRET_KEY`, `DATABASE_URL` y `ACCESS_TOKEN_EXPIRE_MINUTES` solo desde entorno/`.env` (Artículo IV.3); verificar con `tests/unit/test_config.py` que las variables se cargan y que falta obligatoria produce error explícito al arrancar
- [X] T008 Implementar `app/database.py` con engine y factoría de sesión, aplicando `connect_args={"check_same_thread": False}` **solo** cuando la URL es SQLite (Artículo III.2); verificar con `tests/unit/test_database.py` que `connect_args` se añade con una URL SQLite y no se añade con una URL Postgres
- [X] T009 [P] Implementar el modelo `app/models/usuario.py` (tabla `usuarios`) con `id` PK, `email` `NOT NULL UNIQUE` indexado y `hashed_password` `NOT NULL`, según `data-model.md`; verificar con `tests/integration/test_modelo_usuario.py` contra SQLite en memoria que la tabla se crea y que un email duplicado viola la restricción única
- [X] T010 [P] Implementar el modelo `app/models/pista.py` (tabla `pistas`) con `id` PK, `usuario_id` `NOT NULL` FK → `usuarios.id` indexado (Artículo III.3), `nombre_red` `NOT NULL`, `proyecto` `NOT NULL`, `corriente_a` `NOT NULL`, `espesor_oz` `NOT NULL`, `capa` `NOT NULL` (`externa` | `interna`), `delta_t_c` `NOT NULL` y `ancho_mm` `NOT NULL`, sin columnas derivadas ni estado de conformidad (decisión R-011); verificar con `tests/integration/test_modelo_pista.py` que la tabla y la FK se crean y que `usuario_id` nulo se rechaza
- [X] T011 Configurar Alembic en `alembic/env.py` y crear la migración inicial en `alembic/versions/` que cree `usuarios` y `pistas` con sus índices y la FK, sin SQL crudo concatenado (Artículo III.1); verificar con `tests/integration/test_migraciones.py` que `upgrade head` y `downgrade base` funcionan contra SQLite
- [X] T012 Crear la infraestructura de pruebas en `tests/conftest.py` (sesión SQLite en memoria para integración, cliente de API con `app.dependency_overrides` para `get_db`, `get_pistas_repo`, `get_usuarios_repo` y `get_current_user`) y `tests/fakes.py` con el repositorio falso que cumple el mismo contrato que el real, **sin `unittest.mock`** (Artículos VII.2, VII.4, VII.5); verificar con `tests/unit/test_fakes.py` que el repositorio falso expone exactamente las operaciones del `Protocol` del repositorio real
- [X] T013 [P] Implementar `app/repositories/usuarios.py` como única capa con `Session` para usuarios, con `crear`, `obtener_por_email` y `obtener_por_id` (Artículo I.3); verificar con `tests/integration/test_repositorio_usuarios.py` contra SQLite en memoria
- [X] T014 [P] Implementar `app/repositories/pistas.py` con el `Protocol` del contrato del repositorio y la operación `guardar`, filtrando siempre por `usuario_id` (Artículos I.3, III.3); verificar con `tests/integration/test_repositorio_pistas.py` que una pista se guarda asociada a su `usuario_id`
- [X] T015 Implementar `app/services/auth.py` con `registrar_usuario` y `autenticar_usuario`, recibiendo el repositorio como parámetro con valor por defecto (`repo=usuarios_repo`) y sin importar SQLAlchemy ni `Session` (Artículos I.2, II.3); verificar con `tests/unit/test_services_auth.py` usando el repositorio falso que un email duplicado se rechaza, que una contraseña correcta autentica y que una incorrecta no
- [X] T016 Implementar `app/dependencies.py` con `get_db`, `get_usuarios_repo`, `get_pistas_repo` y `get_current_user`, que deriva el usuario **solo** del JWT decodificado (Artículo IV.4); verificar con `tests/unit/test_dependencies.py` que sin token o con token inválido `get_current_user` falla y que nunca lee un `usuario_id` de ruta, body o query
- [X] T017 Implementar `app/routers/auth.py` con `POST /auth/registro` (201 `UsuarioOut`, 400 email ya registrado, 422) y `POST /auth/token` (200 `Token`, 401 credenciales inválidas, 422) según `contracts/rest-api.md`, delegando en `services/auth.py` sin validar reglas en el router (Artículo I.1); verificar con `tests/api/test_auth.py` los cuatro códigos y que ninguna respuesta incluye la contraseña ni su hash (FR-002)
- [X] T018 Implementar `app/main.py` con la app FastAPI, el registro de routers, el middleware de logging y el manejador global que convierte cualquier `Exception` no prevista en 500 con `{"detail": "Error interno del servidor"}` logueando el detalle internamente (Artículo IV.5); verificar con `tests/api/test_errores_globales.py` que una excepción no controlada devuelve ese cuerpo exacto y ningún stack trace
- [X] T019 Implementar `app/mcp/server.py` con FastMCP y `app/mcp/auth.py` con la resolución de identidad (JWT verificado si el transporte lo aporta, usando la misma función que REST; usuario demo como fallback documentado con comentario explícito solo en `stdio` sin token) y montar el servidor MCP en la app ASGI de `app/main.py` (Artículo VI.4, decisión R-004); verificar con `tests/mcp/test_identidad.py` que con token se usa ese usuario, que sin token se usa el fallback y que un `usuario_id` pasado como argumento se ignora

**Checkpoint**: cálculo, persistencia, autenticación, arranque y servidor MCP operativos. Las tres historias pueden empezar.

---

## Phase 3: User Story 1 - Registrar una pista y saber si cumple la norma (Priority: P1) 🎯 MVP

**Goal**: Un diseñador autenticado registra una pista y el sistema la acepta o la rechaza según el mínimo de IPC-2221 (R1), el rango de validez (R2) y la capa (R3).

**Independent Test**: registrar una pista con ancho suficiente (201) y otra con ancho insuficiente para la misma corriente (400), sin usar listados, actualizaciones ni la consulta de cálculo.

- [X] T020 [US1] Definir las excepciones de dominio en `app/services/errores.py` (`AnchoInsuficienteError`, `FueraDeRangoError`, `PistaNoEncontradaError`, `PistaAjenaError`) sin ninguna dependencia de FastAPI (decisión R-009); verificar con `tests/unit/test_errores.py` que el módulo no importa FastAPI ni Starlette y que cada excepción lleva un mensaje específico
- [X] T021 [P] [US1] Implementar `app/schemas/pista.py` con `PistaCreate` (`nombre_red`, `proyecto`, `corriente_a`, `espesor_oz`, `capa`, `delta_t_c`, `ancho_mm`) y `PistaOut` (sin `usuario_id`, sin ancho mínimo derivado), usando el `Enum Capa` de `app/utils/ipc2221.py` con valores `externa` | `interna`, con `ancho_mm > 0` como validación **de schema** (422: un ancho nulo o negativo es un dato inválido, no una pista fuera de norma) y **sin** replicar los rangos de R2 (`corriente_a`, `espesor_oz`, `delta_t_c`) como `gt`/`le`/`ge`, porque son regla de negocio que debe devolver 400 en `services/` (Artículos IV.6, V.3, decisión R-011, `data-model.md` "Capa de validación de cada restricción"); verificar con `tests/unit/test_schemas_pista.py` que una `capa` distinta de esas dos es error de validación (422, caso de error 3), que `ancho_mm` igual a 0 y negativo son 422, que `corriente_a=36` **no** es rechazado por el schema (debe llegar al service para dar 400, caso de error 2) y que `PistaOut` no expone `usuario_id`
- [X] T022 [US1] Implementar `registrar_pista(datos, usuario_id, repo: PistasRepo = pistas_repo)` y `_validar_ancho()` en `app/services/pistas.py`, aplicando **R1** como `ancho_mm >= minimo_mm - TOLERANCIA_MM` y lanzando `AnchoInsuficienteError` si no se cumple (Artículos II.1, II.3, I.4, decisión R-010); verificar con `tests/unit/test_services_pistas.py::test_r1_*` e inyectando el repositorio falso: ancho mayor acepta, ancho exactamente igual al mínimo acepta, 0.0009 mm por debajo acepta por tolerancia, 0.002 mm por debajo rechaza
- [X] T023 [US1] Implementar `_validar_parametros_norma()` en `app/services/pistas.py` aplicando **R2**: `corriente_a` en `(0, 35]`, `delta_t_c` en `[10, 100]`, `espesor_oz` en `[0.5, 3]`, lanzando `FueraDeRangoError` fuera de rango y nunca aceptando con advertencia (Artículo VIII.5); verificar con `tests/unit/test_services_pistas.py::test_r2_*` con repositorio falso: los seis extremos válidos aceptan y un valor justo por fuera de cada límite rechaza
- [X] T024 [US1] Hacer que `app/services/pistas.py` resuelva la constante `k` mediante `K_POR_CAPA` sin ningún `if` por capa, aplicando **R3** (Artículos II.2, VIII.3); verificar con `tests/unit/test_services_pistas.py::test_r3_*` con repositorio falso que `externa` usa 0.048, `interna` usa 0.024 y que una capa no contemplada no llega al cálculo
- [X] T025 [US1] Implementar `POST /pistas/` en `app/routers/pistas.py` traduciendo `AnchoInsuficienteError` y `FueraDeRangoError` a 400 y delegando en `services.pistas.registrar_pista()`, con el `usuario_id` tomado de `get_current_user` (Artículos I.1, IV.4, `contracts/rest-api.md`); verificar con `tests/api/test_pistas_registro.py` los casos de error 1 (400 ancho insuficiente), 2 (400 fuera de rango), 3 (422 capa inválida) y 4 (401 sin token), más el 201 del caso válido
- [X] T026 [US1] Implementar la tool `registrar_pista` en `app/mcp/tools/pistas.py` como adaptador que llama a la **misma** `services.pistas.registrar_pista()` que el router, con descripción específica y verificable y devolviendo `{"error": "..."}` en error de negocio (Artículos VI.1, VI.2, VI.3); verificar con `tests/mcp/test_tools.py` un caso exitoso y un caso de ancho insuficiente (Artículo VII.6), y que la tool no contiene ninguna comparación de ancho propia

**Checkpoint**: MVP entregable. La verificación IPC-2221 funciona por REST y por MCP.

---

## Phase 4: User Story 2 - Consultar el ancho mínimo antes de decidir (Priority: P2)

**Goal**: Obtener el ancho mínimo exigido para unos parámetros sin registrar nada.

**Independent Test**: pedir el ancho mínimo para un juego de parámetros y comprobar que no se creó ninguna pista.

- [X] T027 [P] [US2] Añadir `CalculoIn` (`corriente_a`, `espesor_oz`, `capa`, `delta_t_c`) y `CalculoOut` (`ancho_minimo_mm`) a `app/schemas/pista.py` (Artículos IV.6, V.3); verificar con `tests/unit/test_schemas_calculo.py` que falta de campo o capa inválida es 422 y que `CalculoOut` no incluye campos de pista
- [X] T028 [US2] Implementar `calcular_ancho_minimo(datos)` en `app/services/pistas.py`, que aplica R2, llama a la función pura de `utils/ipc2221.py`, redondea a 3 decimales y **no persiste nada** (FR-014, decisión R-010); verificar con `tests/unit/test_services_calculo.py` que devuelve 0.300 para 1 A/10 °C/1 oz externa, que fuera de rango lanza `FueraDeRangoError` y que no invoca ninguna operación de escritura del repositorio falso
- [X] T029 [US2] Implementar `POST /pistas/calculo` en `app/routers/pistas.py` devolviendo 200 `CalculoOut`, 400 fuera de rango, 401 sin token y 422 de schema, delegando en el service (Artículo I.1, `contracts/rest-api.md`); verificar con `tests/api/test_calculo.py` los cuatro códigos y que un `GET /pistas/` posterior sigue vacío
- [X] T030 [US2] Implementar la tool `calcular_ancho_minimo` en `app/mcp/tools/pistas.py` llamando a la misma función de service que el router (Artículo VI.1); verificar con `tests/mcp/test_tools.py` un caso exitoso, un caso fuera de rango como `{"error": ...}` y el **caso de error 7** de la spec: con 1 A/10 °C/1 oz, capa interna (0.781 mm) devuelve un ancho mayor que capa externa (0.300 mm)

**Checkpoint**: US1 y US2 funcionan de forma independiente por ambas interfaces.

---

## Phase 5: User Story 3 - Gestionar las pistas propias (Priority: P3)

**Goal**: Listar de forma paginada, leer, actualizar y eliminar solo las pistas propias, revalidando la norma al modificar.

**Independent Test**: con dos usuarios, comprobar que cada uno solo alcanza sus pistas incluso pasando el identificador ajeno a mano.

- [X] T031 [P] [US3] Añadir `PistaUpdate` (todos los campos opcionales) y `PaginacionParams` (`skip >= 0` por defecto 0; `1 <= limit <= 100` por defecto 20) a `app/schemas/pista.py` (Artículo V.2, decisión R-005); verificar con `tests/unit/test_schemas_paginacion.py` que `skip` negativo y `limit` fuera de `1..100` son 422 y que los valores por defecto son 0 y 20
- [X] T032 [US3] Ampliar `app/repositories/pistas.py` con `listar_por_usuario(usuario_id, skip, limit)`, `obtener_por_id`, `actualizar` y `eliminar`, filtrando **siempre** por `usuario_id` (Artículos I.3, III.3); verificar con `tests/integration/test_repositorio_pistas_crud.py` contra SQLite en memoria que ninguna operación devuelve ni modifica pistas de otro usuario y que la paginación respeta `skip`/`limit`
- [X] T033 [US3] Implementar `listar_pistas` y `obtener_pista` en `app/services/pistas.py` con el repositorio por parámetro, aplicando **R4**: el `usuario_id` viene del llamador autenticado, y una pista ajena lanza `PistaAjenaError` mientras una inexistente lanza `PistaNoEncontradaError` (Artículos II.3, IV.4); verificar con `tests/unit/test_services_pistas.py::test_r4_*` con repositorio falso que el listado solo devuelve las del usuario y que leer una ajena lanza `PistaAjenaError`
- [X] T034 [US3] Implementar `actualizar_pista` en `app/services/pistas.py` aplicando **R5**: fusiona los campos recibidos sobre los actuales, revalida R1, R2 y R3 sobre el resultado y, si falla, lanza el error de negocio sin escribir nada, dejando la pista con sus valores anteriores y sin estado "no conforme" (decisión R-011); verificar con `tests/unit/test_services_pistas.py::test_r5_*` con repositorio falso que una actualización válida persiste, que una que deja el ancho insuficiente no llama a `actualizar` del repositorio y que una que saca los parámetros de rango tampoco
- [X] T035 [US3] Implementar `eliminar_pista` en `app/services/pistas.py` verificando pertenencia antes de borrar (Artículo IV.4, R4); verificar con `tests/unit/test_services_pistas.py::test_eliminar_*` con repositorio falso que una pista ajena lanza `PistaAjenaError` sin llamar a `eliminar` y que una inexistente lanza `PistaNoEncontradaError`
- [X] T036 [US3] Implementar `GET /pistas/`, `GET /pistas/{id}`, `PATCH /pistas/{id}` y `DELETE /pistas/{id}` en `app/routers/pistas.py`, traduciendo `PistaAjenaError` a 403, `PistaNoEncontradaError` a 404 y los errores de norma a 400, con `GET /pistas/` filtrando por el `usuario_id` del JWT y **nunca** devolviendo 403 (Artículos V.1, IV.4, `contracts/rest-api.md`); verificar con `tests/api/test_pistas_crud.py` los casos de error 5 (403 leer/modificar/eliminar pista ajena por ID), 6 (404 pista inexistente), el 204 de borrado y que el listado de un usuario nunca incluye pistas del otro
- [X] T037 [US3] Implementar las tools `listar_pistas(skip, limit)` y `eliminar_pista(pista_id, confirmar=False)` en `app/mcp/tools/pistas.py`, llamando a los mismos services que los routers y exigiendo confirmación gestionada por el servidor antes de borrar (Artículos VI.1, VI.5, FR-016, decisión R-003); verificar con `tests/mcp/test_tools.py` para cada tool un caso exitoso y uno de error, incluido que `eliminar_pista` sin `confirmar=True` no borra nada y devuelve la pista afectada, y que con `confirmar=True` borra

**Checkpoint**: las tres historias completas por REST y por MCP.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T038 [P] Auditar en `tests/` que cada una de R1, R2, R3, R4 y R5 tiene al menos un test unitario propio e identificable por nombre y que los 7 casos de error de `spec.md` están cubiertos, dejando el mapeo regla → test documentado en `tests/README.md` (Artículo VII.3, cobertura de *reglas*)
- [X] T039 [P] Verificar los umbrales de cobertura con `uv run pytest --cov=app --cov-report=term-missing`: `app/services/` ≥ 90% y global ≥ 70%, con la lista `omit` de `[tool.coverage.run]` aplicada y ningún módulo de negocio excluido (Artículo VII.3)
- [X] T040 [P] Verificar que `uv run ruff check .` termina sin hallazgos y corregir lo que reporte
- [X] T041 [P] Comprobar que ningún módulo de `app/services/` importa SQLAlchemy, `Session` ni FastAPI y que ninguna tool de `app/mcp/tools/` reimplementa lógica de `services/`, con un test de arquitectura en `tests/test_arquitectura.py` que inspeccione los imports (Artículos I.2, I.5, VI.1)
- [X] T042 Ejecutar los 9 escenarios de `quickstart.md` contra la app en marcha (`uv run uvicorn app.main:app`) y el servidor MCP, y anotar cualquier desviación respecto a los valores esperados (0.300, 0.781, 1.816, 3.337 mm)

---

## Dependencies

**Orden de fases**: Phase 1 (Setup) → Phase 2 (Foundational, bloqueante) → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (Polish).

**Dependencias dentro de Phase 2**: T005 y T006 son independientes entre sí. T007 → T008 → (T009, T010) → T011. T012 depende de T008 y T010. T013 y T014 dependen de T009/T010 y de T012. T015 depende de T013. T016 depende de T006, T008, T013 y T014. T017 depende de T015 y T016. T018 depende de T017 y T004. T019 depende de T006, T016 y T018.

**Dependencias de capa dentro de cada historia** (estrictas):

- US1: T020 → T021 → T022 → T023 → T024 → T025 → T026
- US2: T027 → T028 → T029 → T030
- US3: T031 → T032 → T033 → T034 → T035 → T036 → T037

Las tareas de `services/` de una misma historia tocan el mismo archivo (`app/services/pistas.py`), por lo que van en serie aunque cada una cubra una regla distinta.

**Independencia entre historias**: US2 y US3 no dependen de US1; las tres solo dependen de la Phase 2. Se ordenan por prioridad, no por necesidad técnica.

## Parallel Execution Examples

- **Phase 1**: T003 y T004 en paralelo una vez hecho T002.
- **Phase 2**: T005 ∥ T006 (dos módulos distintos de `utils/`); T009 ∥ T010 (dos modelos); T013 ∥ T014 (dos repositorios).
- **US1**: T021 puede hacerse en paralelo con T020 (schemas y excepciones son archivos distintos); de T022 en adelante, serie.
- **US2 / US3**: T027 y T031 son paralelizables entre sí si se trabajan las dos historias a la vez, porque tocan `app/schemas/pista.py` en secciones distintas; coordinar el archivo o hacerlas en serie si el mismo agente edita ambas.
- **Phase 6**: T038, T039, T040 y T041 en paralelo; T042 al final, con la app en marcha.

## Implementation Strategy

**MVP**: Phase 1 + Phase 2 + Phase 3 (US1) = 26 tareas. Con eso un diseñador ya registra pistas y el sistema las acepta o las rechaza según IPC-2221, por REST y por MCP, que es la razón de existir del sistema.

**Incremento 2**: Phase 4 (US2) añade la consulta previa del ancho mínimo, que evita el ciclo de prueba y error.

**Incremento 3**: Phase 5 (US3) añade la gestión del histórico con aislamiento por usuario y revalidación al modificar.

**Cierre**: Phase 6 verifica cobertura de reglas, umbrales, lint y arquitectura de capas.

**Regla de terminación** (Artículo VII.8): ninguna tarea se marca como hecha sin su test correspondiente en verde. Si un test no se puede escribir todavía, la tarea no está lista para empezar.

**Fuera de alcance**: no hay tareas de frontend, contenedores, CI/CD ni despliegue; esta funcionalidad es un servicio backend con dos interfaces (REST y MCP).
