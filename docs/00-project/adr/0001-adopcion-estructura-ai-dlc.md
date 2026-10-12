# ADR-0001: Adopción de la estructura AI-DLC (polyrepo)

* **Estado:** accepted
* **Fecha:** 2026-10-12
* **Decisores:** Jeremi Alcala
* **Fase AI-DLC:** 00-project
* **Versión:** 0.1.0
* **ID:** ADR-0001
* **Supersede:** —
* **Controles OWASP afectados:** A06 (diseño inseguro), A03 (cadena de suministro)

## Contexto

El gateway nació en 2024 como un servicio suelto: código plano en la raíz, sin requisitos escritos, sin threat
model, sin changelog y con `main` sin proteger. En octubre de 2026 se endureció el webhook y se empaquetó para
desplegarlo detrás de un hostname público, y ninguna de esas decisiones quedó registrada fuera de los mensajes de
commit y de la descripción de dos pull requests.

El servicio maneja datos personales (nombres, números de WhatsApp y contenido de mensajes) y credenciales de Meta.
Publicarlo sin un threat model ni un criterio escrito de qué debe cumplirse antes de cada paso es operar a ciegas.

## Decisión

Adoptar el estándar AI-DLC en su adaptación a polyrepo (un repositorio, un servicio):

- El código vive en `src/` y las pruebas en `tests/`, con la pirámide `unit → integration → contract → e2e → security`.
- La documentación vive en `docs/`, una carpeta por fase (`00-project` … `06-monitoring`), con los diagramas inline.
- `.ai-dlc/` contiene los checklists de los gates 0–5, las plantillas y el mapeo OWASP.
- `CHANGELOG.md` sigue Keep a Changelog 1.1.0 y SemVer 2.0.0.
- `main` queda protegida por ruleset y solo recibe pull requests desde `develop`, `release/*` o `hotfix/*`.

Los gates se cierran de forma retroactiva ("as-built") para lo que ya existe: se documenta lo construido y cada
hueco se deja visible en su checklist en vez de darlo por cumplido.

## Alternativas consideradas

| Opción | Pros | Contras | Riesgo de seguridad |
|---|---|---|---|
| Seguir con el layout plano y sin proceso | Cero trabajo | Las decisiones siguen sin registro; nada frena un despliegue inseguro | Alto: el servicio se publica sin threat model |
| Solo añadir `docs/` sin mover el código | No toca imports ni empaquetado | El repo se desvía de la plantilla y de los repos hermanos; la pirámide de pruebas no tiene sitio | Medio |
| **Estructura AI-DLC polyrepo** | Mismo estándar que los repos hermanos; el servicio de referencia de la plantilla usa los mismos paquetes | Un movimiento masivo de ficheros y gates retroactivos | Bajo |

## Consecuencias

- Positivas: cada decisión nueva tiene dónde registrarse; los gates dan un criterio explícito antes del despliegue.
- Negativas / deuda asumida: los gates 2 y 3 no se cumplen hoy (cobertura por ramas del 60 % frente al 80 %,
  dependencias de 2024, solo pruebas unitarias). Quedan abiertos, no maquillados.
- Impacto en threat model: ninguno todavía; el threat model es el primer entregable del Gate 1.

## Abierto

Decisiones que este ADR no cierra y que requieren confirmación humana:

- **Idioma.** Los artefactos AI-DLC se escriben en español, como pide el estándar; el código, el README y los
  commits siguen en inglés, como el resto del historial. Es el valor por defecto adoptado, no una decisión tomada.
- **Ubicación del repositorio.** Sigue en la cuenta personal; no se ha decidido si pasa a la organización.
- **Versionado.** Solo existe el tag `v0.0.1`. La convención del estándar corta 0.1.0 al cerrar el Gate 0 y 1.0.0
  al cerrar el Gate 5.
