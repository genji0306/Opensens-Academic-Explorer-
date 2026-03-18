"""Smoke tests for Skill v2.0 router, schemas, and executor."""
import pytest


class TestIntentRouter:
    def setup_method(self):
        from skill_v2.router import IntentRouter
        self.router = IntentRouter()

    def test_classify_chemical_formula(self):
        assert self.router.classify_intent({"chemical_formula": "NaCl"}) == "predict_structure"

    def test_classify_xrd_path(self):
        assert self.router.classify_intent({"xrd_path": "test.xy"}) == "predict_from_xrd"

    def test_classify_agent_v(self):
        assert self.router.classify_intent({"agent": "agent_v"}) == "visualize"

    def test_classify_benchmark_dataset(self):
        assert self.router.classify_intent({"dataset": "supercon_24"}) == "benchmark"

    def test_classify_discover_text(self):
        assert self.router.classify_intent({"text": "discover novel superconductor"}) == "discover_material"

    def test_classify_xrd_text(self):
        assert self.router.classify_intent({"text": "analyze XRD pattern"}) == "predict_from_xrd"

    def test_default_intent(self):
        assert self.router.classify_intent({}) == "predict_structure"

    def test_build_plan_predict_structure(self):
        plan = self.router.build_plan({"chemical_formula": "MgB2"})
        assert plan.intent == "predict_structure"
        assert plan.n_steps >= 1
        assert plan.steps[0].agent == "agent_pb"

    def test_build_plan_xrd(self):
        plan = self.router.build_plan({"xrd_path": "test.xy", "composition_hint": "NaCl"})
        assert plan.intent == "predict_from_xrd"
        assert plan.steps[0].agent == "agent_xc"

    def test_build_plan_benchmark(self):
        plan = self.router.build_plan({"dataset": "supercon_24"})
        assert plan.intent == "benchmark"
        assert plan.steps[0].agent == "benchmarks"

    def test_build_plan_visualize(self):
        plan = self.router.build_plan({"agent": "agent_v"})
        assert plan.intent == "visualize"

    def test_build_plan_discover(self):
        plan = self.router.build_plan({"action": "discover"})
        assert plan.intent == "discover_material"
        assert plan.n_steps == 2  # orchestrator + dashboard update


class TestSchemas:
    def test_execution_plan_to_dict(self):
        from skill_v2.schemas import ExecutionPlan, ExecutionStep
        plan = ExecutionPlan(
            intent="test",
            steps=[ExecutionStep(agent="a", action="b")],
        )
        d = plan.to_dict()
        assert d["intent"] == "test"
        assert d["n_steps"] == 1
        assert d["agents"] == ["a"]

    def test_execution_result_success(self):
        from skill_v2.schemas import ExecutionPlan, ExecutionResult, StepResult
        plan = ExecutionPlan(intent="test")
        result = ExecutionResult(
            plan=plan,
            step_results=[StepResult(step_index=0, agent="a", action="b", success=True)],
        )
        assert result.success is True
        assert len(result.failed_steps) == 0

    def test_execution_result_failure(self):
        from skill_v2.schemas import ExecutionPlan, ExecutionResult, StepResult
        plan = ExecutionPlan(intent="test")
        result = ExecutionResult(
            plan=plan,
            step_results=[
                StepResult(step_index=0, agent="a", action="b", success=True),
                StepResult(step_index=1, agent="c", action="d", success=False, error="fail"),
            ],
        )
        assert result.success is False
        assert len(result.failed_steps) == 1


class TestExecutor:
    def test_dry_run(self):
        from skill_v2.schemas import ExecutionPlan, ExecutionStep
        from skill_v2.executor import PlanExecutor
        plan = ExecutionPlan(
            intent="test",
            steps=[ExecutionStep(agent="agent_pb", action="predict",
                                 params={"formula": "NaCl"})],
        )
        executor = PlanExecutor(dry_run=True)
        result = executor.execute(plan)
        assert result.success is True
        assert result.step_results[0].details.get("dry_run") is True

    def test_dependency_skip(self):
        from skill_v2.schemas import ExecutionPlan, ExecutionStep
        from skill_v2.executor import PlanExecutor
        plan = ExecutionPlan(
            intent="test",
            steps=[
                ExecutionStep(agent="unknown_agent", action="fail"),
                ExecutionStep(agent="agent_v", action="export_cif", depends_on=[0]),
            ],
        )
        executor = PlanExecutor(dry_run=False)
        result = executor.execute(plan)
        # Step 0 should fail (unknown dispatch), step 1 should be skipped
        assert not result.step_results[0].success
        assert not result.step_results[1].success
        assert "Dependency" in result.step_results[1].error
