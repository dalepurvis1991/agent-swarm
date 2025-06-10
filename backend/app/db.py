import os
import contextlib
from typing import List, Tuple
import psycopg
from pgvector.psycopg import register_vector
from .embeddings import embed

DB_DSN = os.getenv("DATABASE_URL", "postgresql://dev:dev@localhost:5432/email_processing")


@contextlib.contextmanager
def get_connection():
    """Get database connection with pgvector support."""
    try:
        with psycopg.connect(DB_DSN) as conn:
            register_vector(conn)
            yield conn
    except psycopg.Error as e:
        raise ConnectionError(f"Database connection failed: {e}")


def add_doc(content: str) -> None:
    """Add document to vector store."""
    vec = embed(content)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
            (content, vec)
        )


def query_similar(text: str, k: int = 3) -> List[Tuple[str, float]]:
    """Query for similar documents using cosine similarity."""
    vec = embed(text)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT content, 1 - (embedding <=> %s) AS similarity "
            "FROM documents ORDER BY embedding <=> %s LIMIT %s",
            (vec, vec, k)
        ).fetchall()
    return rows


def init_db() -> None:
    """Initialize database connection (test connectivity)."""
    with get_connection():
        pass  # Just test that we can connect 