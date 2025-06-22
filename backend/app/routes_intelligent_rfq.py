from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List
import os
from ..agents.intelligent_rfq_agent import IntelligentRFQAgent

router = APIRouter()

class RFQRequest(BaseModel):
    specification: str
    session_id: Optional[str] = None

class RFQResponse(BaseModel):
    status: str
    message: str
    question: Optional[str] = None
    analysis: Optional[Dict] = None
    suppliers_found: Optional[int] = None
    emails_generated: Optional[List[Dict]] = None
    session_id: Optional[str] = None

# Global agent instance
intelligent_agent = None

def get_intelligent_agent():
    global intelligent_agent
    if intelligent_agent is None:
        openai_key = os.getenv("OPENAI_API_KEY")
        serpapi_key = os.getenv("SERPAPI_KEY")
        
        if not openai_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        if not serpapi_key:
            raise HTTPException(status_code=500, detail="SerpAPI key not configured")
            
        intelligent_agent = IntelligentRFQAgent(openai_key, serpapi_key)
    
    return intelligent_agent

@router.post("/intelligent-rfq/process", response_model=RFQResponse)
async def process_intelligent_rfq(request: RFQRequest):
    """
    Process an RFQ request using the intelligent agent.
    This will:
    1. Analyze the request to understand the industry and requirements
    2. Search for relevant suppliers
    3. Generate custom emails for each supplier
    4. Ask follow-up questions if needed
    """
    try:
        agent = get_intelligent_agent()
        result = agent.process_rfq_request(request.specification)
        
        if result.get("status") == "needs_clarification":
            return RFQResponse(
                status="needs_clarification",
                message="I need more information to find the best suppliers for you.",
                question=result.get("question"),
                analysis=result.get("analysis")
            )
        
        elif result.get("status") == "ready_to_send":
            return RFQResponse(
                status="ready_to_send",
                message=f"Found {result.get('suppliers_found', 0)} suppliers and generated custom emails for the top 5.",
                analysis=result.get("analysis"),
                suppliers_found=result.get("suppliers_found"),
                emails_generated=result.get("emails_generated")
            )
        
        else:
            return RFQResponse(
                status="error",
                message="An error occurred while processing your request."
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing RFQ: {str(e)}")

@router.post("/intelligent-rfq/clarify", response_model=RFQResponse)
async def clarify_rfq_request(request: RFQRequest):
    """
    Process additional clarification for an RFQ request.
    """
    try:
        agent = get_intelligent_agent()
        
        # For now, treat clarification as a new request
        # In a full implementation, you'd maintain session state
        result = agent.process_rfq_request(request.specification)
        
        if result.get("status") == "needs_clarification":
            return RFQResponse(
                status="needs_clarification",
                message="I need a bit more information.",
                question=result.get("question"),
                analysis=result.get("analysis")
            )
        
        elif result.get("status") == "ready_to_send":
            return RFQResponse(
                status="ready_to_send",
                message=f"Perfect! I found {result.get('suppliers_found', 0)} suppliers and generated custom emails.",
                analysis=result.get("analysis"),
                suppliers_found=result.get("suppliers_found"),
                emails_generated=result.get("emails_generated")
            )
        
        else:
            return RFQResponse(
                status="error",
                message="An error occurred while processing your clarification."
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing clarification: {str(e)}")

@router.get("/intelligent-rfq/example-emails/{industry}")
async def get_example_emails(industry: str):
    """
    Get example emails for different industries to show the AI's capabilities.
    """
    examples = {
        "construction": {
            "product": "Steel RSJ beams",
            "email_preview": "Dear [Supplier],\n\nWe require steel RSJ beams for a commercial construction project. Please provide quotes including:\n- Load bearing specifications\n- CE marking compliance\n- Delivery to site capabilities\n- Installation services available..."
        },
        "insurance": {
            "product": "Commercial property insurance",
            "email_preview": "Dear [Insurance Provider],\n\nWe require commercial property insurance for our warehouse facility. Please provide quotes including:\n- Coverage limits and deductibles\n- Business interruption coverage\n- Claims handling process\n- Risk assessment requirements..."
        },
        "flooring": {
            "product": "Commercial vinyl flooring",
            "email_preview": "Dear [Flooring Supplier],\n\nWe need commercial-grade vinyl flooring for a 5000 sq ft office space. Please provide quotes including:\n- Wear layer thickness specifications\n- Installation services\n- Warranty terms\n- Subfloor preparation requirements..."
        }
    }
    
    return examples.get(industry, {"error": "Industry not found"}) 