# Implementation Plan: Verificador de pistas de PCB según IPC-2221

**Branch**: `main` (directorio de feature `001-verificador-pistas-ipc2221`; el script de setup reporta `BRANCH` desde `.specify/feature.json`, no desde git) | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-verificador-pistas-ipc2221/spec.md`

## Summary

Servicio que permite a un diseñador de PCB registrar sus pistas y verificar
automáticamente, contra la ecuación de IPC-2221, si el ancho diseñado alcanza el
mínimo exigido por la corriente que va a conducir (R1), dentro del rango de
validez del modelo (R2), con la constante `k` que corresponde a la capa (R3),
aislado por usuario (R4) y revalidando al modificar (R5).

Enfoque técnico: una API FastAPI y un servidor MCP (FastMCP) que exponen las
mismas reglas porque ambos llaman a las mismas funciones de `app/services/`
(Artículo VI.1). El cálculo de IPC-2221 es una función pura en `app/utils/`, sin
dependencias de persistencia (Artículo I.4), y las constantes de la norma viven
en un único módulo (Artículo VIII.3). Los services reciben el repositorio como
parámetro con valor por defecto (Artículo II.3), lo que permite testear con un
repositorio falso sin `unittest.mock` (Artículo VII.2).

## Technical Context

**Language/Version**: Python 3.12, gestionado con `uv`

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 +
`pydantic-settings`, `passlib[bcrypt]`, `python-jose` (JWT HS256), FastMCP
(servidor MCP). Ver "Dependencias añadidas" más abajo: tres librerías de soporte
no estaban en la lista del encargo y se declaran explícitamente.

**Storage**: SQLite en desarrollo, vía SQLAlchemy 2.x con migraciones Alembic. El
módulo `app/database.py` aplica `connect_args={"check_same_thread": False}` solo
para SQLite, de modo que el mismo código funcione contra Postgres sin tocar
`services/` ni `routers/` (Artículo III.2).

**Testing**: pytest + pytest-cov. Pirámide unitarias → integración → API
(Artículo VII.1), con umbrales de cobertura del Artículo VII.3 y la lista `omit`
declarada en `pyproject.toml`.

**Target Platform**: servidor Linux/Windows con Python 3.12; API HTTP local en
desarrollo. El servidor MCP se monta sobre la misma app ASGI.

**Project Type**: web service (API REST + servidor MCP), sin frontend.

**Performance Goals**: el cálculo de IPC-2221 es aritmética de coma flotante sin
E/S, así que el objetivo es que la verificación no añada latencia perceptible
frente al acceso a base de datos. Resuelto en `research.md` (R-006): la spec no
fija objetivos numéricos y el dominio no los exige.

**Constraints**: anchos siempre en milímetros en la frontera del sistema
(FR-017); tolerancia de comparación 0.001 mm y ancho mínimo reportado a 3
decimales; `SECRET_KEY` y `DATABASE_URL` solo desde `.env` (Artículo IV.3).

**Scale/Scope**: uso individual por diseñador, del orden de cientos a miles de
pistas por usuario; paginación obligatoria en el listado (FR-010). 8 endpoints
REST y 4 tools MCP, ambos ya fijados por la spec. Resuelto en `research.md`
(R-006).

### Dependencias añadidas (desviación declarada)

El encargo pedía no agregar librerías fuera de la lista sin declararlo. Estas
tres son de soporte y no aportan reglas de negocio:

| Librería | Por qué es necesaria | Alternativa si se rechaza |
|----------|----------------------|---------------------------|
| `httpx` | `TestClient` de FastAPI/Starlette lo requiere para los tests de API (Artículo VII.5) | Probar solo services y repositorios, perdiendo los tests de API que la constitución exige |
| `email-validator` | `EmailStr` de Pydantic v2 lo requiere para validar el email único del Usuario (FR-001) | Usar `str` con validación propia en el schema |
| `uvicorn` | Servidor ASGI para levantar la app en desarrollo y para `quickstart.md` | Ejecutar solo la suite de tests, sin app en ejecución |

Ninguna otra librería se incorpora. No se propone frontend, Docker, CI/CD ni
despliegue: fuera del alcance de esta funcionalidad por indicación explícita.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluado contra `.specify/memory/constitution.md` v1.0.0.

| Artículo | Gate | Estado inicial | Cómo lo cumple el diseño |
|----------|------|----------------|--------------------------|
| I.1 | Los routers no validan reglas de negocio | PASS | `app/routers/pistas.py` traduce resultado o excepción de dominio a HTTP; los umbrales de R1/R2/R3 viven en `app/services/pistas.py` |
| I.2 | Los services no importan SQLAlchemy ni `Session` | PASS | Los services solo conocen el contrato del repositorio que reciben por parámetro |
| I.3 | Solo los repositorios acceden a la base de datos | PASS | `app/repositories/pistas.py` y `usuarios.py` son la única capa con `Session` |
| I.4 | El cálculo IPC-2221 es función pura en `utils/`; la decisión de aceptar/rechazar vive en `services/` | PASS | `app/utils/ipc2221.py::ancho_minimo_mm()` es puro; `services/pistas.py` compara y decide |
| I.5 | Las tools MCP no reimplementan lógica de services | PASS | Ver VI.1 |
| II.1 | SRP: validación separada de orquestación | PASS | `_validar_parametros_norma()` y `_validar_ancho()` separados de `registrar_pista()` |
| II.2 | OCP: extender por constante/Enum, no reescribiendo `if` | PASS | `K_POR_CAPA: dict[Capa, float]` y `Capa` como `Enum`; añadir una capa es añadir una entrada |
| II.3 | DIP: repositorio como parámetro con valor por defecto | PASS | `def registrar_pista(..., repo: PistasRepo = pistas_repo)` en todos los services |
| II.4 | No forzar LSP/ISP artificialmente | PASS | Sin jerarquías de clases; el contrato del repositorio es estructural (Protocol) |
| III.1 | SQLAlchemy + Alembic, sin SQL crudo concatenado | PASS | Migración inicial en Alembic; consultas con la API de SQLAlchemy |
| III.2 | `database.py` portable a Postgres | PASS | `connect_args` condicional solo para SQLite |
| III.3 | `usuario_id` como FK y nunca omitido al consultar pistas | PASS | Todas las consultas de `pistas` filtran por `usuario_id` en el repositorio |
| IV.1 | bcrypt vía `passlib[bcrypt]`, contraseña nunca expuesta ni logueada | PASS | `app/utils/seguridad.py` hashea; `UsuarioOut` no incluye el hash |
| IV.2 | OAuth2 password flow + JWT HS256, expiración finita | PASS | `POST /auth/token`; `ACCESS_TOKEN_EXPIRE_MINUTES` en configuración |
| IV.3 | `SECRET_KEY`/`DATABASE_URL` solo en `.env`, con `.env.example` versionado | PASS | `app/config.py` con `pydantic-settings`; `.env` en `.gitignore` |
| IV.4 | `usuario_id` siempre del JWT, nunca de URL/body/query; verificar pertenencia antes de tocar | PASS | `get_current_user` como dependencia; el service comprueba pertenencia antes de leer/actualizar/eliminar |
| IV.5 | `Exception` genérica → 500 con detalle fijo, sin stack trace al cliente | PASS | Manejador global en `app/main.py` que loguea internamente |
| IV.6 | Toda entrada validada con schemas Pydantic | PASS | `app/schemas/` valida antes de llamar a `services/` |
| V.1 | Verbos y códigos, con 403 solo para recurso ajeno identificado por `id` | PASS | La tabla de contrato de la spec ya fija los códigos; `GET /pistas/` filtra y nunca devuelve 403 |
| V.2 | Paginación con `skip`/`limit` y valores por defecto razonables | PASS | `skip=0`, `limit=20`, `limit` máximo 100 (decisión R-005) |
| V.3 | Schemas de entrada y salida distintos, sin exponer el modelo ORM | PASS | `PistaCreate`, `PistaUpdate`, `PistaOut` separados |
| VI.1 | Cada tool MCP llama a un service; la lógica se agrega primero en `services/` | PASS | Las 4 tools son adaptadores finos sobre `services/pistas.py` |
| VI.2 | Descripción de tool específica y verificable | PASS | Redactadas en `contracts/mcp-tools.md` |
| VI.3 | Errores de negocio como estructura clara, no excepción sin controlar | PASS | Las tools devuelven `{"error": "..."}` |
| VI.4 | Identidad MCP documentada: token verificado si existe; usuario demo solo como fallback declarado | PASS | `app/mcp/auth.py` resuelve identidad; decisión R-004 |
| VI.5 | Tool destructiva con confirmación gestionada por el servidor | PASS | `eliminar_pista` exige `confirmar=True` (FR-016, decisión R-003) |
| VII.1 | Pirámide de pruebas | PASS | Mayoría unitarias sobre `utils/` y `services/` |
| VII.2 | Repositorio falso por parámetro; prohibido `unittest.mock` para esto | PASS | `tests/fakes.py` implementa el mismo contrato |
| VII.3 | 100% de reglas de negocio con test propio; `services/` ≥ 90%; global ≥ 70% con `omit` declarado | PASS | R1–R5 y los 7 casos de error tienen test nominado; `omit` en `pyproject.toml` |
| VII.4 | Integración contra base de datos real (SQLite en memoria) | PASS | Fixture de sesión real, no el repositorio falso |
| VII.5 | Tests de API con `dependency_overrides` | PASS | Se sustituyen `get_db`, `get_pistas_repo` y `get_current_user` |
| VII.6 | Cada tool MCP con caso exitoso y caso de error | PASS | 4 tools × 2 casos mínimos |
| VII.7 | El cálculo se verifica contra valores de referencia calculados a mano | PASS | Caso 1 A, ΔT 10 °C, 1 oz, capa externa (ver `research.md` R-002) |
| VIII.1 | Ecuación y constantes de IPC-2221 | PASS | `I = k·ΔT^0.44·A^0.725`, `k` 0.048/0.024 |
| VIII.2 | IPC-2221 y no IPC-2152, declarado en spec y en el docstring del módulo | PASS | Docstring de `app/utils/ipc2221.py` |
| VIII.3 | Constantes de la norma en un único módulo de `utils/`, sin repetirse | PASS | `app/utils/ipc2221.py` es la única fuente de `k`, exponentes, factor oz→mils y 0.0254 |
| VIII.4 | API en milímetros; mils es detalle interno | PASS | Conversión encapsulada en `utils/` |
| VIII.5 | Rango de validez sin extrapolación silenciosa, con test propio | PASS | R2 con límites concretos y rechazo 400 |

**Resultado inicial**: PASS, sin violaciones. Sección "Complexity Tracking" no
aplica y se omite.

### Re-check después del diseño de Phase 1

Reevaluado contra `research.md`, `data-model.md`, `contracts/rest-api.md`,
`contracts/mcp-tools.md` y `quickstart.md`: **PASS, sin violaciones nuevas**. El
diseño no introdujo ninguna capa, entidad ni endpoint fuera de los que ya declara
la spec, así que ningún gate cambió de estado. Puntos que el diseño concretó:

- **I.2 / I.4**: `app/utils/ipc2221.py` quedó como función pura y única sede de las
  constantes, incluida `TOLERANCIA_MM`; la comparación (una decisión) se quedó en
  el service (R-001, R-010).
- **II.3 / VII.2**: el contrato del repositorio se expresa como `Protocol` y se
  inyecta por parámetro con valor por defecto, lo que hace innecesario
  `unittest.mock` (R-007).
- **IV.4 / V.1**: `PistaOut` no expone `usuario_id`, para que no exista la
  tentación de aceptarlo como entrada; `GET /pistas/` filtra y nunca devuelve 403.
- **V.2**: paginación concretada en `skip=0`, `limit=20`, máximo 100 (R-005), lo
  único que la spec había dejado abierto para la planificación.
- **VI.1 / VI.3 / VI.5**: las 4 tools quedaron como adaptadores sobre los mismos
  services, con errores de negocio como estructura y confirmación de borrado
  gestionada por el servidor (R-003, R-008, R-009).
- **VIII.5 / R2**: el rango de validez se trata como regla de negocio (400) y no
  como validación de schema (422), para respetar el caso de error 2 de la spec.

Una decisión de diseño se registró explícitamente como *no* tomada: no se persiste
ni se expone el ancho mínimo calculado, porque no es un atributo declarado en la
spec (R-011). Exponerlo sería un cambio de spec, no de plan.

## Project Structure

### Documentation (this feature)

```text
specs/001-verificador-pistas-ipc2221/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── rest-api.md
│   └── mcp-tools.md
├── checklists/
│   └── requirements.md  # Creado por /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/
├── main.py                 # App FastAPI, montaje ASGI del MCP, middleware de logging, manejador 500 (IV.5)
├── config.py               # pydantic-settings: SECRET_KEY, DATABASE_URL, ACCESS_TOKEN_EXPIRE_MINUTES (IV.3)
├── database.py             # Engine y sesión; connect_args condicional solo para SQLite (III.2)
├── logging_config.py       # Configuración de logging
├── dependencies.py         # get_db, get_pistas_repo, get_usuarios_repo, get_current_user (IV.4, VII.5)
├── routers/
│   ├── auth.py             # POST /auth/registro, POST /auth/token
│   └── pistas.py           # CRUD de /pistas/ + POST /pistas/calculo (I.1)
├── services/
│   ├── auth.py             # registrar_usuario, autenticar_usuario
│   └── pistas.py           # registrar_pista, listar_pistas, obtener_pista, actualizar_pista, eliminar_pista, calcular_ancho_minimo (I.2, II.1, II.3)
├── repositories/
│   ├── usuarios.py         # Única capa con Session para usuarios (I.3)
│   └── pistas.py           # Única capa con Session para pistas; filtra siempre por usuario_id (III.3)
├── models/
│   ├── usuario.py          # Modelo SQLAlchemy Usuario
│   └── pista.py            # Modelo SQLAlchemy Pista, con usuario_id FK
├── schemas/
│   ├── usuario.py          # UsuarioCreate, UsuarioOut, Token
│   └── pista.py            # PistaCreate, PistaUpdate, PistaOut, CalculoIn, CalculoOut (V.3, IV.6)
├── utils/
│   ├── ipc2221.py          # Función pura del cálculo + constantes de la norma (I.4, VIII.1, VIII.3)
│   └── seguridad.py        # Hash bcrypt y firma/verificación JWT (IV.1, IV.2)
└── mcp/
    ├── server.py           # Servidor FastMCP
    ├── auth.py             # Resolución de identidad en MCP (VI.4)
    └── tools/
        └── pistas.py       # registrar_pista, calcular_ancho_minimo, listar_pistas, eliminar_pista (VI.1)

