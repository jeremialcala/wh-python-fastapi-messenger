"""Regenera docs/02-design/contracts/openapi.yaml a partir de la aplicación.

El contrato OpenAPI no se escribe a mano: se deriva de `app.openapi()`. Ejecutar desde la raíz del repositorio:

    python .ai-dlc/scripts/gen_openapi.py

No necesita `config.env` ni servicios: usa los ajustes de prueba de `tests/conftest.py`.
`tests/contract/test_openapi_contract.py` falla si el fichero versionado deja de coincidir con la aplicación.
"""
import pathlib
import runpy
import sys

import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "docs" / "02-design" / "contracts" / "openapi.yaml"

# Los DTO generan sus valores por defecto y sus ejemplos con Faker y random al importarse, así que cambian en cada
# arranque. Se quitan del contrato para que este sea estable y comparable.
VOLATILES = {"default", "examples", "example"}

CABECERA = """\
# Contrato OpenAPI del gateway (fase 02-design, Gate 1). Refleja la API tal como está construida.
# Generado con .ai-dlc/scripts/gen_openapi.py: regenerar, no editar a mano.
# Sin valores por defecto ni ejemplos: en el código son aleatorios y cambian en cada arranque.
# No declara esquemas de seguridad porque la aplicación no los declara: la cabecera X-API-Key y la firma
# X-Hub-Signature-256 se comprueban en dependencias que OpenAPI no ve.
"""


def normalizar(nodo, en_propiedades=False):
    """Devuelve el nodo sin las claves volátiles. Los nombres de propiedad de un esquema nunca se quitan."""
    if isinstance(nodo, dict):
        return {
            clave: normalizar(valor, en_propiedades=(clave == "properties"))
            for clave, valor in nodo.items()
            if en_propiedades or clave not in VOLATILES
        }
    if isinstance(nodo, list):
        return [normalizar(valor) for valor in nodo]
    return nodo


def volcar(spec) -> str:
    return CABECERA + yaml.safe_dump(normalizar(spec), sort_keys=True, allow_unicode=True, width=110)


def generar() -> str:
    runpy.run_path(str(RAIZ / "tests" / "conftest.py"))
    sys.path.insert(0, str(RAIZ / "src"))
    import app  # noqa: E402  (después de fijar los ajustes de prueba)

    return volcar(app.app.openapi())


if __name__ == "__main__":
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(generar(), encoding="utf-8", newline="\n")
    print("escrito", DESTINO.relative_to(RAIZ))
