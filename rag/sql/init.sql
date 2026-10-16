CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge (
    id        SERIAL PRIMARY KEY,
    content   TEXT,
    metadata  JSONB,
    embedding VECTOR(1024)
);

CREATE INDEX IF NOT EXISTS knowledge_embedding_idx
    ON knowledge USING hnsw (embedding vector_cosine_ops);
