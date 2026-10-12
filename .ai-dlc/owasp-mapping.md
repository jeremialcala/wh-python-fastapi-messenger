# Mapeo OWASP Top 10:2025 → Controles del repo

Tabla viva. Cada requisito de seguridad de `docs/01-requirements/` referencia su fila aquí.
Los **controles por defecto** son el baseline mínimo del repo; ajústalos por servicio según su superficie de ataque.
Columnas: **Controles** (qué hacemos) · **Verificación** (herramienta/gate que lo prueba) · **Evidencia** (artefacto que demuestra cumplimiento).

> **Sin adaptar todavía (2026-10-12).** Lo que sigue es el baseline objetivo del estándar AI-DLC, copiado de la
> plantilla: describe los controles a los que el repo debe llegar, **no** evidencia de lo que ya implementa.
> Se ajusta a este servicio al cerrar los gates 0 y 1; hasta entonces ninguna fila cuenta como cumplida.

## Resumen

| ID | Riesgo | Fase / Gate principal | Verificación automatizada |
|---|---|---|---|
| A01 | Broken Access Control | 02 / Gate 1 | Tests de autorización (e2e/security) |
| A02 | Security Misconfiguration | 05 / Gate 4 | IaC scan + container scan |
| A03 | Software Supply Chain Failures | 03 / Gate 2 | SCA + SBOM + lockfiles firmados |
| A04 | Cryptographic Failures | 02 / Gate 1 | SAST cripto + revisión de diseño |
| A05 | Injection | 04 / Gate 3 | SAST + tests con payloads + DAST |
| A06 | Insecure Design | 02 / Gate 1 | Threat model STRIDE/DREAD |
| A07 | Identification & Auth Failures | 02 / Gate 1 | Tests de auth + DAST |
| A08 | Software & Data Integrity Failures | 05 / Gate 4 | Firma de artefactos + verificación CI |
| A09 | Logging & Monitoring Failures | 06 / Gate 5 | Revisión de dashboards + alertas |
| A10 | Mishandling of Exceptional Conditions | 02 / Gate 1 | Tests de error + revisión de diseño |

## A01 — Broken Access Control

**Controles por defecto**

- Autorización centralizada en la capa de aplicación (policy/guard único), **deny-by-default**.
- Control de acceso basado en roles/atributos (RBAC/ABAC) verificado server-side; nunca confiar en el cliente.
- IDs de objeto indirectos o validación de ownership en cada acceso a recurso (evita IDOR).
- Segregación de endpoints administrativos; CORS restrictivo (allowlist explícita).

**Verificación:** tests de autorización en `tests/security/` (acceso horizontal y vertical), DAST con cuentas de distinto rol.
**Evidencia:** matriz de roles × recursos en `docs/02-design/architecture.md` + reportes de tests.

## A02 — Security Misconfiguration

**Controles por defecto**

- Hardening por defecto: deshabilitar features/puertos no usados, sin credenciales por defecto.
- Configuración como código en `infra/`; sin configuración manual en producción.
- Cabeceras de seguridad (HSTS, CSP, X-Content-Type-Options, etc.) aplicadas globalmente.
- Imágenes base mínimas (distroless/alpine), usuario no-root en contenedores.

**Verificación:** IaC scan (Checkov/tfsec) + container scan (Trivy) en Gate 4.
**Evidencia:** reportes de escaneo en CI + `infra/environments/`.

## A03 — Software Supply Chain Failures *(nuevo)*

**Controles por defecto**

- SCA en cada build; bloqueo de dependencias con CVE crítico/alto.
- **SBOM** (CycloneDX/SPDX) generado y archivado por release.
- Lockfiles fijados y verificados; pin por hash cuando el ecosistema lo permita.
- Verificación de dependencias alucinadas por IA: toda dep nueva se valida contra el registro oficial (ver `guides/ai-security-controls.md`).
- Fuentes de paquetes restringidas a registros aprobados; sin instalación desde URLs arbitrarias.

