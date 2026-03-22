from __future__ import annotations

from uuid import uuid4

from app.api.boards import _board_notification_payload
from app.contracts.activity import (
    parse_board_activity_payload,
    parse_gateway_activity_payload,
)
from app.models.agents import Agent
from app.models.board_groups import BoardGroup
from app.models.boards import Board
from app.services.openclaw.coordination_service import GatewayCoordinationService


def test_board_notification_payload_matches_contract() -> None:
    board = Board(id=uuid4(), organization_id=uuid4(), name="Ops Board", slug="ops-board")
    source_board = Board(
        id=uuid4(),
        organization_id=board.organization_id,
        name="Core Board",
        slug="core-board",
    )
    group = BoardGroup(id=uuid4(), organization_id=board.organization_id, name="Ops Group")
    target = Agent(id=uuid4(), board_id=board.id, gateway_id=uuid4(), name="Fox")

    payload = _board_notification_payload(
        kind="board_group_join",
        board=board,
        target_agent=target,
        notification_status="failed",
        error="gateway unavailable",
        source_board=source_board,
        group=group,
        changed_fields=["gateway_id", "board_group_id"],
    )

    assert payload == {
        "notification_kind": "board_group_join",
        "notification_status": "failed",
        "board_id": str(board.id),
        "board_name": "Ops Board",
        "target_agent_id": str(target.id),
        "target_agent_name": "Fox",
        "source_board_id": str(source_board.id),
        "source_board_name": "Core Board",
        "board_group_id": str(group.id),
        "board_group_name": "Ops Group",
        "changed_fields": ["gateway_id", "board_group_id"],
        "error": "gateway unavailable",
    }
    parsed = parse_board_activity_payload(payload)
    assert parsed.board_name == "Ops Board"
    assert parsed.notification_kind == "board_group_join"


def test_gateway_activity_payload_matches_contract() -> None:
    board = Board(id=uuid4(), organization_id=uuid4(), name="Ops Board", slug="ops-board")
    actor = Agent(id=uuid4(), board_id=board.id, gateway_id=uuid4(), name="Lead")
    target = Agent(id=uuid4(), board_id=board.id, gateway_id=uuid4(), name="Otter")

    payload = GatewayCoordinationService._gateway_activity_payload(
        kind="gateway_lead_message",
        notification_status="sent",
        board=board,
        actor_agent=actor,
        target_agent=target,
        extra={
            "gateway_id": str(target.gateway_id),
            "gateway_name": "Demo Gateway",
            "action": "lead_message",
            "delivery_status": "delivered",
            "target_kind": "lead",
            "workspace_path": "/tmp/demo",
            "session_key": "agent:session",
        },
    )

    assert payload == {
        "notification_kind": "gateway_lead_message",
        "notification_status": "sent",
        "board_id": str(board.id),
        "board_name": "Ops Board",
        "actor_agent_id": str(actor.id),
        "target_agent_id": str(target.id),
        "target_agent_name": "Otter",
        "gateway_id": str(target.gateway_id),
        "gateway_name": "Demo Gateway",
        "action": "lead_message",
        "delivery_status": "delivered",
        "target_kind": "lead",
        "workspace_path": "/tmp/demo",
        "session_key": "agent:session",
    }
    parsed = parse_gateway_activity_payload(payload)
    assert parsed.gateway_name == "Demo Gateway"
    assert parsed.action == "lead_message"
