"""Specification Clarification Agent.

This agent helps users refine their product specifications by asking
intelligent follow-up questions when details are missing or unclear.
"""

import json
import logging
from typing import Dict, Any, List, Optional
import openai
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ClarificationResponse(BaseModel):
    """Response from the clarification agent."""
    status: str  # "needs_clarification" or "complete"
    question: Optional[str] = None  # Follow-up question if status is "needs_clarification"
    structured_spec: Optional[Dict[str, Any]] = None  # Structured spec if status is "complete"
    reasoning: Optional[str] = None  # Why this question was asked or why spec is complete


class SpecificationClarifier:
    """Agent for clarifying product specifications through conversation."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the clarifier with OpenAI API key."""
        self.client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None
        
    def clarify_specification(
        self, 
        original_spec: str, 
        conversation_history: List[Dict[str, str]] = None
    ) -> ClarificationResponse:
        """
        Analyze a specification and either ask a clarifying question or return structured data.
        
        Args:
            original_spec: The initial product specification from the user
            conversation_history: Previous Q&A in format [{"role": "assistant", "content": "..."}, {"role": "user", "content": "..."}]
            
        Returns:
            ClarificationResponse with either a question or structured specification
        """
        if not self.client:
            # Fallback for testing without API key
            return self._mock_clarification(original_spec, conversation_history)
        
        try:
            # Build conversation context
            messages = [
                {
                    "role": "system",
                    "content": self._get_system_prompt()
                },
                {
                    "role": "user", 
                    "content": f"Original specification: {original_spec}"
                }
            ]
            
            # Add conversation history
            if conversation_history:
                for msg in conversation_history:
                    messages.append(msg)
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content
            return self._parse_response(response_text)
            
        except Exception as e:
            logger.error(f"Error in specification clarification: {e}")
            return ClarificationResponse(
                status="needs_clarification",
                question="Could you provide more details about your product requirements?",
                reasoning="System error occurred, requesting general clarification"
            )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the clarification agent."""
        return """You are a procurement specification clarifier. Your job is to help users refine their product specifications.

Given a product specification, you should:

1. If the specification is incomplete or unclear, ask ONE specific follow-up question to gather missing critical information
2. If the specification is complete enough for suppliers to quote, return structured JSON

Critical information needed for quotes:
- Product type/category
- Quantity needed
- Key specifications (size, material, color, etc.)
- Quality requirements
- Timeline/deadline
- Budget range (if mentioned)

Response format:
{
  "status": "needs_clarification" or "complete",
  "question": "Your single follow-up question" (only if needs_clarification),
  "structured_spec": {
    "product_type": "...",
    "quantity": "...",
    "specifications": {...},
    "timeline": "...",
    "budget": "..."
  } (only if complete),
  "reasoning": "Why you asked this question or why spec is complete"
}

Guidelines:
- Ask only ONE question at a time
- Focus on the most critical missing information
- Be specific and actionable
- If multiple details are missing, prioritize quantity, product type, and key specs
- Don't ask about budget unless user mentions it
- Mark as complete when you have enough info for suppliers to provide meaningful quotes"""

    def _parse_response(self, response_text: str) -> ClarificationResponse:
        """Parse the LLM response into a structured format."""
        try:
            # Try to extract JSON from the response
            response_data = json.loads(response_text)
            return ClarificationResponse(**response_data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            # Fallback: treat as a clarification question
            return ClarificationResponse(
                status="needs_clarification",
                question=response_text.strip(),
                reasoning="Failed to parse structured response"
            )
    
    def _mock_clarification(
        self, 
        original_spec: str, 
        conversation_history: List[Dict[str, str]] = None
    ) -> ClarificationResponse:
        """Mock clarification for testing without API key."""
        
        # Simple rule-based logic for testing
        spec_lower = original_spec.lower()
        
        # Check if we have quantity
        has_quantity = any(word in spec_lower for word in ['units', 'pieces', 'dozen', 'hundred', 'thousand', '100', '1000', 'qty'])
        
        # Check if we have material/type info
        has_material = any(word in spec_lower for word in ['cotton', 'plastic', 'metal', 'wood', 'fabric', 'eco', 'organic'])
        
        # Check if we have size info
        has_size = any(word in spec_lower for word in ['small', 'medium', 'large', 'cm', 'inch', 'size'])
        
        # If this is a follow-up in conversation
        if conversation_history and len(conversation_history) >= 2:
            return ClarificationResponse(
                status="complete",
                structured_spec={
                    "product_type": "tote bags" if "bag" in spec_lower else "custom product",
                    "quantity": "1000 units" if not has_quantity else "specified",
                    "specifications": {
                        "material": "eco-friendly" if "eco" in spec_lower else "standard",
                        "size": "standard" if not has_size else "specified",
                        "color": "natural" if not any(color in spec_lower for color in ['red', 'blue', 'black', 'white']) else "specified"
                    },
                    "timeline": "4-6 weeks",
                    "budget": "not specified"
                },
                reasoning="Sufficient information gathered through conversation"
            )
        
        # Ask for missing critical info
        if not has_quantity:
            return ClarificationResponse(
                status="needs_clarification",
                question="How many units do you need?",
                reasoning="Quantity is essential for accurate pricing"
            )
        
        if not has_size and "bag" in spec_lower:
            return ClarificationResponse(
                status="needs_clarification", 
                question="What size bags do you need? (e.g., small promotional bags, large shopping bags, or specific dimensions)",
                reasoning="Size specification needed for tote bags"
            )
        
        if not has_material:
            return ClarificationResponse(
                status="needs_clarification",
                question="What material preference do you have? (e.g., cotton, canvas, recycled plastic, etc.)",
                reasoning="Material specification affects pricing and supplier matching"
            )
        
        # If we have basic info, mark as complete
        return ClarificationResponse(
            status="complete",
            structured_spec={
                "product_type": "tote bags" if "bag" in spec_lower else original_spec,
                "quantity": "to be confirmed",
                "specifications": {"material": "as specified", "requirements": original_spec},
                "timeline": "standard lead time",
                "budget": "market rate"
            },
            reasoning="Basic specification provided, suppliers can provide initial quotes"
        )

class ClarifyAgent:
    SYSTEM_PROMPT = """You are a helpful assistant that helps clarify product specifications.
    If the specification is incomplete or unclear, ask ONE follow-up question to get the missing information.
    If the specification is complete, respond with status="complete" and include the structured specification in spec_json.
    Keep your questions focused and specific."""

    def __init__(self, api_key: str):
        openai.api_key = api_key

    def chat(self, spec: str) -> Dict:
        """
        Process a specification and either ask a follow-up question or return a complete spec.
        
        Args:
            spec: The current specification text
            
        Returns:
            Dict containing either:
            - status="question" and a follow-up question
            - status="complete" and the structured spec_json
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": spec}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # Extract the assistant's response
            assistant_response = response.choices[0].message.content
            
            # Check if the response indicates completion
            if "status=\"complete\"" in assistant_response.lower():
                # Extract the spec_json from the response
                # This is a simple implementation - you might want to make this more robust
                return {
                    "status": "complete",
                    "spec_json": assistant_response
                }
            else:
                return {
                    "status": "question",
                    "question": assistant_response
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            } 