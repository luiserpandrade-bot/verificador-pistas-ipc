# Feature Specification: Verificador de pistas de PCB según IPC-2221

**Feature Branch**: `main` (sin rama dedicada: no hay hook `before_specify` registrado en este proyecto)

**Created**: 2026-09-22

**Status**: Draft

**Input**: User description: "Genera la especificación de la funcionalidad usando como fuente el archivo spec-borrador.md de la raíz. Conserva las entidades, las cinco reglas de negocio, la tabla del contrato REST, el contrato MCP y los siete casos de error tal como están. Conserva textualmente las cuatro marcas las marcas de clarificación sin resolverlas ni eliminarlas: se responderán con /speckit-clarify. No inventes requisitos, endpoints ni entidades que no estén en el borrador."

Sistema que permite a un diseñador registrar las pistas de sus diseños de PCB y
verificar automáticamente si el ancho de cada pista cumple el mínimo exigido por
la ecuación de IPC-2221 para la corriente que va a conducir.

## Clarifications

### Session 2026-09-22

- Q: ¿Un ancho exactamente igual al mínimo calculado se acepta, o se exige un margen de seguridad? → A: Se acepta. La comparación es `ancho_mm >= minimo_mm`, sin margen de seguridad adicional; el margen lo decide el diseñador eligiendo un ΔT conservador.
- Q: ¿Cuáles son los límites exactos de corriente, ΔT y espesor, y una entrada fuera de rango se rechaza con error o se acepta con una advertencia en la respuesta? → A: `corriente_a` mayor que 0 y hasta 35 A; `delta_t_c` entre 10 y 100 °C inclusive; `espesor_oz` entre 0.5 y 3 oz inclusive. Fuera de ese rango se rechaza con error de regla de negocio (400); nunca se acepta con advertencia.
- Q: ¿Con cuántos decimales y con qué tolerancia se compara el ancho diseñado contra el mínimo calculado, para evitar falsos rechazos por redondeo? → A: Se compara en milímetros con tolerancia absoluta de 0.001 mm a favor del diseñador, es decir `ancho_mm >= minimo_mm - 0.001`. El ancho mínimo se reporta redondeado a 3 decimales.
- Q: Si una actualización deja la pista fuera de norma, ¿se rechaza la actualización completa o se guarda marcada como no conforme? → A: Se rechaza la actualización completa con 400 y la pista conserva sus valores anteriores. No existe un estado "no conforme" almacenado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar una pista y saber si cumple la norma (Priority: P1)

Un diseñador con cuenta en el sistema registra una pista de su diseño indicando
la red a la que pertenece, el proyecto, la corriente que conducirá, el espesor
de cobre, si va en capa externa o interna, la elevación de temperatura admisible
y el ancho que diseñó. El sistema le responde si la pista queda aceptada o la
rechaza por no alcanzar el ancho mínimo que exige IPC-2221 para esos parámetros.

**Why this priority**: es la razón de existir del sistema. Sin esta historia no
hay verificación y el resto de funciones no aporta valor por sí solo.

**Independent Test**: se puede probar por completo registrando una pista con
ancho suficiente (queda aceptada) y otra con ancho insuficiente para la misma
corriente (queda rechazada), sin necesitar listados, actualizaciones ni la
consulta de cálculo.

**Acceptance Scenarios**:

1. **Given** un diseñador autenticado, **When** registra una pista cuyo ancho
   diseñado es mayor o igual al mínimo de IPC-2221 para su corriente, espesor,
   capa y ΔT, **Then** la pista queda registrada y asociada a ese diseñador.
2. **Given** un diseñador autenticado, **When** registra una pista cuyo ancho
   diseñado es menor al mínimo de IPC-2221 para esos parámetros, **Then** la
   pista se rechaza con un error de regla de negocio y no queda registrada.
3. **Given** un diseñador autenticado, **When** registra una pista con
   parámetros fuera del rango de validez del modelo, **Then** la solicitud se
   rechaza y el resultado no se extrapola en silencio.
4. **Given** un diseñador autenticado, **When** registra una pista indicando una
   capa distinta de externa o interna, **Then** la entrada se rechaza como
   inválida.

---

### User Story 2 - Consultar el ancho mínimo antes de decidir (Priority: P2)

Antes de fijar el ancho de una pista en su diseño, el diseñador consulta qué
ancho mínimo exige IPC-2221 para una corriente, espesor, capa y ΔT dados. La
consulta no registra nada: solo informa.

**Why this priority**: evita el ciclo de prueba y error de registrar pistas para
descubrir que se rechazan, pero el sistema ya es útil sin ella.

