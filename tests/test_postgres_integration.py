"""Run against a disposable PostgreSQL pgvector instance with TEST_DATABASE_URL set."""

import os
import uuid

import pytest


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requires isolated PostgreSQL test database")
def test_postgres_round_trip():
    from app.backend import PostgresRepository
    from app.embeddings import HashEmbeddings

    # This test intentionally targets the persistent storage adapter, not a fake.
    # Hash embeddings are permitted here for bounded deterministic integration tests.
    repo = PostgresRepository(os.environ["TEST_DATABASE_URL"], HashEmbeddings())
    name = f"test-{uuid.uuid4().hex[:12]}.md"
    record = repo.ingest(name, "A reference passage about provenance and citation.")
    try:
        assert any(row["id"] == record["id"] for row in repo.list_documents())
        assert any(item["document_id"] == record["id"] for item in repo.search("provenance citation", 4))
    finally:
        repo.delete(record["id"])
