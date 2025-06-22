from openai import OpenAI
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import requests
from serpapi import Client

@dataclass
class ProductLead:
    product_name: str
    supplier_name: str
    supplier_email: str
    supplier_website: str
    estimated_price: Optional[float]
    product_url: str
    relevance_score: float

@dataclass
class IndustryContext:
    industry: str
    key_specifications: List[str]
    typical_suppliers: List[str]
    price_factors: List[str]
    required_certifications: List[str]

class IntelligentRFQAgent:
    def __init__(self, openai_api_key: str = None, serpapi_key: str = None):
        import os
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.serpapi_key = serpapi_key or os.getenv('SERPAPI_KEY')
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        
    def analyze_request(self, user_request: str) -> Dict:
        """Analyze the user's request to understand the industry, product type, and missing information"""
        
        system_prompt = """You are an expert procurement analyst. Analyze the user's request and determine:
        1. What industry/category this falls into (construction, insurance, technology, manufacturing, etc.)
        2. What specific product or service they need
        3. What key specifications are missing that suppliers would need
        4. What follow-up questions should be asked to get complete requirements
        
        Return your analysis as JSON with this structure:
        {
            "industry": "string",
            "product_category": "string", 
            "product_description": "string",
            "missing_specifications": ["list of missing specs"],
            "follow_up_questions": ["list of specific questions to ask"],
            "estimated_complexity": "low/medium/high",
            "requires_clarification": true/false,
            "next_question": "single most important question to ask next"
        }"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Using gpt-3.5-turbo as it's more accessible
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_request}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            analysis = json.loads(response.choices[0].message.content)
            return analysis
            
        except Exception as e:
            return {
                "error": str(e),
                "industry": "unknown",
                "requires_clarification": True,
                "next_question": "Could you provide more details about what you need?"
            }
    
    def search_suppliers(self, product_description: str, industry: str) -> List[ProductLead]:
        """Search for suppliers using SerpAPI and web scraping"""
        
        leads = []
        
        try:
            # Search for suppliers
            search_queries = [
                f"{product_description} suppliers UK",
                f"{industry} {product_description} manufacturers",
                f"buy {product_description} wholesale",
                f"{product_description} quotes online"
            ]
            
            for query in search_queries[:2]:  # Limit to 2 queries to avoid rate limits
                client = Client(api_key=self.serpapi_key)
                results = client.search({
                    "engine": "google",
                    "q": query,
                    "num": 10
                })
                
                for result in results.get("organic_results", []):
                    # Extract supplier information
                    lead = self._extract_supplier_info(result, product_description)
                    if lead:
                        leads.append(lead)
                        
        except Exception as e:
            print(f"Error searching suppliers: {e}")
            
        # Remove duplicates and sort by relevance
        unique_leads = {}
        for lead in leads:
            key = lead.supplier_name.lower()
            if key not in unique_leads or lead.relevance_score > unique_leads[key].relevance_score:
                unique_leads[key] = lead
                
        return sorted(list(unique_leads.values()), key=lambda x: x.relevance_score, reverse=True)[:10]
    
    def _extract_supplier_info(self, search_result: Dict, product_description: str) -> Optional[ProductLead]:
        """Extract supplier information from search results"""
        
        try:
            title = search_result.get("title", "")
            snippet = search_result.get("snippet", "")
            url = search_result.get("link", "")
            
            # Use AI to determine if this is a relevant supplier
            relevance_prompt = f"""
            Analyze if this search result is for a legitimate supplier of "{product_description}":
            
            Title: {title}
            Description: {snippet}
            URL: {url}
            
            Return JSON with:
            {{
                "is_supplier": true/false,
                "supplier_name": "extracted company name",
                "relevance_score": 0.0-1.0,
                "estimated_price": null or number,
                "contact_info_likely": true/false
            }}
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": relevance_prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            if analysis.get("is_supplier") and analysis.get("relevance_score", 0) > 0.3:
                return ProductLead(
                    product_name=product_description,
                    supplier_name=analysis.get("supplier_name", title.split(" ")[0]),
                    supplier_email="",  # Will be found later
                    supplier_website=url,
                    estimated_price=analysis.get("estimated_price"),
                    product_url=url,
                    relevance_score=analysis.get("relevance_score", 0.5)
                )
                
        except Exception as e:
            print(f"Error extracting supplier info: {e}")
            
        return None
    
    def generate_custom_email(self, lead: ProductLead, full_specification: str, industry: str) -> str:
        """Generate a custom email for each supplier based on their industry and the specific product"""
        
        email_prompt = f"""
        Generate a professional email to request a quote from a {industry} supplier.
        
        Supplier: {lead.supplier_name}
        Product needed: {lead.product_name}
        Full specification: {full_specification}
        Industry context: {industry}
        
        The email should:
        1. Be professional and industry-appropriate
        2. Include all relevant specifications
        3. Ask for industry-specific information (certifications, compliance, etc.)
        4. Request timeline and pricing
        5. Be personalized to this specific supplier
        6. Include any industry-specific requirements
        
        Generate ONLY the email content (no subject line):
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": email_prompt}],
                temperature=0.7,
                max_tokens=800
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"Dear {lead.supplier_name},\n\nWe are interested in obtaining a quote for {lead.product_name}.\n\nSpecification: {full_specification}\n\nPlease provide your best pricing and availability.\n\nBest regards"
    
    def find_contact_email(self, supplier_website: str) -> Optional[str]:
        """Try to find contact email for a supplier (placeholder - would need web scraping)"""
        
        # This would typically involve:
        # 1. Scraping the supplier's website
        # 2. Looking for contact pages
        # 3. Extracting email addresses
        # 4. Using AI to determine the best contact email
        
        # For now, return a placeholder
        return None
    
    def process_rfq_request(self, user_request: str) -> Dict:
        """Main method to process an RFQ request"""
        
        # Step 1: Analyze the request
        analysis = self.analyze_request(user_request)
        
        if analysis.get("requires_clarification"):
            return {
                "status": "needs_clarification",
                "question": analysis.get("next_question"),
                "analysis": analysis
            }
        
        # Step 2: Search for suppliers
        suppliers = self.search_suppliers(
            analysis.get("product_description", ""),
            analysis.get("industry", "")
        )
        
        # Step 3: Generate custom emails for each supplier
        emails = []
        for supplier in suppliers[:5]:  # Top 5 suppliers
            email_content = self.generate_custom_email(
                supplier, 
                user_request,
                analysis.get("industry", "")
            )
            
            emails.append({
                "supplier": supplier.supplier_name,
                "email_content": email_content,
                "website": supplier.supplier_website,
                "estimated_price": supplier.estimated_price
            })
        
        return {
            "status": "ready_to_send",
            "analysis": analysis,
            "suppliers_found": len(suppliers),
            "emails_generated": emails,
            "top_suppliers": [s.supplier_name for s in suppliers[:5]]
        } 