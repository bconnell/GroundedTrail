"""Simple source-level ranking measures; metrics do not establish answer factuality."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationCase:
    question: str
    expected_source: str


def score_rankings(cases: list[EvaluationCase], retrieved: list[list[str]]) -> dict:
    if len(cases) != len(retrieved):
        raise ValueError("Every evaluation case requires one ranking")
    hits = 0
    reciprocal_rank = 0.0
    for case, ranking in zip(cases, retrieved, strict=True):
        try:
            rank = ranking.index(case.expected_source) + 1
        except ValueError:
            continue
        hits += 1
        reciprocal_rank += 1 / rank
    count = len(cases)
    return {
        "case_count": count,
        "hit_rate": round(hits / count, 4) if count else 0.0,
        "mrr": round(reciprocal_rank / count, 4) if count else 0.0,
    }
