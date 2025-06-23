"""Main FastAPI application entry point with improved error handling."""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg
from backend.app.db import DB_DSN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_database_connection():
    """Check database connection with retry logic."""
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            conn = psycopg.connect(DB_DSN)
            conn.close()
            logger.info("Database connection successful")
            return True
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Failed to connect to database after all retries")
                return False
    
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting up application...")
    
    # Check database connection
    db_connected = await check_database_connection()
    if not db_connected:
        logger.error("Could not establish database connection. Application may not function properly.")
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title="Agent Swarm API",
    description="API for automated RFQ processing and supplier management",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Agent Swarm API is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Quick database connection test
        conn = psycopg.connect(DB_DSN)
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.get("/api/offers")
async def get_offers():
    """Get all offers."""
    try:
        from backend.app.offers import OfferManager
        offers = await OfferManager.get_offers_by_spec("", limit=100)
        return {"offers": offers}
    except Exception as e:
        logger.error(f"Error fetching offers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/offers/{offer_id}")
async def get_offer(offer_id: int):
    """Get specific offer by ID."""
    try:
        from backend.app.offers import OfferManager
        offer = await OfferManager.get_offer_by_id(offer_id)
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        return offer
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching offer {offer_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