**Independent Test**: se puede probar pidiendo el ancho mínimo para un conjunto
de parámetros y comprobando que no se creó ninguna pista como efecto de la
consulta.

**Acceptance Scenarios**:

1. **Given** un diseñador autenticado, **When** consulta el ancho mínimo para
   una corriente, espesor, capa y ΔT válidos, **Then** recibe el ancho mínimo en
   milímetros y no se persiste ninguna pista.
2. **Given** los mismos parámetros de corriente, espesor y ΔT, **When** consulta
   el ancho mínimo para capa interna y para capa externa, **Then** el ancho
   devuelto para capa interna es mayor que el de capa externa.
3. **Given** un diseñador autenticado, **When** consulta el ancho mínimo con
   parámetros fuera del rango de validez, **Then** la consulta se rechaza.

---

### User Story 3 - Gestionar las pistas propias (Priority: P3)

El diseñador lista sus pistas de forma paginada, consulta una pista concreta,
modifica los parámetros de una pista existente y elimina las que ya no
necesita. Solo ve y toca sus propias pistas.

**Why this priority**: es la gestión del histórico. Aporta valor acumulado, pero
la verificación (P1) y la consulta previa (P2) ya entregan el núcleo.

**Independent Test**: se puede probar con dos diseñadores distintos, cada uno
listando y modificando sus pistas y comprobando que no alcanza las del otro ni
pasando el identificador ajeno de forma manual.

**Acceptance Scenarios**:

1. **Given** un diseñador con varias pistas registradas, **When** solicita su
   listado con paginación, **Then** recibe únicamente sus pistas.
2. **Given** una pista que pertenece a otro diseñador, **When** intenta leerla,
   modificarla o eliminarla pasando su identificador, **Then** la operación se
   deniega.
3. **Given** una pista propia, **When** la actualiza con valores que dejarían el
   ancho por debajo del mínimo de IPC-2221, **Then** la actualización completa se
   rechaza y la pista conserva sus valores anteriores.
4. **Given** una pista propia, **When** la elimina, **Then** deja de aparecer en
   su listado.

---

### Edge Cases

- Un ancho diseñado exactamente igual al ancho mínimo calculado se acepta: la
  comparación es `>=`, sin margen de seguridad adicional (R1).
- Los extremos del rango de validez se aceptan: `delta_t_c` de 10 °C y de
  100 °C, y `espesor_oz` de 0.5 oz y de 3 oz son válidos. `corriente_a` debe ser
  estrictamente mayor que 0 y como máximo 35 A. Un valor justo por fuera de
  cualquiera de esos límites se rechaza con 400 (R2).
- Una diferencia de hasta 0.001 mm por debajo del mínimo calculado no provoca
  rechazo: la tolerancia absoluta de 0.001 mm juega a favor del diseñador y
  evita falsos rechazos por redondeo.
- Una actualización que dejaría la pista fuera de norma se rechaza por completo
  con 400 y la pista conserva sus valores anteriores; no queda almacenada como
  no conforme (R5).
- ¿Cómo se comporta el sistema cuando se opera sobre una pista que no existe?
- ¿Cómo se comporta el sistema cuando se opera sin identidad autenticada?
- ¿Cómo se comporta la herramienta de eliminación por MCP si no se obtiene la
  confirmación exigida?

## Requirements *(mandatory)*

### Reglas de negocio

- **R1 — Ancho suficiente**: el ancho diseñado de una pista debe ser mayor o
  igual al ancho mínimo que resulta de la ecuación de IPC-2221 para su
  corriente, espesor, capa y ΔT. Si es menor, la pista se rechaza. Un ancho
  exactamente igual al mínimo calculado se acepta: la comparación es
  `ancho_mm >= minimo_mm`, aplicada con la tolerancia declarada en el apartado
  de cálculo de referencia, y no se exige ningún margen de seguridad adicional.
  El margen lo decide el diseñador eligiendo un ΔT conservador.
- **R2 — Rango de validez del modelo**: los parámetros deben estar dentro del
  rango en el que la ecuación de IPC-2221 es aplicable. Ese rango es:
  `corriente_a` mayor que 0 y hasta 35 A; `delta_t_c` entre 10 y 100 °C
  inclusive; `espesor_oz` entre 0.5 y 3 oz inclusive. Una entrada fuera de ese
  rango se rechaza con error de regla de negocio (400) y nunca se acepta con
  una advertencia en la respuesta: el resultado no se extrapola en silencio.
- **R3 — Constante según la capa**: el cálculo usa k = 0.048 para capa externa
  y k = 0.024 para capa interna. Una capa distinta de esas dos es inválida.
- **R4 — Aislamiento por usuario**: un usuario solo puede leer, modificar o
  eliminar sus propias pistas, sin importar qué identificador se pase en la
  solicitud.
