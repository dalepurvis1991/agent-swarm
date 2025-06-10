# Agent Swarm - Email Processing Backend

A FastAPI-based email processing service with validation and logging.

## Prerequisites

* Python 3.11+
* Poetry (`pip install poetry`)

## Quickstart

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Install dependencies
poetry install

# 3. Install package in development mode (for imports)
poetry install -e .

# 4. Run the development server
poetry run uvicorn backend.app.main:app --reload

# 5. Run tests
poetry run pytest
```

## API Endpoints

### POST /incoming-email

Processes incoming email data with validation.

**Request Body:**
```json
{
    "subject": "Test message",
    "from": "alice@example.com", 
    "body": "Hello world"
}
```

**Response:**
```json
{
    "received": true
}
```

**Error Responses:**
- `400` - Invalid JSON
- `422` - Validation error (missing fields, invalid email format, etc.)

## Testing

The test suite includes:
- Happy path testing
- JSON parsing error handling
- Field validation testing
- Email format validation

Run with: `poetry run pytest`

## Development

Server runs on `http://localhost:8000` by default.
API documentation available at `http://localhost:8000/docs` (FastAPI auto-generated).

## Vector Database

The application uses PostgreSQL with pgvector for storing and searching email content.

### Database Setup

```bash
# Start the database
docker compose up -d db

# Check database health
docker compose ps
```

### Environment Variables

Set `DATABASE_URL` if using a different database:
```bash
# In .env file
DATABASE_URL=postgresql://dev:dev@localhost:5432/email_processing
```

### Search CLI Tool

Search for similar emails using the CLI tool:

```bash
# Search for emails similar to a query
poetry run python tools/search.py "product recommendations"

# Example output:
# Search results for: 'product recommendations'
# --------------------------------------------------
# Similarity: 0.850
# Content: Check out our new product line...
# ------------------------------
```

The vector store automatically indexes email body content when emails are received via the `/incoming-email` endpoint. 