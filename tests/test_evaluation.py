"""Deterministic measures, including misses and empty datasets."""

from app.evaluation import EvaluationCase, score_rankings


def test_reference_rankings():
    cases = [EvaluationCase("a", "first.md"), EvaluationCase("b", "second.md"),
             EvaluationCase("c", "missing.md")]
    metrics = score_rankings(cases, [["first.md"], ["first.md", "second.md"], ["other.md"]])
    assert metrics == {"case_count": 3, "hit_rate": 0.6667, "mrr": 0.5}


def test_empty_and_mismatched():
    assert score_rankings([], []) == {"case_count": 0, "hit_rate": 0.0, "mrr": 0.0}
    try:
        score_rankings([EvaluationCase("q", "a")], [])
    except ValueError:
        pass
    else:
        raise AssertionError("Missing ranking was accepted")


def test_evaluation_endpoint(client):
    response = client.get("/api/evaluation")
    assert response.status_code == 200
    assert response.json()["case_count"] == 3
    assert response.json()["hit_rate"] == 0.0
