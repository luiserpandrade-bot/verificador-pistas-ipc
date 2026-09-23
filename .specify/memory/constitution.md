# Constitución — Verificador de Pistas de PCB (IPC-2221)

## Core Principles

### Artículo I — Arquitectura en capas

1. `routers/` reciben la solicitud HTTP, delegan al service correspondiente y
   traducen su resultado (o excepción) a una respuesta HTTP. Un router NUNCA
   valida reglas de negocio (ej. "el ancho debe cumplir el mínimo de
   IPC-2221") — esa lógica vive en `services/`.
2. `services/` contienen toda la lógica de negocio. Un service NUNCA importa
   SQLAlchemy, `Session`, ni ningún detalle de persistencia directamente.
3. `repositories/` son la única capa autorizada a leer o escribir en la base
   de datos. Un repository no contiene reglas de negocio, solo operaciones
   de persistencia (guardar, listar, buscar, actualizar, eliminar).
4. `utils/` son funciones puras (mismo input → mismo output, sin efectos
   secundarios), sin importar nada de `services/`, `routers/` ni
   `repositories/`. El cálculo del ancho mínimo según la ecuación de
   IPC-2221 vive en `utils/` como función pura; la DECISIÓN de aceptar o
   rechazar una pista con ese resultado vive en `services/`.
5. `mcp/tools/` NUNCA reimplementan lógica de `services/`. Si una tool de MCP
   y un router necesitan la misma regla, ambos llaman al mismo service.

### Artículo II — SOLID aplicado (no teórico)

1. **SRP**: cada función de `services/` hace una sola cosa. La validación
   (`_validar_x`) está separada de la orquestación (`registrar_x`).
2. **OCP**: agregar una capa, un tipo de cobre o una constante de la norma se
   hace agregando un valor a una constante o `Enum` (ej. la constante `k`
   por tipo de capa), nunca reescribiendo un `if` ya existente.
3. **DIP**: todo service que necesite un repository lo recibe como parámetro
   con un valor por defecto (`def registrar_pista(..., repo=pistas_repo)`),
   nunca lo importa fijo dentro del cuerpo de la función. Esto es
   innegociable: es lo que permite testear sin `unittest.mock`.
4. No se fuerza LSP ni ISP si el proyecto no tiene jerarquías de clases ni
   interfaces formales — no agregar complejidad artificial para cumplir un
   principio que no aplica todavía.

### Artículo III — Persistencia

1. SQLAlchemy como ORM, Alembic para migraciones. Ninguna sentencia SQL cruda
   concatenada con strings.
2. SQLite en desarrollo; el código de `database.py` debe funcionar contra
   Postgres sin tocar `services/` ni `routers/` (usar `connect_args`
   condicional solo para SQLite).
3. Cada modelo con datos de usuario incluye `usuario_id` como FK. Ninguna
   consulta de datos de Pista puede omitir el filtro por `usuario_id`.

### Artículo IV — Seguridad (no negociable)

1. Contraseñas: hash con bcrypt (vía `passlib[bcrypt]` con versiones fijadas
   que se sabe que funcionan). Nunca se guarda ni se loguea una contraseña
   en texto plano, y nunca se expone en una respuesta.
2. Autenticación: OAuth2 password flow + JWT firmado con HS256.
   `ACCESS_TOKEN_EXPIRE_MINUTES` configurable, nunca infinito.
3. `SECRET_KEY` y `DATABASE_URL` viven solo en `.env` (nunca versionado),
   cargados con `pydantic-settings`. `.env.example` sí se versiona y
   documenta todas las variables necesarias sin valores reales.
   `SECRET_KEY` se genera con `openssl rand -hex 32` o equivalente
   criptográficamente seguro, nunca escrito a mano.
4. Autorización: el `usuario_id` para filtrar, crear o modificar una pista
   SIEMPRE sale del token JWT decodificado (`get_current_user`), NUNCA de un
   parámetro de la URL, del body, ni de un query param. Esto aplica también
   a recursos ya existentes: cualquier operación sobre una pista por `id`
   (leer, actualizar, eliminar) primero verifica que esa pista pertenece al
   usuario autenticado, antes de tocarla.
5. Un error no controlado (`Exception` genérica) devuelve `500` con
   `{"detail": "Error interno del servidor"}` — nunca un stack trace ni el
   mensaje de la excepción original al cliente. El detalle sí se loguea
   internamente.
6. Toda entrada de usuario se valida con schemas Pydantic antes de llegar a
   `services/`.

### Artículo V — Diseño de endpoints REST

1. Convención de verbos y códigos: `POST` crea (`201`), `GET` lista/lee
   (`200`), `PATCH` actualiza (`200`), `DELETE` elimina (`204`), fallo de
   autenticación (`401`), recurso no encontrado (`404`), error de validación
   de schema (`422`), error de regla de negocio conocido (`400` con
   `{"detail": "..."}`). `403` se reserva para cuando el recurso solicitado
   existe pero pertenece a otro usuario y la operación lo identifica por
   `id` explícito en la ruta (ej. `PATCH /pistas/{id}`); un listado
   (`GET /pistas/`) NUNCA devuelve `403` — simplemente filtra por el
   `usuario_id` del JWT y nunca expone ni acepta el de otro usuario.
2. Toda lista paginada expone `skip` y `limit` como query params, con
   valores por defecto razonables (ej. `skip=0, limit=20`); valores
   inválidos (negativos, no numéricos) son error de schema (`422`).
3. Los schemas de entrada y salida son distintos (`PistaCreate`,
   `PistaUpdate` vs `PistaOut`) — nunca se expone el modelo de SQLAlchemy
   directamente.

### Artículo VI — MCP: tools y reutilización

1. Cada tool de MCP llama a una función de `services/`, punto. Ejemplo:
   `registrar_pista` (tool) y `POST /pistas/` (router) llaman a la misma
   función `services/pistas.py::registrar_pista()`. Si una tool necesita
   lógica que no existe en `services/`, esa lógica se agrega en `services/`
   primero, y la tool la reutiliza — nunca al revés.
2. La descripción de cada tool es específica y verificable (ej. "Registra
   una pista con corriente, espesor de cobre, capa, ΔT y ancho, y la rechaza
   si el ancho es menor al mínimo de IPC-2221"), nunca genérica ("maneja
   pistas").
3. Errores de negocio se devuelven como una estructura clara
   (`{"error": "..."}`), nunca como una excepción sin controlar que rompa
   la sesión del cliente MCP.
4. Si el transporte es `stdio` y no hay forma de propagar identidad real de
   usuario, se documenta explícitamente en el código como simplificación
   consciente (comentario), nunca como un olvido silencioso. Si el
   transporte es `streamable-http` y hay un token verificado, la tool DEBE
   usar la identidad de ese token (el mismo JWT que usa REST, nunca un
   usuario demo hardcodeado) — el usuario demo es solo el fallback legítimo
   cuando no hay ningún token disponible, y se documenta como tal.
5. Cualquier tool con efecto destructivo (ej. `eliminar_pista`) debe pedir
   confirmación explícita gestionada por el servidor, nunca depender de que
   el modelo decida preguntar por su cuenta.

### Artículo VII — Testing y cobertura

1. Pirámide de pruebas obligatoria: unitarias (mayoría) → integración →
   API/E2E (minoría).
2. Tests unitarios de `services/` inyectan un repositorio falso (que cumple
   el mismo contrato que el real) como parámetro — está PROHIBIDO usar
   `unittest.mock` para esto, porque el diseño con DIP ya lo hace
   innecesario.
3. Cobertura mínima exigida:
   - 100% de las reglas de negocio explícitas de `spec.md` cubiertas por al
     menos un test unitario cada una — cobertura de *reglas*, no solo de
     líneas.
   - Cobertura de líneas de `services/` ≥ 90%.
   - Cobertura global de líneas ≥ 70%, medida con
     `pytest --cov=app --cov-report=term-missing`. Este umbral NO exige
     cubrir el arranque de la app (`main.py`: lifespan, montaje ASGI de MCP,
     middleware de logging), el servidor MCP en sí (`mcp/server.py`,
     `mcp/auth.py`) ni `logging_config.py` — son infraestructura de
     arranque, no lógica de negocio, y su exclusión se declara
     explícitamente en `[tool.coverage.run] omit` de `pyproject.toml`,
     nunca como una omisión silenciosa.
4. Tests de integración corren contra una base de datos real (SQLite en
   memoria como mínimo), nunca contra el repositorio falso.
5. Tests de API usan `app.dependency_overrides` de FastAPI para sustituir
   `get_db`, `get_pistas_repo` y `get_current_user` — nunca levantan un
   servidor real ni golpean la base de datos de desarrollo.
6. Toda tool de MCP tiene al menos dos tests: un caso exitoso y un caso de
   error de negocio, verificados directamente o vía MCP Inspector.
7. La función de cálculo de IPC-2221 en `utils/` se verifica contra valores
   de referencia calculados a mano y documentados en el propio test (ej.
   1 A, ΔT = 10 °C, 1 oz, capa externa ≈ 0,30 mm), con tolerancia declarada.
8. Ninguna tarea de `tasks.md` se considera terminada sin su test
   correspondiente en verde.

### Artículo VIII — Dominio técnico: IPC-2221

1. La regla central del sistema aplica la ecuación de IPC-2221 para la
   capacidad de corriente de conductores:
   `I = k · ΔT^0.44 · A^0.725`, con `A` en mils², `ΔT` en °C e `I` en A,
   `k = 0.048` para capa externa y `k = 0.024` para capa interna. El ancho
   se obtiene como `A / (espesor_oz · 1.378)` en mils.
2. Se declara explícitamente que se usa IPC-2221 y no IPC-2152: IPC-2152 es
   la norma vigente y más precisa, pero se basa en gráficas sin ecuación
   cerrada. Esta decisión se documenta en `spec.md` y en el docstring del
   módulo de cálculo, nunca queda implícita.
3. Las constantes de la norma (`k` por capa, exponentes, factor oz → mils)
   viven en un solo módulo de `utils/` y no se repiten en ningún otro lugar
   del código.
4. La API recibe y devuelve anchos en milímetros; la conversión a mils es un
   detalle interno del cálculo y nunca se le exige al cliente.
5. El modelo tiene un rango de validez. Una entrada fuera de ese rango
   NUNCA se extrapola en silencio: `spec.md` define qué ocurre (rechazo o
   advertencia) y esa decisión tiene su propio test.

## Gobernanza

Esta constitución tiene prioridad sobre cualquier decisión tomada durante
`/speckit-implement`. Si el agente necesita desviarse de un artículo, debe
señalarlo explícitamente y esperar aprobación antes de continuar, no
decidir en silencio.

**Version**: 1.0.0 | **Ratified**: 2026-09-22 | **Last Amended**: 2026-09-22
