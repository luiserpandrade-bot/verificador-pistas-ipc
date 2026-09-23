# Phase 0 — Research: Verificador de pistas de PCB según IPC-2221

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-22

Este documento resuelve las incógnitas del Technical Context del plan y fija las
decisiones técnicas, cada una citando el artículo de
`.specify/memory/constitution.md` que la justifica. Las cuatro reglas que estaban
abiertas en la spec (R1, R2, R5 y la tolerancia de comparación) ya fueron
decididas en `## Clarifications` y aquí solo se traducen a diseño.

---

## R-001 — Ubicación del cálculo de IPC-2221

**Decision**: el cálculo vive en `app/utils/ipc2221.py` como función pura
`ancho_minimo_mm(corriente_a, espesor_oz, capa, delta_t_c) -> float`, sin importar
nada de `services/`, `routers/` ni `repositories/`, y sin efectos secundarios. La
decisión de aceptar o rechazar una pista con ese resultado vive en
`app/services/pistas.py`. El módulo concentra además todas las constantes de la
norma: `K_POR_CAPA` (0.048 externa / 0.024 interna), los exponentes 0.44 y 0.725,
el factor 1.378 de oz→mils y el 0.0254 de mils→mm; ningún otro módulo las
redefine.

**Rationale**: Artículo I.4 exige exactamente este corte (función pura en
`utils/`, decisión en `services/`) y el Artículo VIII.3 exige una única fuente de
las constantes. Ser función pura es lo que hace que el Artículo VII.7 sea
verificable con valores calculados a mano, sin base de datos ni HTTP.

**Alternatives considered**: (a) calcular dentro del service — rechazado: viola
I.4 y obliga a montar el contexto del service para probar aritmética; (b) un
módulo `domain/` aparte — rechazado: la constitución nombra `utils/` como el
lugar de las funciones puras, y añadir una capa no prevista rompería el Artículo
I sin necesidad.

---

## R-002 — Valores de referencia para verificar el cálculo

**Decision**: el test unitario del cálculo se ancla en valores calculados a mano y
documentados en el propio test, con tolerancia declarada de ±0.001 mm:

| Corriente | ΔT | Espesor | Capa | A (mils²) | Ancho (mils) | Ancho (mm) | Redondeado |
|-----------|-----|---------|------|-----------|--------------|------------|------------|
| 1 A | 10 °C | 1 oz | externa | 16.2960 | 11.8258 | 0.300376 | 0.300 |
| 1 A | 10 °C | 1 oz | interna | 42.3931 | 30.7642 | 0.781411 | 0.781 |
| 5 A | 20 °C | 1 oz | externa | 98.5107 | 71.4882 | 1.815800 | 1.816 |
| 35 A | 100 °C | 3 oz | externa | 543.1672 | 131.3902 | 3.337312 | 3.337 |

El primer caso coincide con el valor de referencia que la propia constitución cita
(1 A, ΔT 10 °C, 1 oz, capa externa ≈ 0,30 mm). El segundo y el primero juntos
cubren el caso de error 7 de la spec: con los mismos parámetros, capa interna
(0.781 mm) exige más ancho que capa externa (0.300 mm).

**Rationale**: Artículo VII.7 exige valores de referencia calculados a mano,
documentados en el test y con tolerancia declarada.

**Alternatives considered**: comparar contra una segunda implementación del mismo
cálculo — rechazado: un error en la ecuación se replicaría en ambas y el test no
detectaría nada.

---

## R-003 — Confirmación de la tool destructiva por MCP

**Decision**: `eliminar_pista(pista_id, confirmar: bool = False)` no borra nada si
`confirmar` no es `True`: devuelve una estructura que describe la pista afectada y
exige repetir la llamada con `confirmar=True`. La comprobación la hace el servidor
en la propia tool, antes de llamar al service de borrado, y además se verifica que
la pista pertenece al usuario.

**Rationale**: Artículo VI.5 exige que la confirmación sea gestionada por el
servidor y no dependa de que el modelo decida preguntar; FR-016 lo recoge. El
Artículo IV.4 obliga a verificar pertenencia antes de tocar el recurso.

