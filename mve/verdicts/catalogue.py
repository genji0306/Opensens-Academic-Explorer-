"""Frozen r5 §5 label vocabulary; visibility is not a classifier target."""

from mve.validation import require

LABELS = {
    "Q-domain": (
        "euclidean_plane",
        "solid",
        "function_plot",
        "chart",
        "graph",
        "knot",
        "surface",
        "braid",
        "unsupported",
    ),
    "Q-track": ("appearance_only", "annotated_problem"),
    "Q-shape": ("triangle", "quadrilateral", "circle", "polygon_n", "line_config", "mixed"),
    "Q-claim-workflow": (
        "restates_measured",
        "propose_new_measurement",
        "contradicts_measured",
        "discard",
    ),
    "Q-mark-type": ("tick_equal", "arc_equal", "right_angle_box", "arrow_parallel", "none"),
    "Q-agree-action": ("merge", "remeasure", "human"),
    "Q-solver": ("newclid", "lean_typecheck_only", "prover", "human", "none"),
    "Q-drift-flag": ("yes", "no"),
    "Q-topo-workflow": ("pd_transcribe", "invariants_only", "reject_diagram", "human"),
}
ABSTENTIONS = {"not_visible", "unsure"}


def check_label(judgment, graph):
    question, verdict = judgment["question"], judgment["verdict"]
    label = judgment.get("label")
    if verdict == "label" or question.startswith("Q-"):
        require(question in LABELS, "unknown catalogue question")
        require(verdict in {"label", *ABSTENTIONS}, "visibility is not a catalogue label")
        if verdict == "label":
            require(label in LABELS[question], "invalid catalogue label")
        if question == "Q-claim-workflow":
            require(
                bool((graph[judgment["target"]].get("text") or "").strip()),
                "Q-claim-workflow needs a free-text claim",
            )
    if verdict != "label":
        require(label is None, "only explicit label verdicts carry a label")
