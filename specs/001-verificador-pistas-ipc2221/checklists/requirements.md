# Specification Quality Checklist: Verificador de pistas de PCB según IPC-2221

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [ ] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [ ] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
- [ ] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [ ] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [ ] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [ ] No implementation details leak into specification

## Notes

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

### Estado de los ítems no marcados

Los seis ítems sin marcar no son defectos accidentales: fallan por decisiones
explícitas del usuario al encargar esta especificación. No se corrigieron porque
hacerlo contradiría esas instrucciones. Quedan documentados aquí para revisión
humana.

1. **No implementation details (languages, frameworks, APIs)** y **No
   implementation details leak into specification**: el usuario pidió conservar
   tal cual la tabla del contrato REST (métodos, rutas, códigos de estado) y el
   contrato MCP (firmas de las tools). Ambas secciones son detalle de interfaz y
   hacen fallar estos dos ítems por diseño.
2. **Written for non-technical stakeholders**: las historias de usuario, las
   reglas de negocio y los criterios de éxito sí son legibles sin perfil
   técnico, pero las secciones de contrato REST/MCP y el cálculo de referencia
   no lo son. Se conservan por la misma instrucción del punto anterior.
3. **No [NEEDS CLARIFICATION] markers remain**: la especificación conserva
   textualmente cuatro marcas `[NECESITA CLARIFICACIÓN]` (en R1, R2, R5 y el
   cálculo de referencia) por indicación explícita del usuario, que las
   responderá con `/speckit-clarify`. Esto excede además el límite de 3 marcas
   que sugiere la plantilla de `/speckit-specify`; no se descartó ninguna porque
   el usuario pidió las cuatro.
4. **Requirements are testable and unambiguous** y **All functional requirements
   have clear acceptance criteria**: FR-006, FR-007 y FR-012 dependen de R1, R2
   y R5, que están pendientes de clarificación (umbral exacto de aceptación,
   límites del rango de validez y comportamiento ante una actualización que deja
   la pista fuera de norma). Serán verificables en cuanto se resuelvan esas
   cuatro marcas.
5. **Success criteria are technology-agnostic**: SC-004 nombra las dos
   interfaces (REST y MCP) porque la equivalencia de comportamiento entre ambas
   es en sí un requisito del borrador, no un detalle de implementación
   accesorio. El resto de criterios (SC-001, SC-002, SC-003, SC-005, SC-006) sí
   es agnóstico.

### Desviaciones respecto al flujo estándar de la skill

- La skill indica presentar las marcas pendientes como preguntas con opciones
  A/B/C y esperar respuesta del usuario antes de continuar. No se hizo: el
  usuario indicó expresamente que las cuatro marcas se conservan sin resolver y
  se responderán con `/speckit-clarify`.
- No se ejecutó ninguna iteración de corrección automática sobre los ítems
  fallidos, porque cada uno de ellos falla por una instrucción explícita del
  usuario y corregirlo significaría desobedecerla.