**Alternatives considered**: (a) confiar en que el cliente MCP pida confirmación —
rechazado explícitamente por VI.5; (b) borrado en dos fases con un token temporal
— rechazado: añade estado en el servidor sin que la spec lo pida.

---

## R-004 — Identidad del usuario en la sesión MCP

**Decision**: `app/mcp/auth.py` resuelve la identidad así: si el transporte
aporta un token JWT verificable, se usa **ese** usuario, decodificado con la misma
función que usa REST (`app/utils/seguridad.py`). Si el transporte es `stdio` y no
hay ningún token disponible, se usa un usuario demo como fallback, documentado con
un comentario explícito en el código como simplificación consciente. Nunca se
acepta un `usuario_id` recibido como argumento de una tool.

**Rationale**: Artículo VI.4 describe este comportamiento literalmente, incluida
la obligación de documentar el fallback y de no hardcodear un usuario demo cuando
sí hay token. Artículo IV.4 prohíbe tomar la identidad de un parámetro.

**Alternatives considered**: exigir token siempre, también en `stdio` — rechazado:
haría inusable el servidor en el transporte que la constitución contempla; el
fallback documentado es la salida que ella misma autoriza.

---

## R-005 — Valores por defecto de la paginación

**Decision**: `skip=0`, `limit=20` por defecto, con `limit` máximo 100 y ambos
validados en el schema (`skip >= 0`, `1 <= limit <= 100`). Un valor negativo o no
numérico es error de schema (422), no de negocio.

**Rationale**: la spec dejó los valores por defecto a la planificación y el
Artículo V.2 exige que existan `skip` y `limit` con valores razonables y que los
inválidos sean 422. El tope de 100 evita que un listado degenere en una descarga
completa sin que haga falta una regla de negocio nueva.

**Alternatives considered**: sin tope superior — rechazado: deja el coste del
listado en manos del cliente; paginación por cursor — rechazado: la spec fija
`skip`/`limit` y cambiarlo sería inventar contrato.

---

## R-006 — Objetivos de rendimiento y escala (incógnitas del Technical Context)

**Decision**: no se fijan objetivos numéricos de latencia ni de throughput. El
alcance operativo asumido es uso individual por diseñador, del orden de cientos a
miles de pistas por usuario, con paginación obligatoria en el listado. El único
requisito de rendimiento derivable es que la verificación no añada trabajo
apreciable: el cálculo es aritmética de coma flotante sin E/S ni consultas.

**Rationale**: la spec no declara métricas de rendimiento y sus criterios de éxito
(SC-001 a SC-006) son de corrección, no de velocidad. Inventar un objetivo de
latencia sería añadir un requisito que el borrador no contiene. Queda registrado
como área Outstanding de bajo impacto, tal como se reportó en `/speckit-clarify`.

**Alternatives considered**: fijar un p95 arbitrario (por ejemplo 200 ms) —
rechazado: número sin origen en la spec y no verificable como valor de negocio.

---

## R-007 — Inyección del repositorio en los services

**Decision**: cada función de `app/services/` que necesite persistencia recibe el
repositorio como último parámetro con valor por defecto, por ejemplo
`def registrar_pista(datos, usuario_id, repo: PistasRepo = pistas_repo)`. El
contrato del repositorio se expresa como `typing.Protocol` en
`app/repositories/pistas.py`, y el módulo del repositorio real es un objeto con
funciones de persistencia. Los services nunca importan `Session` ni SQLAlchemy.

**Rationale**: Artículo II.3 lo declara innegociable y explica el motivo: es lo
que permite testear sin `unittest.mock`. El Artículo VII.2 lo cierra prohibiendo
`unittest.mock` para sustituir el repositorio, y el Artículo I.2 prohíbe que el
service conozca la persistencia.

