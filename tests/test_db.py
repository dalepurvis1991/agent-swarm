import pytest
from unittest.mock import Mock, patch
import psycopg
import backend.app.db as db


class MockConnection:
    """Mock database connection for testing."""
    
    def __init__(self):
        self.store = []
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args):
        pass
        
    def execute(self, query, params=None):
        """Mock execute that simulates basic INSERT/SELECT operations."""
        if "INSERT" in query:
            # Store the content (first parameter)
            content = params[0] if params else ""
            self.store.append(content)
            return Mock()
        elif "SELECT" in query:
            # Return mock results with fake similarity scores
            return Mock(fetchall=lambda: [
                (content, 0.8) for content in self.store[:3]
            ])
        return Mock()


@pytest.fixture
def mock_db():
    """Fixture that provides a mocked database connection."""
    mock_conn = MockConnection()
    with patch('backend.app.db.get_connection') as mock_get_conn:
        mock_get_conn.return_value.__enter__ = lambda self: mock_conn
        mock_get_conn.return_value.__exit__ = lambda self, *args: None
        yield mock_conn


def test_add_doc(mock_db):
    """Test adding a document to the store."""
    db.add_doc("hello world email")
    assert "hello world email" in mock_db.store


def test_query_similar(mock_db):
    """Test querying for similar documents."""
    # Add some test documents
    db.add_doc("hello world email")
    db.add_doc("eco friendly tote bags")
    
    # Query for similar documents
    results = db.query_similar("tote bags")
    
    # Should return results
    assert len(results) >= 1
    # Results should be tuples of (content, similarity)
    assert all(isinstance(r, tuple) and len(r) == 2 for r in results)


def test_add_and_query_workflow(mock_db):
    """Test the complete workflow of adding and querying documents."""
    # Add several documents
    docs = [
        "hello world email",
        "eco friendly tote bags",
        "product recommendations"
    ]
    
    for doc in docs:
        db.add_doc(doc)
    
    # Query should return results
    results = db.query_similar("products")
    assert len(results) <= 3  # Limited by k=3 default
    
    # Check that we get content and similarity scores
    for content, similarity in results:
        assert isinstance(content, str)
        assert isinstance(similarity, (int, float))


def test_init_db_success():
    """Test successful database initialization."""
    with patch('backend.app.db.get_connection') as mock_conn:
        mock_conn.return_value.__enter__ = Mock()
        mock_conn.return_value.__exit__ = Mock()
        
        # Should not raise any exception
        db.init_db()


def test_connection_error():
    """Test handling of database connection errors."""
    with patch('backend.app.db.psycopg.connect') as mock_connect:
        # Simulate a psycopg error (which gets wrapped as ConnectionError)
        mock_connect.side_effect = psycopg.Error("Connection failed")
        
        with pytest.raises(ConnectionError):
            db.add_doc("test content") 