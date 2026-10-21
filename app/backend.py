"""Persistent vector retrieval and an explicitly temporary demo implementation."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import threading
import uuid

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def chunk_text(text: str, size: int = 760, overlap: int = 100) -> list[str]:
    """Bounded overlapping chunks; preserve source offsets through stable order."""
    if not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            break_at = text.rfind(" ", start + size // 2, end)
            if break_at > start:
                end = break_at
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


@dataclass(frozen=True)
class DocumentEntry:
    id: str
    name: str
    sha256: str
    chunk_count: int
    created_at: str
    updated_at: str
    chunk_ids: list[str]

    def public(self) -> dict:
        result = asdict(self)
        result.pop("chunk_ids")
        return result


class Repository:
    """One public API shared by memory and PostgreSQL backends."""

    def __init__(self, vector_store) -> None:
        self.vector_store = vector_store
        self.lock = threading.RLock()

    def _list(self) -> list[DocumentEntry]:
        raise NotImplementedError

    def _save(self, entry: DocumentEntry, replacing: str | None = None) -> None:
        raise NotImplementedError

    def _remove(self, document_id: str) -> None:
        raise NotImplementedError

    def list_documents(self) -> list[dict]:
        with self.lock:
            return [entry.public() for entry in self._list()]

    def get(self, document_id: str) -> DocumentEntry | None:
        return next((entry for entry in self._list() if entry.id == document_id), None)

    def ingest(self, name: str, content: str, replacing: str | None = None) -> dict:
        with self.lock:
            current = self._list()
            old = next((item for item in current if item.id == replacing), None)
            if replacing is not None and old is None:
                raise KeyError("Document not found")
            if any(item.name == name and item.id != replacing for item in current):
                raise FileExistsError("A document with this name already exists")
            chunks = chunk_text(content)
            if not chunks:
                raise ValueError("Document contains no searchable text")
            doc_id = old.id if old else str(uuid.uuid4())
            new_chunk_ids = [str(uuid.uuid4()) for _ in chunks]
            docs = [
                Document(
                    page_content=piece,
                    metadata={"document_id": doc_id, "name": name, "chunk_index": i + 1, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()},
                )
                for i, piece in enumerate(chunks)
            ]
            # Insert before changing catalog. If embedding fails, existing source remains valid.
            self.vector_store.add_documents(docs, ids=new_chunk_ids)
            now = utc_now()
            entry = DocumentEntry(
                id=doc_id,
                name=name,
                sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                chunk_count=len(chunks),
                created_at=old.created_at if old else now,
                updated_at=now,
                chunk_ids=new_chunk_ids,
            )
            try:
                self._save(entry, replacing)
            except Exception:
                self.vector_store.delete(ids=new_chunk_ids)
                raise
            if old:
                self.vector_store.delete(ids=old.chunk_ids)
            return entry.public()

    def delete(self, document_id: str) -> None:
        with self.lock:
            old = self.get(document_id)
            if not old:
                raise KeyError("Document not found")
            self.vector_store.delete(ids=old.chunk_ids)
            self._remove(document_id)

    def search(self, question: str, top_k: int) -> list[dict]:
        with self.lock:
            active = {entry.id: entry for entry in self._list()}
            if not active:
                return []
            # Extra candidates allow expired chunks to be filtered without presenting them.
            found = self.vector_store.similarity_search_with_score(question, k=max(20, top_k * 5))
            results = []
            for document, raw_score in found:
                identifier = document.metadata.get("document_id")
                entry = active.get(identifier)
                index = document.metadata.get("chunk_index")
                if not entry or not isinstance(index, int):
                    continue
                if (document.metadata.get("name") != entry.name
                        or document.metadata.get("sha256") != entry.sha256):
                    continue
                results.append(
                    {
                        "citation": len(results) + 1,
                        "document_id": entry.id,
                        "name": entry.name,
                        "chunk_index": index,
                        "excerpt": document.page_content,
                        # Scores are backend-specific; avoid implying calibrated confidence.
                        "raw_score": round(float(raw_score), 5),
                    }
                )
                if len(results) >= top_k:
                    break
            return results


class MemoryRepository(Repository):
    """Ephemeral, deterministic preview backend. Never advertised as PG persistence."""

    def __init__(self, embeddings) -> None:
        super().__init__(InMemoryVectorStore(embedding=embeddings))
        self.entries: dict[str, DocumentEntry] = {}

    def _list(self) -> list[DocumentEntry]:
        return sorted(self.entries.values(), key=lambda item: item.created_at)

    def _save(self, entry: DocumentEntry, replacing: str | None = None) -> None:
        self.entries[entry.id] = entry

    def _remove(self, document_id: str) -> None:
        del self.entries[document_id]


class PostgresRepository(Repository):
    """Metadata catalog and LangChain PGVectorStore using one PostgreSQL database."""

    def __init__(self, database_url: str, embeddings) -> None:
        from langchain_postgres import PGEngine, PGVectorStore
        from sqlalchemy import create_engine, text

        self.sql = create_engine(database_url, pool_pre_ping=True)
        with self.sql.begin() as connection:
            connection.execute(
                text(
                    """CREATE TABLE IF NOT EXISTS source_documents (
                        id UUID PRIMARY KEY, name VARCHAR(120) UNIQUE NOT NULL,
                        sha256 CHAR(64) NOT NULL, chunk_count INTEGER NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
                        chunk_ids JSONB NOT NULL
                    )"""
                )
            )
        pg_engine = PGEngine.from_connection_string(url=database_url)
        pg_engine.init_vectorstore_table(table_name="groundedtrail_chunks", vector_size=384)
        store = PGVectorStore.create_sync(
            engine=pg_engine, table_name="groundedtrail_chunks", embedding_service=embeddings
        )
        super().__init__(store)

    def _list(self) -> list[DocumentEntry]:
        from sqlalchemy import text

        with self.sql.connect() as connection:
            rows = connection.execute(
                text("SELECT id, name, sha256, chunk_count, created_at, updated_at, chunk_ids "
                     "FROM source_documents ORDER BY created_at")
            ).mappings()
            return [
                DocumentEntry(
                    id=str(row["id"]), name=row["name"], sha256=row["sha256"],
                    chunk_count=row["chunk_count"],
                    created_at=row["created_at"].isoformat(),
                    updated_at=row["updated_at"].isoformat(),
                    chunk_ids=row["chunk_ids"] if isinstance(row["chunk_ids"], list)
                    else json.loads(row["chunk_ids"]),
                )
                for row in rows
            ]

    def _save(self, entry: DocumentEntry, replacing: str | None = None) -> None:
        from sqlalchemy import text

        with self.sql.begin() as connection:
            if replacing:
                connection.execute(
                    text("""UPDATE source_documents SET name=:name, sha256=:sha256,
                        chunk_count=:chunk_count, updated_at=:updated_at,
                        chunk_ids=CAST(:chunk_ids AS jsonb) WHERE id=CAST(:id AS uuid)"""),
                    {**asdict(entry), "chunk_ids": json.dumps(entry.chunk_ids)},
                )
            else:
                connection.execute(
                    text("""INSERT INTO source_documents
                        (id, name, sha256, chunk_count, created_at, updated_at, chunk_ids)
                        VALUES (CAST(:id AS uuid), :name, :sha256, :chunk_count,
                        :created_at, :updated_at, CAST(:chunk_ids AS jsonb))"""),
                    {**asdict(entry), "chunk_ids": json.dumps(entry.chunk_ids)},
                )

    def _remove(self, document_id: str) -> None:
        from sqlalchemy import text

        with self.sql.begin() as connection:
            connection.execute(
                text("DELETE FROM source_documents WHERE id=CAST(:id AS uuid)"),
                {"id": document_id},
            )