- **R5 — Revalidación al modificar**: al actualizar una pista se vuelven a
  verificar R1, R2 y R3 con los valores resultantes. Si el resultado queda fuera
  de norma, la actualización completa se rechaza con 400 y la pista conserva sus
  valores anteriores; no existe un estado "no conforme" almacenado.

### Functional Requirements

- **FR-001**: El sistema MUST permitir que una persona se registre como usuario
  con un email único y una contraseña, y MUST rechazar el registro si el email
  ya está registrado.
- **FR-002**: El sistema MUST no exponer nunca la contraseña de un usuario en
  ninguna respuesta.
- **FR-003**: El sistema MUST permitir que un usuario registrado obtenga una
  credencial de sesión presentando su email y contraseña, y MUST rechazar
  credenciales inválidas.
- **FR-004**: El sistema MUST exigir identidad autenticada para toda operación
  sobre pistas y para la consulta de ancho mínimo.
- **FR-005**: Los usuarios MUST poder registrar una pista indicando nombre de
  red, proyecto, corriente en amperios, espesor de cobre en onzas, capa,
  elevación de temperatura admisible en °C y ancho diseñado en milímetros.
- **FR-006**: Al registrar una pista, el sistema MUST aplicar R1 y rechazar la
  pista cuyo ancho diseñado no alcance el mínimo de IPC-2221.
- **FR-007**: Al registrar una pista o al calcular un ancho mínimo, el sistema
  MUST aplicar R2 y no extrapolar en silencio parámetros fuera del rango de
  validez del modelo.
- **FR-008**: El sistema MUST aplicar R3: usar k = 0.048 para capa externa y
  k = 0.024 para capa interna, y tratar cualquier otra capa como entrada
  inválida.
- **FR-009**: El sistema MUST aplicar R4: derivar el usuario propietario de la
  identidad autenticada y nunca de un identificador recibido en la solicitud,
  tanto al listar como al leer, modificar o eliminar una pista concreta.
- **FR-010**: Los usuarios MUST poder listar sus pistas de forma paginada
  mediante los parámetros `skip` y `limit`.
- **FR-011**: Los usuarios MUST poder leer una pista propia por su
  identificador.
- **FR-012**: Los usuarios MUST poder actualizar los campos de una pista
  propia, y el sistema MUST aplicar R5 revalidando R1, R2 y R3 con los valores
  resultantes.
- **FR-013**: Los usuarios MUST poder eliminar una pista propia.
- **FR-014**: Los usuarios MUST poder obtener el ancho mínimo exigido para una
  corriente, espesor, capa y ΔT dados sin que esa consulta persista nada.
- **FR-015**: El sistema MUST exponer por MCP las mismas reglas de negocio que
  por REST para registrar una pista, calcular el ancho mínimo, listar pistas y
  eliminar una pista, operando sobre el usuario autenticado de la sesión MCP.
- **FR-016**: La herramienta MCP de eliminación MUST exigir una confirmación
  gestionada por el servidor antes de ejecutar, y MUST verificar que la pista
  pertenece al usuario.
- **FR-017**: El sistema MUST recibir y devolver anchos en milímetros.

### Key Entities *(include if feature involves data)*

- **Usuario**: email (único), contraseña (nunca expuesta en respuestas).
- **Pista**: nombre de red, proyecto (texto libre), corriente en amperios,
  espesor de cobre en onzas, capa (externa o interna), elevación de temperatura
  admisible en °C, ancho diseñado en milímetros. Pertenece a un usuario.

## Cálculo de referencia (IPC-2221)

`I = k · ΔT^0.44 · A^0.725`, con I en amperios, ΔT en °C y A (área de sección)
en mils². De ahí: `A = (I / (k · ΔT^0.44))^(1/0.725)` y
`ancho_mils = A / (espesor_oz · 1.378)`. El resultado se convierte a milímetros
multiplicando por 0.0254.

Se usa IPC-2221 y no IPC-2152 porque esta última, siendo la norma vigente y más
precisa, se basa en gráficas sin ecuación cerrada. La decisión queda declarada.

La comparación entre el ancho diseñado y el mínimo calculado se hace en
milímetros, con una tolerancia absoluta de 0.001 mm a favor del diseñador:
`ancho_mm >= minimo_mm - 0.001`. El ancho mínimo se reporta redondeado a 3
decimales.

## Contrato de la API (REST)

