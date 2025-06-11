"""Routes for RFQ specification clarification."""

import logging
import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.app.db import get_connection
from backend.agents.clarify_agent import SpecificationClarifier, ClarificationResponse
import json

logger = logging.getLogger(__name__)

rfq_router = APIRouter(prefix="/rfq", tags=["RFQ Clarification"])


class StartRFQRequest(BaseModel):
    """Request to start an RFQ clarification session."""
    specification: str


class AnswerRFQRequest(BaseModel):
    """Request to answer a clarification question."""
    session_id: str
    answer: str


class RFQSessionResponse(BaseModel):
    """Response for RFQ session operations."""
    session_id: str
    status: str
    question: Optional[str] = None
    structured_spec: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None


def get_clarifier() -> SpecificationClarifier:
    """Dependency to get the specification clarifier."""
    return SpecificationClarifier()


@rfq_router.post("/start", response_model=RFQSessionResponse)
async def start_rfq_session(
    request: StartRFQRequest,
    clarifier: SpecificationClarifier = Depends(get_clarifier)
):
    """
    Start a new RFQ clarification session.
    
    Args:
        request: Contains the initial product specification
        
    Returns:
        Session information with either a clarifying question or completion status
    """
    try:
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Get clarification response
        clarification = clarifier.clarify_specification(request.specification)
        
        # Prepare messages array
        messages = [
            {"role": "user", "content": request.specification, "timestamp": "now"}
        ]
        
        if clarification.question:
            messages.append({
                "role": "assistant", 
                "content": clarification.question,
                "timestamp": "now"
            })
        
        # Store session in database
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rfq_sessions 
                (session_id, original_spec, spec_json, status, messages)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                session_id,
                request.specification,
                json.dumps(clarification.structured_spec) if clarification.structured_spec else None,
                clarification.status,
                json.dumps(messages)
            ))
            conn.commit()
        
        logger.info(f"Started RFQ session {session_id} with status {clarification.status}")
        
        return RFQSessionResponse(
            session_id=session_id,
            status=clarification.status,
            question=clarification.question,
            structured_spec=clarification.structured_spec,
            reasoning=clarification.reasoning
        )
        
    except Exception as e:
        logger.error(f"Error starting RFQ session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start RFQ session: {str(e)}")


@rfq_router.post("/answer", response_model=RFQSessionResponse)
async def answer_rfq_question(
    request: AnswerRFQRequest,
    clarifier: SpecificationClarifier = Depends(get_clarifier)
):
    """
    Answer a clarification question in an existing RFQ session.
    
    Args:
        request: Contains session ID and the user's answer
        
    Returns:
        Updated session with either another question or completion status
    """
    try:
        # Retrieve session from database
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT original_spec, messages, status 
                FROM rfq_sessions 
                WHERE session_id = %s
            """, (request.session_id,))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="RFQ session not found")
            
            original_spec, messages_json, current_status = result
            messages = json.loads(messages_json) if messages_json else []
        
        if current_status == "complete":
            raise HTTPException(status_code=400, detail="RFQ session already completed")
        
        # Add user's answer to conversation
        messages.append({
            "role": "user", 
            "content": request.answer,
            "timestamp": "now"
        })
        
        # Build conversation history for clarifier
        conversation_history = []
        for msg in messages:
            if msg["role"] in ["user", "assistant"]:
                conversation_history.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Get next clarification
        clarification = clarifier.clarify_specification(original_spec, conversation_history)
        
        # Add assistant response to messages if there's a question
        if clarification.question:
            messages.append({
                "role": "assistant",
                "content": clarification.question,
                "timestamp": "now"
            })
        
        # Update session in database
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE rfq_sessions 
                SET spec_json = %s, status = %s, messages = %s, updated_at = NOW()
                WHERE session_id = %s
            """, (
                json.dumps(clarification.structured_spec) if clarification.structured_spec else None,
                clarification.status,
                json.dumps(messages),
                request.session_id
            ))
            conn.commit()
        
        logger.info(f"Updated RFQ session {request.session_id} with status {clarification.status}")
        
        return RFQSessionResponse(
            session_id=request.session_id,
            status=clarification.status,
            question=clarification.question,
            structured_spec=clarification.structured_spec,
            reasoning=clarification.reasoning
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error answering RFQ question: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process answer: {str(e)}")


@rfq_router.get("/session/{session_id}")
async def get_rfq_session(session_id: str):
    """
    Retrieve details of an RFQ session.
    
    Args:
        session_id: UUID of the session
        
    Returns:
        Session details including conversation history
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, original_spec, spec_json, status, messages, created_at, updated_at
                FROM rfq_sessions 
                WHERE session_id = %s
            """, (session_id,))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="RFQ session not found")
            
            session_id, original_spec, spec_json, status, messages_json, created_at, updated_at = result
            
            return {
                "session_id": session_id,
                "original_spec": original_spec,
                "structured_spec": json.loads(spec_json) if spec_json else None,
                "status": status,
                "messages": json.loads(messages_json) if messages_json else [],
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat()
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving RFQ session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session: {str(e)}")


@rfq_router.get("/sessions")
async def list_rfq_sessions(limit: int = 50, status: Optional[str] = None):
    """
    List recent RFQ sessions.
    
    Args:
        limit: Maximum number of sessions to return
        status: Filter by status (optional)
        
    Returns:
        List of RFQ sessions
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT session_id, original_spec, status, created_at, updated_at
                FROM rfq_sessions
            """
            params = []
            
            if status:
                query += " WHERE status = %s"
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            sessions = cursor.fetchall()
            
            return [
                {
                    "session_id": session[0],
                    "original_spec": session[1],
                    "status": session[2],
                    "created_at": session[3].isoformat(),
                    "updated_at": session[4].isoformat()
                }
                for session in sessions
            ]
        
    except Exception as e:
        logger.error(f"Error listing RFQ sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}") 