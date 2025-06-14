import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from backend.app.models import EmailPayload
from backend.app.db import add_doc, init_db
from backend.app.routes import quotes_router
from backend.app.routes_clarify import rfq_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        init_db()
        logging.info("Database connection OK")
    except Exception as e:
        logging.error(f"Database startup failed: {e}")
        raise
    yield
    # Shutdown (if needed)


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the quotes router
app.include_router(quotes_router)

# Include the RFQ clarification router
app.include_router(rfq_router)


@app.post("/incoming-email", status_code=status.HTTP_200_OK)
async def incoming_email(req: Request):
    try:
        payload_dict = await req.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    
    try:
        payload = EmailPayload(**payload_dict)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Validation error") from exc

    try:
        add_doc(payload.body)
        logging.info("EMAIL STORED: %s", payload.model_dump())
        return {"received": True}
    except ConnectionError as e:
        logging.error("Database error: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable") 