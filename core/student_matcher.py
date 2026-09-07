"""Matching and comparison helpers for hardcopy student forms vs reference data."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

MATCH_FIELDS = [
    ("Application No", "Application No", 1.0),
    ("Name", "Name", 0.25),
    ("Father Name", "Father Name", 0.25),
    ("Mother Name", "Mother Name", 0.15),
    ("Dob", "Dob", 0.15),
    ("School Id", "School Id", 0.10),
    ("Aadhar No", "Aadhar No", 0.10),
]


def normalize(value) -> str:
    text = "" if value is None else str(value)
    text = text.strip().upper()
    return re.sub(r"[^A-Z0-9]+", "", text)


def similarity(a, b) -> float:
    left, right = normalize(a), normalize(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def compare_fields(form_data: dict, reference: dict) -> list[dict]:
    rows = []
    for form_key, ref_key, _weight in MATCH_FIELDS[1:]:
        form_value = form_data.get(form_key, "")
        ref_value = reference.get(ref_key, "")
        score = similarity(form_value, ref_value)
        if not form_value and not ref_value:
            status = "blank"
        elif score >= 0.97:
            status = "match"
        elif score >= 0.70:
            status = "close"
        else:
            status = "mismatch"
        rows.append({"field": form_key, "form": form_value, "reference": ref_value, "score": score, "status": status})
    return rows


def match_score(form_data: dict, reference: dict) -> float:
    rows = compare_fields(form_data, reference)
    weighted = [(row["score"], weight) for row, (_fk, _rk, weight) in zip(rows, MATCH_FIELDS[1:]) if row["form"] or row["reference"]]
    if not weighted:
        return 0.0
    return sum(score * weight for score, weight in weighted) / sum(weight for _score, weight in weighted)


def rank_candidates(form_data: dict, candidates: list[dict]) -> list[tuple[float, dict]]:
    ranked = [(match_score(form_data, candidate), candidate) for candidate in candidates]
    return sorted(ranked, key=lambda item: item[0], reverse=True)
