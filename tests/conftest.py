"""Offline API fixtures. The database is covered by an opt-in integration test."""

import pytest
from fastapi.testclient import TestClient

from app.backend import MemoryRepository
from app.config import Settings
from app.embeddings import HashEmbeddings
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        settings=Settings(backend="memory", embeddings="hash"),
        repository=MemoryRepository(HashEmbeddings()),
    )
    with TestClient(app) as test_client:
        yield test_client
