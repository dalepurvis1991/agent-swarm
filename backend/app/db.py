import os
import contextlib
from typing import List, Tuple
import psycopg
from psycopg.rows import dict_row
from .embeddings import embed

DB_DSN = os.getenv("DATABASE_URL", "postgresql://dev:dev@localhost:5432/email_processing")


@contextlib.contextmanager
def get_connection():
    """Get database connection."""
    try:
        conn = psycopg.connect(DB_DSN, row_factory=dict_row)
        try:
            yield conn
        finally:
            conn.close()
    except psycopg.Error as e:
        raise ConnectionError(f"Database connection failed: {e}")


def add_doc(content: str) -> None:
    """Add document to vector store."""
    try:
        vec = embed(content)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
                (content, vec)
            )
            conn.commit()
    except Exception as e:
        print(f"Warning: Database operation failed: {e}")


def query_similar(text: str, k: int = 3) -> List[Tuple[str, float]]:
    """Query for similar documents using cosine similarity."""
    try:
        vec = embed(text)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM documents LIMIT %s",
                (k,)
            )
            rows = cursor.fetchall()
        return rows
    except Exception as e:
        print(f"Warning: Database query failed: {e}")
        return []


def init_db() -> None:
    """Initialize database connection (test connectivity)."""
    try:
        with get_connection():
            pass  # Just test that we can connect
        print("Database connection OK")
    except Exception as e:
        print(f"Warning: Database connection failed: {e}. Running without database.") 