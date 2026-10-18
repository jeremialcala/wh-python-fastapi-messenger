# 03 — Implementación (Gate 2)

El código vive en `src/`, no aquí. Esta carpeta documenta lo transversal de la implementación:

- Estándares de código (estilo, manejo de errores, logging).
- `repo-history.md`: grafo e historial del repositorio, derivados de `git log` y nunca escritos a mano.
- Evidencia de SAST, SCA, escaneo de secretos y cobertura.

Cierra con `.ai-dlc/gates/gate-2-implementation.md`: SAST limpio, dependencias verificadas, cobertura por ramas
de al menos el 80 %, dual review y ningún secreto en el código.

- [autenticacion.md](autenticacion.md): cómo llama un cliente al servicio y cómo lo opera el operador.
- [cifrado-de-datos.md](cifrado-de-datos.md): qué se cifra, con qué claves y cómo se opera.
- [exportar-y-borrar.md](exportar-y-borrar.md): cómo se atiende a quien pide sus datos, y qué borra la baja de un bot o
  de un cliente.
- [revision-dual-gate-2.md](revision-dual-gate-2.md): la parte de la IA de la revisión dual del Gate 2, con cada
  hallazgo y su estado.
