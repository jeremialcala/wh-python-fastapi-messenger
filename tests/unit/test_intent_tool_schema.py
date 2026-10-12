# -*- coding: utf-8 -*-
from classes import Action, ApiCall, ActionParameter
from enums import Status


def _sample_action() -> Action:
    return Action(
        name="get_order",
        description="Fetch the status and details of a customer order",
        type="api_call",
        parameters=[
            ActionParameter(name="order_id", type="string",
                            description="The unique identifier of the order", required=True),
            ActionParameter(name="channel", type="string",
                            description="Sales channel", required=False,
                            enum=["web", "store", "app"]),
        ],
        apiCall=ApiCall(method="GET", url="https://api.example.com/orders/{order_id}")
    )


def test_to_tool_schema_shape():
    schema = _sample_action().to_tool_schema()

    assert schema["name"] == "get_order"
    assert schema["description"].startswith("Fetch the status")
    assert schema["input_schema"]["type"] == "object"

    props = schema["input_schema"]["properties"]
    assert props["order_id"] == {
        "type": "string",
        "description": "The unique identifier of the order",
    }
    # enum is carried through only when present
    assert props["channel"]["enum"] == ["web", "store", "app"]


def test_to_tool_schema_required_list():
    schema = _sample_action().to_tool_schema()
    # only parameters flagged required should appear
    assert schema["input_schema"]["required"] == ["order_id"]


def test_inactive_actions_excluded_from_tool_definitions():
    from classes import Intent

    active = _sample_action()
    inactive = _sample_action()
    inactive.name = "hidden"
    inactive.status = Status.DIS.value

    intent = Intent(name="check_order_status",
                    description="The user wants to know the status of an order",
                    actions=[active, inactive])

    tools = intent.tool_definitions()
    names = [t["name"] for t in tools]
    assert names == ["get_order"]
