from app.backend import chunk_text
from app.embeddings import HashEmbeddings


def test_chunker_covers_content_and_handles_small_inputs():
    assert chunk_text(" ") == []
    assert chunk_text("tiny") == ["tiny"]
    chunks = chunk_text("word " * 500)
    assert len(chunks) > 1
    assert all(len(chunk) <= 760 for chunk in chunks)


def test_hash_embedding_is_deterministic_and_dimensionally_valid():
    embedder = HashEmbeddings()
    assert embedder.embed_query("Source citation") == embedder.embed_query("Source citation")
    assert len(embedder.embed_query("Source citation")) == 384
    assert all(value == 0 for value in embedder.embed_query(""))
