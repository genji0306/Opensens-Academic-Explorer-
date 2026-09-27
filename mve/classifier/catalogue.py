"""Frozen §5 questions and the complete openJev v1.4 input serialization."""

import json
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1] / "questions"


def catalogue():
    return json.loads((DIRECTORY / "catalogue.json").read_text())["questions"]


def prompt(qid, state):
    q = catalogue()[qid]
    if q["primitive"] == "noul":
        candidates = [f"true: {q['question']}", f"false: not {q['question']}"]
        body = f"Context:\n{state}\n\nEvaluate proposition: {q['question']}"
    else:
        candidates = [f"It is {label}" for label in q["labels"]]
        body = f"Question: {q['question']}\n\nContext:\n{state}"
    return (
        "".join("<<LABEL>>" + c for c in candidates + ["insufficient evidence"])
        + "<<SEP>>"
        + body
    )
