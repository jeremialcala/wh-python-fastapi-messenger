# -*- coding: utf-8 -*-
"""
    The committed OpenAPI contract must be what the application actually serves.
    If this fails, regenerate it:  python .ai-dlc/scripts/gen_openapi.py
"""
import importlib.util
import pathlib
import re

import app as app_module
from constants import DESCRIPTION

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "02-design" / "contracts" / "openapi.yaml"
GENERATOR = ROOT / ".ai-dlc" / "scripts" / "gen_openapi.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("gen_openapi", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_openapi_matches_the_application():
    generator = load_generator()
    committed = CONTRACT.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert committed == generator.volcar(app_module.app.openapi())


def test_the_description_names_no_route_the_application_does_not_serve():
    """It described an /answers endpoint that was never there."""
    def shape(path: str) -> str:
        return re.sub(r"\{[^}]*\}", "{}", path)

    served = [shape(route.path) for route in app_module.app.routes]
    named = re.findall(r"^\* (/[^:\s]*):", DESCRIPTION, flags=re.MULTILINE)

    assert named == ["/bot", "/chat", "/chat/{BOT-ID}/phones"]
    for path in named:
        assert any(route.startswith(shape(path)) for route in served), path
    assert "answers" not in app_module.app.openapi()["info"]["description"]


def test_volatile_keys_are_dropped_but_property_names_are_kept():
    generator = load_generator()
    schema = {"default": 1, "properties": {"default": {"type": "string", "examples": ["a"]}}}

    assert generator.normalizar(schema) == {"properties": {"default": {"type": "string"}}}