alembic/
├── env.py
└── versions/               # Migración inicial: usuarios y pistas (III.1)

tests/
├── conftest.py             # Fixtures: sesión SQLite en memoria, dependency_overrides (VII.4, VII.5)
├── fakes.py                # Repositorio falso con el mismo contrato (VII.2)
├── unit/
│   ├── test_ipc2221.py     # Valores de referencia calculados a mano (VII.7)
│   └── test_services_pistas.py  # R1-R5 con repositorio falso
├── integration/
│   └── test_repositories.py     # Contra SQLite en memoria
├── api/
│   ├── test_auth.py
│   └── test_pistas.py      # Los 7 casos de error de la spec
└── mcp/
    └── test_tools.py       # 4 tools × (éxito + error de negocio) (VII.6)

pyproject.toml              # uv, pytest-cov con [tool.coverage.run] omit declarado (VII.3), ruff
.env.example                # Variables documentadas sin valores reales (IV.3)
```

**Structure Decision**: estructura única de servicio backend bajo `app/`, con las
siete carpetas de capas exigidas por el encargo (`routers/`, `mcp/tools/`,
`services/`, `repositories/`, `models/`, `schemas/`, `utils/`), que es exactamente
el corte de responsabilidades del Artículo I. Se descartan las variantes
frontend/backend y móvil de la plantilla: esta funcionalidad no tiene interfaz de
usuario propia; sus dos interfaces son REST y MCP. Los tests se separan por nivel
de la pirámide del Artículo VII.1 en `tests/unit`, `tests/integration`,
`tests/api` y `tests/mcp`.
