"""MutableFlow.add_decorator(..., duplicates=OVERRIDE) must replace a flow
decorator, not leave the old instance registered next to the new one.

Regression test for #2739: overriding ``@project`` from a FlowMutator left both
instances in the flow's decorator list, so ``flow_init`` ran twice and a run got
two ``project_branch`` tags.
"""

import pytest

from metaflow import FlowSpec, project, step
from metaflow.flowspec import FlowStateItems
from metaflow.user_decorators.mutable_flow import MutableFlow


def _make_mutable_flow(flow_cls):
    return MutableFlow(
        flow_cls,
        pre_mutate=True,
        statically_defined=False,
        inserted_by=["test"],
    )


def _project_decorators(flow_cls):
    return flow_cls._flow_state[FlowStateItems.FLOW_DECORATORS]["project"]


def _make_static_flow():
    @project(name="static_name", branch="static_branch")
    class StaticProjectFlow(FlowSpec):
        @step
        def start(self):
            self.next(self.end)

        @step
        def end(self):
            pass

    return StaticProjectFlow


def _make_base_and_child_flows():
    @project(name="base_name")
    class BaseProjectFlow(FlowSpec):
        pass

    class ChildProjectFlow(BaseProjectFlow):
        @step
        def start(self):
            self.next(self.end)

        @step
        def end(self):
            pass

    return BaseProjectFlow, ChildProjectFlow


@pytest.mark.parametrize(
    "make_flow",
    [_make_static_flow, lambda: _make_base_and_child_flows()[1]],
    ids=["defined_on_flow", "inherited_from_base"],
)
def test_override_replaces_flow_decorator(make_flow):
    flow_cls = make_flow()
    mutable_flow = _make_mutable_flow(flow_cls)
    # Read the decorators first, as a FlowMutator inspecting decorator_specs does.
    assert len(list(mutable_flow.decorator_specs)) == 1

    added = mutable_flow.add_decorator(
        project,
        deco_kwargs={"name": "new_name", "branch": "new_branch"},
        duplicates=MutableFlow.OVERRIDE,
    )

    decos = _project_decorators(flow_cls)
    assert decos == [added]
    assert decos[0].attributes["name"] == "new_name"
    assert decos[0].attributes["branch"] == "new_branch"
    assert [spec[0] for spec in mutable_flow.decorator_specs] == ["project"]


def test_override_does_not_touch_base_class_decorators():
    base_cls, child_cls = _make_base_and_child_flows()
    mutable_flow = _make_mutable_flow(child_cls)
    mutable_flow.add_decorator(
        project, deco_kwargs={"name": "new_name"}, duplicates=MutableFlow.OVERRIDE
    )

    base_decos = base_cls._flow_state[FlowStateItems.FLOW_DECORATORS]["project"]
    assert len(base_decos) == 1
    assert base_decos[0].attributes["name"] == "base_name"


def test_consecutive_overrides_keep_one_decorator():
    flow_cls = _make_static_flow()
    mutable_flow = _make_mutable_flow(flow_cls)
    for name in ("first", "second"):
        mutable_flow.add_decorator(
            project, deco_kwargs={"name": name}, duplicates=MutableFlow.OVERRIDE
        )

    decos = _project_decorators(flow_cls)
    assert len(decos) == 1
    assert decos[0].attributes["name"] == "second"
