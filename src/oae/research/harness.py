"""Reusable research-harness primitives extracted from RH + Klein + Timeguard.

The core pattern is:

control lane -> intervention lane -> review lane -> optional promotion lane

This module is intentionally lightweight. It captures the reusable protocol and
stable artifact naming without coupling every domain to RH-specific language.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


LaneRole = Literal["control", "intervention", "review", "promotion"]


@dataclass(frozen=True)
class HarnessLane:
    lane_id: str
    role: LaneRole
    entrypoint: str
    description: str
    artifact_prefix: str
    key_outputs: tuple[str, ...] = ()
    success_signals: tuple[str, ...] = ()

    def build_artifact_id(self, *, module_slug: str, run_tag: str) -> str:
        return f"{self.artifact_prefix}-{module_slug}-{run_tag}"

    def to_dict(self, *, module_slug: str, run_tag: str) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "role": self.role,
            "entrypoint": self.entrypoint,
            "description": self.description,
            "artifact_prefix": self.artifact_prefix,
            "artifact_id": self.build_artifact_id(module_slug=module_slug, run_tag=run_tag),
            "key_outputs": list(self.key_outputs),
            "success_signals": list(self.success_signals),
        }


@dataclass(frozen=True)
class ResearchHarness:
    module_slug: str
    question: str
    control_lane: HarnessLane
    intervention_lane: HarnessLane
    review_lane: HarnessLane
    promotion_lane: HarnessLane | None = None
    comparability_contract: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    taboo_routes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def artifact_plan(self, run_tag: str) -> dict[str, str]:
        plan = {
            "control": self.control_lane.build_artifact_id(module_slug=self.module_slug, run_tag=run_tag),
            "intervention": self.intervention_lane.build_artifact_id(module_slug=self.module_slug, run_tag=run_tag),
            "review": self.review_lane.build_artifact_id(module_slug=self.module_slug, run_tag=run_tag),
        }
        if self.promotion_lane is not None:
            plan["promotion"] = self.promotion_lane.build_artifact_id(
                module_slug=self.module_slug,
                run_tag=run_tag,
            )
        return plan

    def to_dict(self, run_tag: str) -> dict[str, Any]:
        payload = {
            "module_slug": self.module_slug,
            "question": self.question,
            "artifact_plan": self.artifact_plan(run_tag),
            "control_lane": self.control_lane.to_dict(module_slug=self.module_slug, run_tag=run_tag),
            "intervention_lane": self.intervention_lane.to_dict(module_slug=self.module_slug, run_tag=run_tag),
            "review_lane": self.review_lane.to_dict(module_slug=self.module_slug, run_tag=run_tag),
            "comparability_contract": list(self.comparability_contract),
            "obligations": list(self.obligations),
            "taboo_routes": list(self.taboo_routes),
            "notes": list(self.notes),
        }
        if self.promotion_lane is not None:
            payload["promotion_lane"] = self.promotion_lane.to_dict(
                module_slug=self.module_slug,
                run_tag=run_tag,
            )
        return payload


def build_riemann_harness() -> ResearchHarness:
    return ResearchHarness(
        module_slug="riemann",
        question=(
            "Which intervention changes the RH research program in a useful way when measured "
            "against a matched baseline and reviewed through Timeguard?"
        ),
        control_lane=HarnessLane(
            lane_id="baseline",
            role="control",
            entrypoint="python3 oae.py --riemann-research --topology baseline",
            description="Matched baseline RH recursive research run.",
            artifact_prefix="control",
            key_outputs=("summary.json", "failure_atlas.json", "campaign_benchmark.json"),
            success_signals=("clean control trace", "repeated blocker visibility"),
        ),
        intervention_lane=HarnessLane(
            lane_id="klein",
            role="intervention",
            entrypoint="python3 oae.py --riemann-research --topology klein",
            description="Klein-mode intervention that adds cross-lane pressure and return certificates.",
            artifact_prefix="intervention",
            key_outputs=("summary.json", "failure_atlas.json", "certificate_report.json"),
            success_signals=("cross-lane pressure", "surface-return certificate", "obstruction shift"),
        ),
        review_lane=HarnessLane(
            lane_id="timeguard",
            role="review",
            entrypoint="python3 -m src.oae.studios.timeguard.cli run",
            description="Compare baseline and Klein as control plane vs intervention plane.",
            artifact_prefix="review",
            key_outputs=("timeguard_report.md", "timeguard_scorecards.json", "timeguard_forecast.json"),
            success_signals=("ranked work packages", "named taboo routes", "promotion recommendation"),
        ),
        promotion_lane=HarnessLane(
            lane_id="seed-pack-launch",
            role="promotion",
            entrypoint="python3 -m src.oae.studios.timeguard.cli launch-external-seed-pack",
            description="Promote one reviewed frontier pack into a real RH campaign.",
            artifact_prefix="promotion",
            key_outputs=("external_seed_launch_report.md", "summary.json"),
            success_signals=("promoted frontier bundle", "single reviewed launch"),
        ),
        comparability_contract=(
            "same seed packs",
            "same max rounds",
            "same hypothesis budget",
            "same worker budget",
            "same numeric worker settings",
            "same saved-report policy",
        ),
        obligations=(
            "finite_window_only",
            "global_exclusion_gap",
            "translation_gap",
            "tail_control_gap",
        ),
        taboo_routes=(
            "same-lane loops without a return certificate",
            "circular equivalence-wall restatements",
            "reopening finite-data reconstruction after the route is closed",
        ),
        notes=(
            "Use baseline as the control plane and Klein as the intervention plane.",
            "Do not present any artifact as proof progress on RH.",
        ),
    )


def build_rtap_harness() -> ResearchHarness:
    return ResearchHarness(
        module_slug="rtap",
        question=(
            "Which RTAP intervention improves candidate quality or blocker visibility when held against "
            "a matched direct-loop control run?"
        ),
        control_lane=HarnessLane(
            lane_id="direct-loop",
            role="control",
            entrypoint="python3 oae.py --rtap",
            description="Direct RTAP loop used as the clean reference branch.",
            artifact_prefix="control",
            key_outputs=("final_report.json", "candidate reports"),
            success_signals=("stable control ranking", "repeated family bottlenecks"),
        ),
        intervention_lane=HarnessLane(
            lane_id="campaign",
            role="intervention",
            entrypoint="python3 oae.py --campaign --rtap",
            description="Adaptive RTAP campaign with planner, reflection, and memory.",
            artifact_prefix="intervention",
            key_outputs=("campaign report", "phase outcomes", "memory updates"),
            success_signals=("better phase selection", "clearer dead-end family map"),
        ),
        review_lane=HarnessLane(
            lane_id="campaign-review",
            role="review",
            entrypoint="compare direct RTAP vs campaign RTAP artifacts under one budget contract",
            description="Review lane for candidate quality, budget use, and repeated dead ends.",
            artifact_prefix="review",
            key_outputs=("comparison report", "ranked next work packages"),
            success_signals=("promotable family shortlist", "taboo route list"),
        ),
        promotion_lane=HarnessLane(
            lane_id="candidate-package",
            role="promotion",
            entrypoint="promote one reviewed family or synthesis package into tighter validation",
            description="Single-family promotion lane for RTAP follow-up.",
            artifact_prefix="promotion",
            key_outputs=("validation bundle", "review package"),
            success_signals=("one promoted family", "clear provenance"),
        ),
        comparability_contract=(
            "same total budget",
            "same candidate family pool",
            "same score weights",
            "same pressure and Tc constraints",
        ),
        obligations=(
            "ambient-pressure realism",
            "stability under the same score contract",
            "synthesis feasibility",
            "dead-end family recurrence",
        ),
        taboo_routes=(
            "retrying the same family without a changed mechanism",
            "promotion based only on headline Tc",
            "budget drift between control and intervention",
        ),
    )


def build_sensing_studio_harness() -> ResearchHarness:
    return ResearchHarness(
        module_slug="sensing-studio",
        question=(
            "Which sensing intervention improves blind-eval quality or routing clarity under the same analyte "
            "and evidence budget?"
        ),
        control_lane=HarnessLane(
            lane_id="direct-policy",
            role="control",
            entrypoint="python3 oae.py --sensor --analyte <name>",
            description="Current direct sensing loop as the control branch.",
            artifact_prefix="control",
            key_outputs=("sensor outputs", "observer score"),
            success_signals=("clean blind-eval baseline", "repeatable routing history"),
        ),
        intervention_lane=HarnessLane(
            lane_id="recursive-policy",
            role="intervention",
            entrypoint="python3 oae.py --campaign --sensor --analyte <name>",
            description="Recursive or campaign-style sensing policy under the same analyte.",
            artifact_prefix="intervention",
            key_outputs=("verification bundles", "routing history", "session trace"),
            success_signals=("better blind evaluation", "more useful routing decisions"),
        ),
        review_lane=HarnessLane(
            lane_id="observer-review",
            role="review",
            entrypoint="compare verification bundles and routing churn across both sensing branches",
            description="Review lane anchored on blind evaluation rather than raw score alone.",
            artifact_prefix="review",
            key_outputs=("verification comparison", "promotion recommendation"),
            success_signals=("held-out robustness", "routing clarity", "reduced churn"),
        ),
        promotion_lane=HarnessLane(
            lane_id="assay-package",
            role="promotion",
            entrypoint="promote one reviewed assay/export bundle",
            description="Single promotion lane for export or deployment follow-up.",
            artifact_prefix="promotion",
            key_outputs=("assay package", "export bundle"),
            success_signals=("one reviewed export package", "clear deployment target"),
        ),
        comparability_contract=(
            "same analyte",
            "same calibration evidence",
            "same held-out blind-eval policy",
            "same round budget",
        ),
        obligations=(
            "blind-eval robustness",
            "calibration drift",
            "routing churn without accuracy gain",
            "held-out verification failure",
        ),
        taboo_routes=(
            "changing the analyte mid-comparison",
            "claiming improvement without blind-eval gain",
            "routing loops that do not alter evidence or model posture",
        ),
    )


def build_default_harnesses() -> dict[str, ResearchHarness]:
    return {
        "riemann": build_riemann_harness(),
        "rtap": build_rtap_harness(),
        "sensing-studio": build_sensing_studio_harness(),
    }
