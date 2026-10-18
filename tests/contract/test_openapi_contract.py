# -*- coding: utf-8 -*-
"""
    The committed OpenAPI contracts must be what the two services actually serve: the management API and the
    webhook.
    If this fails, regenerate it:  python .ai-dlc/scripts/gen_openapi.py
"""
import importlib.util
import pathlib
import re

import pytest

import app as app_module
import webhook as webhook_module
from constants import DESCRIPTION, WEBHOOK_DESCRIPTION

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "docs" / "02-design" / "contracts"
SERVICES = {"management": (app_module, CONTRACTS / "openapi.yaml", DESCRIPTION),
            "webhook": (webhook_module, CONTRACTS / "openapi-webhook.yaml", WEBHOOK_DESCRIPTION)}
GENERATOR = ROOT / ".ai-dlc" / "scripts" / "gen_openapi.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("gen_openapi", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_committed_openapi_matches_the_application(service):
    generator = load_generator()
    module, contract, _ = SERVICES[service]
    committed = contract.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert committed == generator.volcar(module.app.openapi())


@pytest.mark.parametrize("service,at_least", [("management", 20), ("webhook", 2)])
def test_the_description_names_no_route_the_application_does_not_serve(service, at_least):
    """It described an /answers endpoint that was never there."""
    def shape(path: str) -> str:
        return re.sub(r"\{[^}]*\}", "{}", path)

    module, _, description = SERVICES[service]
    served = {shape(route.path) for route in module.app.routes}
    named = re.findall(r"(?<![\w}])(/[a-z][\w{}/-]*)", description)

    assert len(named) >= at_least
    for path in named:
        assert shape(path) in served, path
    assert "answers" not in module.app.openapi()["info"]["description"]


def test_volatile_keys_are_dropped_but_property_names_are_kept():
    generator = load_generator()
    schema = {"default": 1, "properties": {"default": {"type": "string", "examples": ["a"]}}}

    assert generator.normalizar(schema) == {"properties": {"default": {"type": "string"}}}
