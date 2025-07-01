#!/bin/bash
# Backend startup script with database connection verification

echo "Starting backend service..."

# Export DATABASE_URL if not set
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="postgresql://dev:dev@db:5432/email_processing"
    echo "DATABASE_URL not set, using default: $DATABASE_URL"
else
    echo "DATABASE_URL is set: $DATABASE_URL"
fi

# Show other important environment variables
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:+Set}"
echo "SERPAPI_KEY: ${SERPAPI_KEY:+Set}"

# Wait for database to be ready
echo "Waiting for database..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if poetry run python -c "
import psycopg
try:
    conn = psycopg.connect('$DATABASE_URL')
    conn.close()
    print('Database is ready!')
    exit(0)
except Exception as e:
    print(f'Database not ready: {e}')
    exit(1)
"; then
        break
    fi
    
    retry_count=$((retry_count + 1))
    echo "Waiting for database... (attempt $retry_count/$max_retries)"
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "ERROR: Database connection failed after $max_retries attempts"
    exit 1
fi

# Start the application
echo "Starting FastAPI application..."
exec poetry run python -m backend.app.main