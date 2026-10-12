# -*- coding: utf-8 -*-
"""
    The committed OpenAPI contract must be what the application actually serves.
    If this fails, regenerate it:  python .ai-dlc/scripts/gen_openapi.py
"""
import importlib.util
import pathlib

import app as app_module

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


def test_volatile_keys_are_dropped_but_property_names_are_kept():
    generator = load_generator()
    schema = {"default": 1, "properties": {"default": {"type": "string", "examples": ["a"]}}}

    assert generator.normalizar(schema) == {"properties": {"default": {"type": "string"}}}