| Método | Ruta | Auth | Request | Éxito | Errores esperados |
|--------|------|------|---------|-------|-------------------|
| POST | /auth/registro | No | email, contraseña | 201 Usuario | 400 email ya registrado, 422 |
| POST | /auth/token | No | email, contraseña | 200 token | 401 credenciales inválidas, 422 |
| POST | /pistas/ | Sí | nombre_red, proyecto, corriente_a, espesor_oz, capa, delta_t_c, ancho_mm | 201 Pista | 400 ancho insuficiente, 400 fuera de rango, 401, 422 |
| GET | /pistas/ | Sí | query: skip, limit | 200 lista | 401, 422 |
| GET | /pistas/{id} | Sí | — | 200 Pista | 401, 403 no es dueño, 404 |
| PATCH | /pistas/{id} | Sí | campos a modificar | 200 Pista | 400 ancho insuficiente, 401, 403, 404, 422 |
| DELETE | /pistas/{id} | Sí | — | 204 | 401, 403 no es dueño, 404 |
| POST | /pistas/calculo | Sí | corriente_a, espesor_oz, capa, delta_t_c | 200 ancho mínimo | 400 fuera de rango, 401, 422 |

`POST /pistas/calculo` no persiste nada: devuelve el ancho mínimo para esos
parámetros, para consultarlo antes de decidir el ancho de una pista.

## Contrato equivalente por MCP

- Tool `registrar_pista(nombre_red, proyecto, corriente_a, espesor_oz, capa, delta_t_c, ancho_mm)`:
  mismas reglas que `POST /pistas/`, operando sobre el usuario autenticado de la
  sesión MCP.
- Tool `calcular_ancho_minimo(corriente_a, espesor_oz, capa, delta_t_c)`: mismo
  comportamiento que `POST /pistas/calculo`, sin persistir nada.
- Tool `listar_pistas(skip, limit)`: mismo comportamiento que `GET /pistas/`.
- Tool `eliminar_pista(pista_id)`: exige confirmación gestionada por el servidor
  antes de ejecutar, y verifica que la pista pertenece al usuario.

## Casos de error explícitos que deben tener test

1. Registrar una pista cuyo ancho es menor al mínimo de IPC-2221 → 400.
2. Registrar una pista con parámetros fuera del rango de validez → 400.
3. Registrar una pista con una capa distinta de externa o interna → 422.
4. Listar o registrar pistas sin token → 401.
5. Leer, modificar o eliminar una pista de otro usuario pasando su ID
   manualmente → 403.
6. Operar sobre una pista inexistente → 404.
7. `calcular_ancho_minimo` con capa interna devuelve un ancho mayor que con
   capa externa para los mismos parámetros restantes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: el 100% de las pistas cuyo ancho diseñado es insuficiente para la
  corriente declarada se rechazan en el momento del registro, sin quedar
  guardadas.
- **SC-002**: el 100% de las entradas con parámetros fuera del rango de validez
  del modelo se resuelven según la regla declarada, sin devolver nunca un
  resultado extrapolado en silencio.
- **SC-003**: ningún usuario consigue leer, modificar ni eliminar una pista
  ajena en ninguno de los intentos, incluso pasando el identificador ajeno de
  forma manual (0 fugas entre usuarios).
- **SC-004**: para los mismos parámetros de entrada, la verificación por MCP y
  la verificación por la API REST dan el mismo veredicto en el 100% de los
  casos.
- **SC-005**: un diseñador puede conocer el ancho mínimo exigido para un juego
  de parámetros sin registrar ninguna pista, en una sola consulta.
- **SC-006**: los 7 casos de error explícitos de este documento están cubiertos
  por al menos una prueba automatizada cada uno.

## Assumptions

- Las cuatro clarificaciones que quedaban pendientes (en R1, R2, R5 y el cálculo
  de referencia) fueron decididas y registradas en `## Clarifications`
  (Session 2026-09-22): umbral de aceptación, límites del rango de validez,
  tolerancia de comparación y comportamiento de una actualización fuera de
  norma. Ya no hay decisiones abiertas en esas cuatro áreas.
- El alcance es exactamente el del borrador: no se añaden entidades, endpoints,
  herramientas MCP ni requisitos que el borrador no contenga. En particular, no
  se asume recuperación de contraseña, roles, compartición de pistas entre
  usuarios, importación de archivos de diseño ni informes agregados.
- Se usa IPC-2221 y no IPC-2152, con la justificación declarada en el apartado
  de cálculo de referencia; esa decisión no se revisa en esta funcionalidad.
- El sistema recibe y devuelve anchos en milímetros; la conversión a mils es un
  detalle interno del cálculo y no se le exige al cliente.
- Cada pista pertenece a un único usuario y el propietario se deriva siempre de
  la identidad autenticada.
- Los valores por defecto de la paginación (`skip`, `limit`) se fijarán en la
  planificación; el borrador solo exige que ambos parámetros existan.
