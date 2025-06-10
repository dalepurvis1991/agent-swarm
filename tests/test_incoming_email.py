import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_happy_path():
    """Test successful email processing"""
    with patch('backend.app.main.add_doc') as mock_add_doc:
        resp = client.post(
            "/incoming-email",
            json={"subject": "Test", "from": "alice@example.com", "body": "Hello"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"received": True}
        # Verify the email body was stored
        mock_add_doc.assert_called_once_with("Hello")


def test_invalid_json():
    """Test malformed JSON handling"""
    resp = client.post(
        "/incoming-email",
        data='{"incomplete": }',
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400


def test_missing_required_fields():
    """Test validation errors for missing fields"""
    resp = client.post(
        "/incoming-email",
        json={"subject": "Test"}  # missing 'from' and 'body'
    )
    assert resp.status_code == 422


def test_invalid_email():
    """Test validation errors for invalid email format"""
    resp = client.post(
        "/incoming-email",
        json={
            "subject": "Test",
            "from": "not-an-email",
            "body": "Hello"
        }
    )
    assert resp.status_code == 422


def test_empty_subject():
    """Test validation errors for empty subject"""
    resp = client.post(
        "/incoming-email",
        json={
            "subject": "",
            "from": "alice@example.com",
            "body": "Hello"
        }
    )
    assert resp.status_code == 422


def test_database_error():
    """Test handling of database connection errors during email processing"""
    with patch('backend.app.main.add_doc') as mock_add_doc:
        mock_add_doc.side_effect = ConnectionError("Database unavailable")
        
        resp = client.post(
            "/incoming-email",
            json={"subject": "Test", "from": "alice@example.com", "body": "Hello"}
        )
        assert resp.status_code == 503
        assert "Database unavailable" in resp.json()["detail"] 