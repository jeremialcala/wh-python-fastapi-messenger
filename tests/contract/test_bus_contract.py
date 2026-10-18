# -*- coding: utf-8 -*-
"""
    The contract of the bus, version 2 (asyncapi-v2.yaml), is still a design: nothing publishes it yet. Until the
    code does and can be validated against it, as test_queue_contract.py does with version 1, this keeps the file
    coherent: every reference points somewhere, and every schema is a valid JSON Schema.
"""
import pathlib

import pytest
import yaml
from jsonschema import Draft202012Validator

CONTRACT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "02-design" / "contracts" / "asyncapi-v2.yaml"
DOCUMENT = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def references(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from references(value)
    elif isinstance(node, list):
        for value in node:
            yield from references(value)


def resolve(pointer: str):
    assert pointer.startswith("#/"), pointer
    node = DOCUMENT
    for part in pointer[2:].split("/"):
        node = node[part]
    return node


def test_it_is_version_2_of_the_bus():
    assert (DOCUMENT["asyncapi"], DOCUMENT["info"]["version"]) == ("3.0.0", "2.0.0")
    assert DOCUMENT["servers"]["bifrost"]["protocol"] == "nats"


@pytest.mark.parametrize("pointer", sorted(set(references(DOCUMENT))))
def test_every_reference_points_somewhere(pointer):
    assert resolve(pointer) is not None


@pytest.mark.parametrize("name", sorted(DOCUMENT["components"]["schemas"]))
def test_every_schema_is_valid(name):
    Draft202012Validator.check_schema(DOCUMENT["components"]["schemas"][name])


def test_every_channel_parameter_is_declared():
    for name, channel in DOCUMENT["channels"].items():
        named = {part[1:-1] for part in channel["address"].split(".") if part.startswith("{")}
        assert named == set(channel.get("parameters", {})), name
