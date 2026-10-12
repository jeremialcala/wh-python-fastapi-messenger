# Política de Seguridad

## Reporte de vulnerabilidades

No abras issues públicos para fallos de seguridad. Escribe al mantenedor indicado al final del
[README](README.md) con el detalle y los pasos para reproducirlo.

## Gestión de secretos

No hay gestor de secretos. La configuración vive en `config.env` en desarrollo y en un `.env` con permisos
restringidos junto al compose en el servidor; ninguno de los dos se versiona ni entra en la imagen
(`.gitignore`, `.dockerignore`). Los tokens de Meta y el `appSecret` de cada chatbot están en su documento de
MongoDB.

La clave privada con la que el gateway abre los tokens de autenticación vive en un fichero del servidor, legible
solo por la cuenta del contenedor y montado en solo lectura. De los clientes no se guarda ningún secreto: solo
la clave pública con la que firman.

Está prohibido commitear secretos. El pipeline lo comprueba: el workflow `Seguridad` escanea la historia
completa con gitleaks y rompe el build ante cualquier hallazgo.

## SBOM y supply chain (A03)

La imagen base está fijada por digest. Las dependencias de Python están fijadas con hashes en
`requirements.lock` y `requirements-dev.lock`, y la imagen y el CI instalan desde ellos. El workflow `Seguridad`
audita ese árbol con `pip-audit` en cada cambio y una vez por semana, y analiza el código con CodeQL.

Todavía no se genera SBOM: es requisito del Gate 4.

## OWASP

El mapeo de controles está en [.ai-dlc/owasp-mapping.md](.ai-dlc/owasp-mapping.md) (Top 10:2025), sin adaptar
todavía a este servicio. Los controles ya implementados están descritos en la sección Seguridad del README.
