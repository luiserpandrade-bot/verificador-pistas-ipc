# Contract — Tools MCP

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md) | **Date**: 2026-09-22

Las cuatro tools son las de la spec; no se añade ninguna. Cada una es un adaptador
fino sobre `app/services/pistas.py`: no reimplementa ninguna regla y llama a la
misma función que el router equivalente (Artículo VI.1, Artículo I.5, decisión
R-008). Servidor con FastMCP en `app/mcp/server.py`.

**Identidad**: si el transporte aporta un JWT verificable, la tool opera sobre ese
usuario, decodificado con la misma función que usa REST. En `stdio` sin token se
usa un usuario demo como fallback, documentado en el código como simplificación
consciente. El `usuario_id` nunca se acepta como argumento (Artículo VI.4,
Artículo IV.4, decisión R-004).

**Errores de negocio**: se devuelven como `{"error": "..."}` con un mensaje
específico, nunca como excepción sin controlar que rompa la sesión del cliente
(Artículo VI.3).

---

## `registrar_pista(nombre_red, proyecto, corriente_a, espesor_oz, capa, delta_t_c, ancho_mm)`

**Descripción (Artículo VI.2)**: "Registra una pista de PCB con su corriente,
espesor de cobre, capa, elevación de temperatura y ancho diseñado, y la rechaza si
el ancho es menor al mínimo que exige IPC-2221 para esos parámetros."

- **Service**: `services.pistas.registrar_pista()` — la misma que `POST /pistas/`
- **Éxito**: la pista registrada (mismos campos que `PistaOut`)
- **Errores**: `{"error": "..."}` por ancho insuficiente (R1), parámetros fuera de
  rango (R2) o capa inválida (R3)

## `calcular_ancho_minimo(corriente_a, espesor_oz, capa, delta_t_c)`

**Descripción**: "Calcula el ancho mínimo en milímetros que exige IPC-2221 para una
corriente, espesor de cobre, capa y elevación de temperatura dados, sin registrar
ninguna pista."

- **Service**: `services.pistas.calcular_ancho_minimo()` — la misma que
  `POST /pistas/calculo`
- **Éxito**: `{"ancho_minimo_mm": <float a 3 decimales>}`
- **Errores**: `{"error": "..."}` por parámetros fuera de rango (R2) o capa
  inválida (R3)
- **No persiste nada**

## `listar_pistas(skip, limit)`

**Descripción**: "Lista de forma paginada las pistas registradas por el usuario
autenticado, con los parámetros de desplazamiento y tamaño de página."

- **Service**: `services.pistas.listar_pistas()` — la misma que `GET /pistas/`
- **Éxito**: lista de pistas del usuario autenticado, nunca de otro (R4)
- **Defaults**: `skip=0`, `limit=20`, `limit` máximo 100 (decisión R-005)
- **Errores**: `{"error": "..."}` por paginación inválida

## `eliminar_pista(pista_id, confirmar=False)`

**Descripción**: "Elimina una pista del usuario autenticado. Requiere confirmación
explícita: sin `confirmar=True` no borra nada y devuelve qué pista se eliminaría."

- **Service**: `services.pistas.eliminar_pista()` — la misma que
  `DELETE /pistas/{id}`
- **Confirmación**: gestionada por el servidor en la propia tool, antes de llamar
  al service. Con `confirmar=False` (por defecto) devuelve la pista afectada y el
  aviso de que hay que repetir la llamada con `confirmar=True`; no depende de que
  el modelo decida preguntar (Artículo VI.5, FR-016, decisión R-003)
- **Éxito**: confirmación de borrado
- **Errores**: `{"error": "..."}` si la pista no existe o pertenece a otro usuario
  (se verifica la pertenencia antes de tocarla, Artículo IV.4)

---

## Cobertura de pruebas exigida

Cada tool tiene como mínimo un caso exitoso y un caso de error de negocio
(Artículo VII.6): 4 tools × 2 casos. Además, el caso de error 7 de la spec se
verifica sobre `calcular_ancho_minimo`: con los mismos parámetros restantes, capa
interna devuelve un ancho mayor que capa externa (0.781 mm frente a 0.300 mm para
1 A, ΔT 10 °C y 1 oz — ver `research.md` R-002).
