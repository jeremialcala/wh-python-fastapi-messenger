# -*- coding: utf-8 -*-
"""
    The isolation between clients holds only if nothing reaches the database around the repository. This test
    reads the source: a query or a write anywhere else fails it.
"""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

# The only places that talk to the database on behalf of a client.
DATA_LAYER = ("repository", "migrations")

# Known accesses outside the data layer. None of them stores what the isolation covers (chatbots, phones, rules,
# intents, contacts): they are the event trail and the per-event keys, and nothing creates an event today.
# The list may only shrink: adding a file to it is a decision, not a fix.
OUTSIDE = {
    "classes/entity_amqp_message.py",
    "classes/entity_event.py",
    "classes/entity_event_action.py",
    "classes/entity_jwk.py",
    "controller/events.py",
}

WRITES = {"save", "delete", "update_one", "upsert_one", "modify", "insert", "insert_one"}


def is_a_route(call: ast.Call) -> bool:
    """@app.delete(...) declares a route: it is not a document being deleted."""
    return isinstance(call.func.value, ast.Name) and call.func.value.id == "app"


def touches_the_database(path: Path) -> bool:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute) and node.attr == "objects":
            return True
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in WRITES
                and not is_a_route(node)):
            return True
    return False


def test_only_the_data_layer_touches_the_database():
    found = {path.relative_to(SRC).as_posix() for path in SRC.rglob("*.py")
             if path.relative_to(SRC).parts[0] not in DATA_LAYER and touches_the_database(path)}

    assert found == OUTSIDE


def test_the_scan_sees_a_query_and_a_write(tmp_path):
    sources = {
        "bots = ChatBot.objects(uuid=bot_id)": True,
        "bot.save()": True,
        "intent.delete()": True,
        "bot = repo.get_bot(bot_id)": False,
        "@app.delete(path='/chat/{bot_id}')\nasync def remove(): pass": False,
    }
    for number, (source, expected) in enumerate(sources.items()):
        path = tmp_path / f"case_{number}.py"
        path.write_text(source, encoding="utf-8")

        assert touches_the_database(path) is expected, source