**Alternatives considered**: (a) `Depends()` de FastAPI dentro del service —
rechazado: acopla el service al framework web y lo vuelve inservible desde MCP;
(b) una clase service con el repositorio inyectado en `__init__` — rechazado: el
Artículo II.4 pide no introducir jerarquías que el proyecto no necesita, y el
parámetro con valor por defecto ya cumple DIP.

---

## R-008 — Reutilización entre REST y MCP

**Decision**: las cuatro tools de `app/mcp/tools/pistas.py` son adaptadores finos:
traducen argumentos, llaman a la función de `app/services/pistas.py`
correspondiente y convierten el resultado o la excepción de dominio en una
estructura serializable. `registrar_pista` (tool) y `POST /pistas/` (router)
llaman a la misma `services.pistas.registrar_pista()`. Ninguna regla se escribe
dos veces; si una tool necesitara lógica que no existe, se añade primero al
service.

**Rationale**: Artículo VI.1 y Artículo I.5 lo exigen en esos términos. Es también
lo que hace verificable SC-004 (mismo veredicto por REST y por MCP).

**Alternatives considered**: que la tool llame al endpoint HTTP por red —
rechazado: duplica serialización y autenticación, y crea dependencia de que el
servidor web esté levantado.

---

## R-009 — Errores de negocio y su traducción a cada interfaz

**Decision**: los services lanzan excepciones de dominio propias
(`AnchoInsuficienteError`, `FueraDeRangoError`, `PistaNoEncontradaError`,
`PistaAjenaError`) definidas sin dependencias de FastAPI. Los routers las traducen
a 400, 404 y 403 según la tabla de contrato de la spec; las tools MCP las traducen
a `{"error": "..."}`. Cualquier `Exception` no prevista se convierte en 500 con
`{"detail": "Error interno del servidor"}` por un manejador global, y el detalle
real se loguea internamente.

**Rationale**: Artículo I.1 (el router traduce, no decide), Artículo IV.5 (500 sin
stack trace al cliente, detalle logueado), Artículo VI.3 (error de negocio como
estructura clara, nunca excepción sin controlar que rompa la sesión MCP) y
Artículo V.1 (qué código corresponde a cada caso).

**Alternatives considered**: lanzar `HTTPException` desde el service — rechazado:
haría que el service dependa del framework web y que la tool MCP reciba un error
HTTP que no sabe interpretar, violando I.2 y VI.1.

---

## R-010 — Tolerancia y redondeo en la comparación

**Decision**: la comparación es `ancho_mm >= minimo_mm - 0.001`, en milímetros, y
el ancho mínimo se reporta redondeado a 3 decimales. La constante de tolerancia
(`TOLERANCIA_MM = 0.001`) vive junto a las demás constantes de la norma en
`app/utils/ipc2221.py`; la comparación en sí la hace el service.

**Rationale**: es la decisión registrada en `## Clarifications` de la spec. El
Artículo VIII.3 pide que las constantes no se repitan, y el Artículo I.4 mantiene
la comparación (una decisión) en el service.

**Alternatives considered**: comparar valores ya redondeados a 3 decimales —
rechazado: el redondeo puede mover el umbral en ambos sentidos, mientras que la
tolerancia explícita siempre juega a favor del diseñador, que es lo decidido.

---

## R-011 — Alcance de lo que se persiste y se expone

**Decision**: se persisten exactamente los atributos que la spec declara en Key
Entities. No se almacena el ancho mínimo calculado, ni un estado de conformidad,
ni marcas de tiempo, y `PistaOut` no añade campos que la spec no nombre. El ancho
mínimo se obtiene cuando se necesita, llamando a la función pura, o con
`POST /pistas/calculo`.

**Rationale**: la spec fija las entidades y el encargo prohíbe inventar entidades
o requisitos. Para R5 esto es coherente: al rechazarse la actualización completa
con 400, no existe ningún estado "no conforme" que hubiera que almacenar.

**Alternatives considered**: guardar `ancho_minimo_mm` como columna derivada —
rechazado: sería un atributo nuevo no declarado, y quedaría obsoleto si cambiaran
las constantes. Si se quisiera exponer, es un cambio de spec, no del plan.