**Verificación:** SCA (Trivy/Snyk) + gate de SBOM en Gate 2; secret scanning sobre lockfiles.
**Evidencia:** SBOM por build + reporte SCA + `SECURITY.md`.

## A04 — Cryptographic Failures

**Controles por defecto**

- TLS 1.2+ en tránsito; cifrado en reposo para datos Confidencial/Restringido (ver `data-classification.md`).
- Algoritmos aprobados (AES-256-GCM, SHA-256+, Argon2/bcrypt para passwords); prohibido MD5/SHA1/DES.
- Claves gestionadas en KMS/Vault; rotación definida; nunca hardcodeadas.
- Sin datos sensibles en logs, URLs ni caché.

**Verificación:** reglas SAST de criptografía + revisión de diseño en Gate 1.
**Evidencia:** sección cripto en threat model + inventario de claves.

## A05 — Injection

**Controles por defecto**

- Consultas parametrizadas / ORM con bindings; nunca concatenar input en queries.
- Validación de entrada por allowlist + output encoding contextual.
- Sanitización en fronteras (SQL, NoSQL, LDAP, OS command, template engines).

**Verificación:** SAST + tests con payloads en `tests/security/` + DAST en Gate 3.
**Evidencia:** matriz OWASP Top 10 ejecutada + reportes SAST/DAST.

## A06 — Insecure Design *(seguridad por diseño)*

**Controles por defecto**

- **Threat model STRIDE** obligatorio por sistema y por servicio con superficie relevante; priorización DREAD.
- Patrones de seguridad seleccionados por amenaza (ver `guides/design-principles.md`).
- Requisitos de abuso/negativos documentados desde Gate 0; rate limiting y límites de recursos en el diseño.

**Verificación:** revisión de threat model y ADRs en Gate 1.
**Evidencia:** `docs/02-design/` threat model + ADRs.

## A07 — Identification & Authentication Failures

**Controles por defecto**

- MFA disponible/forzado en cuentas sensibles; gestión de sesión segura (rotación, expiración, invalidación).
- Política de contraseñas + protección contra credential stuffing (rate limit, lockout progresivo).
- Tokens de corta vida + refresh seguro; almacenamiento seguro de sesión (httpOnly, SameSite).

**Verificación:** tests de auth + DAST de flujos de login/sesión en Gate 3.
**Evidencia:** ADR de autenticación + reportes de tests.

## A08 — Software & Data Integrity Failures

**Controles por defecto**

- Firma de artefactos de build y verificación en el pipeline antes de desplegar.
- Actualizaciones/CI desde fuentes confiables; verificación de integridad (hashes/firmas).
- Deserialización segura; sin deserializar datos no confiables.

**Verificación:** firma + verificación en Gate 4; SBOM (A03) como soporte.
**Evidencia:** logs de firma/verificación en CI.

## A09 — Security Logging & Monitoring Failures

**Controles por defecto**

- Tres pilares operando: métricas, logs estructurados, traces.
- Logging de eventos de seguridad (auth, acceso denegado, cambios de privilegio) sin datos sensibles.
- Dashboard de seguridad + alertas con umbrales; SLIs/SLOs definidos.

**Verificación:** revisión de dashboards, alertas y cobertura de eventos en Gate 5.
**Evidencia:** `docs/06-monitoring/` + enlaces a dashboards.

## A10 — Mishandling of Exceptional Conditions *(nuevo)*

**Controles por defecto**

- Manejo de errores fail-secure: no exponer stack traces ni detalles internos al usuario.
- Mensajes de error genéricos al exterior; detalle solo en logs internos.
- Manejo explícito de timeouts, reintentos con backoff y estados degradados.

**Verificación:** tests de rutas de error/excepción + revisión de diseño en Gate 1.
**Evidencia:** casos negativos en `tests/` + sección de manejo de errores en `docs/02-design/architecture.md`.

---
