"""Critical user workflows, input validation, and evidence lineage."""


def test_health_and_ui(client):
    assert client.get("/api/health").json()["backend"] == "memory"
    assert client.get("/").status_code == 200
    assert "Source library" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/secret").status_code == 404


def test_ingest_retrieve_replace_delete(client):
    create = client.post("/api/documents", json={
        "name": "guide.md", "content": "Releases require tests and a rollback plan."
    })
    assert create.status_code == 201
    document_id = create.json()["id"]
    assert len(client.get("/api/documents").json()["documents"]) == 1
    found = client.post("/api/ask", json={"question": "What do releases require?"}).json()
    assert found["sources"][0]["document_id"] == document_id
    assert "rollback plan" in found["sources"][0]["excerpt"]
    assert found["mode"] == "retrieval"
    replace = client.put(f"/api/documents/{document_id}", json={
        "name": "guide.md", "content": "Updated releases require security review."
    })
    assert replace.status_code == 200
    updated = client.post("/api/ask", json={"question": "What requires security review?"}).json()
    assert "security review" in updated["sources"][0]["excerpt"]
    assert all("rollback plan" not in s["excerpt"] for s in updated["sources"])
    assert client.delete(f"/api/documents/{document_id}").status_code == 204
    assert client.get("/api/documents").json()["documents"] == []
    assert client.post("/api/ask", json={"question": "What requires security review?"}).json()["sources"] == []


def test_validation_and_conflicts(client):
    bad = ["../private.md", "a/secret.txt", "virus.exe", "a\\b.md"]
    for name in bad:
        assert client.post("/api/documents", json={"name": name, "content": "text"}).status_code == 422
    assert client.post("/api/documents", json={"name": "ok.md", "content": " "}).status_code == 422
    assert client.post("/api/documents", json={"name": "ok.md", "content": "data"}).status_code == 201
    assert client.post("/api/documents", json={"name": "ok.md", "content": "data"}).status_code == 409
    assert client.delete("/api/documents/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.post("/api/ask", json={"question": "?"}).status_code == 422
    assert client.post("/api/ask", json={"question": "valid question", "top_k": 11}).status_code == 422
    assert client.post("/api/ask", json={"question": "valid question", "extra": 1}).status_code == 422


def test_citations_never_claim_grounding(client):
    client.post("/api/documents", json={"name": "evidence.md", "content": "The schedule has two phases."})
    response = client.post("/api/ask", json={"question": "How many phases?"}).json()
    assert response["mode"] == "retrieval"
    assert response["sources"][0]["citation"] == 1
    assert response["sources"][0]["chunk_index"] == 1
    assert response["sources"][0]["name"] == "evidence.md"
    assert "confidence" not in response["sources"][0]
