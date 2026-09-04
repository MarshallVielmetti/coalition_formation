import json

import pytest

from coalition_formation.core.actions import (
    Action,
    DisbandCoalitionAction,
    FormCoalitionAction,
    NoOpAction,
    action_from_dict,
)


@pytest.mark.parametrize(
    "action",
    (
        FormCoalitionAction(coalition_id="c1", task_id="t1", robot_ids=("r2", "r1")),
        DisbandCoalitionAction(coalition_id="c1"),
        NoOpAction(reason="nothing feasible"),
    ),
)
def test_typed_actions_round_trip(action: Action) -> None:
    encoded = action.to_dict()
    json.dumps(encoded)
    assert action_from_dict(encoded) == action


def test_form_action_canonicalizes_robot_order_and_rejects_duplicates() -> None:
    action = FormCoalitionAction(
        coalition_id="c1", task_id="t1", robot_ids=("r2", "r1")
    )
    assert action.robot_ids == ("r1", "r2")

    with pytest.raises(ValueError, match="duplicate IDs"):
        FormCoalitionAction(coalition_id="c1", task_id="t1", robot_ids=("r1", "r1"))
