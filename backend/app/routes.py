from fastapi import APIRouter, Query
from backend.app.offers import get_offers

quotes_router = APIRouter()


@quotes_router.get("/quotes")
async def get_quotes(spec: str = Query(..., description="Product specification to search for")):
    """
    Get the 3 cheapest offers for a given specification.
    
    Args:
        spec: Product specification to search for
        
    Returns:
        JSON list of offers sorted by price ascending
    """
    offers = get_offers(spec, limit=3)
    return offers 