# Política de Seguridad

## Reporte de vulnerabilidades

No abras issues públicos para fallos de seguridad. Escribe al mantenedor indicado al final del
[README](README.md) con el detalle y los pasos para reproducirlo.

## Gestión de secretos

No hay gestor de secretos. La configuración vive en `config.env` en desarrollo y en un `.env` con permisos
restringidos junto al compose en el servidor; ninguno de los dos se versiona ni entra en la imagen
(`.gitignore`, `.dockerignore`). Los tokens de Meta y el `appSecret` de cada chatbot están en su documento de
MongoDB.

Está prohibido commitear secretos. El escaneo automático de secretos en el pipeline está pendiente (Gate 2).

## SBOM y supply chain (A03)

La imagen base está fijada por digest. Las dependencias de Python **no** están fijadas con lockfile ni hashes, y
todavía no se genera SBOM ni se ejecuta SCA: son requisitos de los gates 2 y 4, aún abiertos.

## OWASP

El mapeo de controles está en [.ai-dlc/owasp-mapping.md](.ai-dlc/owasp-mapping.md) (Top 10:2025), sin adaptar
todavía a este servicio. Los controles ya implementados están descritos en la sección Security del README.
