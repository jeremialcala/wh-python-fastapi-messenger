# Gate 1 — Diseño (cierre de Fase 02)

- [ ] Arquitectura C4 validada (`docs/02-design/`)
- [ ] Threat model STRIDE de sistema + servicios con superficie relevante
- [ ] ADRs registrados para decisiones clave
- [ ] Contratos de API definidos
- [ ] Patrones de seguridad seleccionados por amenaza priorizada (DREAD)

## Estado (2026-10-12): sin empezar

Ya existen cuatro ADR de diseño, aceptados durante el Gate 0: ADR-0002 a ADR-0005, en `docs/00-project/adr/`.

## Heredado del Gate 0

Decisiones de diseño que el Gate 0 dejó fijadas como requisito y sin resolver:

1. **Parámetros del token de autenticación** (RS02): algoritmos permitidos, contenido obligatorio del JWT, duración,
   y registro y rotación de las claves públicas.
2. **Contrato de la cola** (RF12): un AsyncAPI común con el motor de respuestas.
3. **Custodia de la clave de cifrado de datos** (RS05, RS06): qué clave cifra los datos de cada cliente, quién la
   genera y dónde vive.

Además, el gate exige la ADR de placement por componente y el contrato OpenAPI de la API HTTP.
