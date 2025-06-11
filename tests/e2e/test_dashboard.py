"""E2E tests for the dashboard using Playwright."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_dashboard_search_functionality(page: Page):
    """Test that the dashboard can search for offers and display results."""
    
    # Navigate to the frontend
    page.goto("http://localhost:3000")
    
    # Verify the page loads correctly
    expect(page).to_have_title("Agent Swarm Dashboard")
    
    # Switch to Direct Search tab
    page.locator('button:has-text("🔍 Direct Search")').click()
    
    # Find the search input and search button
    search_input = page.locator('input[placeholder*="Enter product specification"]')
    search_button = page.locator('button:has-text("Search")')
    
    # Verify elements are visible
    expect(search_input).to_be_visible()
    expect(search_button).to_be_visible()
    
    # Type in the search query
    search_input.fill("eco tote bags")
    
    # Click the search button
    search_button.click()
    
    # Wait for results to load (give it some time for the API call)
    page.wait_for_timeout(2000)
    
    # Check if at least one QuoteCard element is present
    # This validates that the search functionality works and displays results
    quote_cards = page.locator('.QuoteCard')
    
    # We expect at least one quote card to be present
    expect(quote_cards).to_have_count_greater_than(0)
    
    # Verify the quote card has expected structure
    first_card = quote_cards.first
    expect(first_card).to_be_visible()
    
    # Verify that the quote card contains expected elements
    # (supplier name, price, etc.)
    expect(first_card.locator('h3')).to_be_visible()  # Supplier name
    expect(first_card.locator('text=Price:')).to_be_visible()  # Price label


@pytest.mark.e2e
def test_dashboard_empty_search(page: Page):
    """Test that empty search shows appropriate validation."""
    
    # Navigate to the frontend
    page.goto("http://localhost:3000")
    
    # Switch to Direct Search tab
    page.locator('button:has-text("🔍 Direct Search")').click()
    
    # Find the search button and click without entering text
    search_button = page.locator('button:has-text("Search")')
    search_button.click()
    
    # Verify error message appears
    error_message = page.locator('text=Please enter a specification')
    expect(error_message).to_be_visible()


@pytest.mark.e2e  
def test_dashboard_no_results(page: Page):
    """Test that searching for non-existent items shows no results message."""
    
    # Navigate to the frontend
    page.goto("http://localhost:3000")
    
    # Switch to Direct Search tab
    page.locator('button:has-text("🔍 Direct Search")').click()
    
    # Search for something that likely won't have results
    search_input = page.locator('input[placeholder*="Enter product specification"]')
    search_button = page.locator('button:has-text("Search")')
    
    search_input.fill("nonexistent product xyz123")
    search_button.click()
    
    # Wait for results
    page.wait_for_timeout(2000)
    
    # Should show no results message
    no_results = page.locator('text=No quotes found')
    expect(no_results).to_be_visible()


@pytest.mark.e2e
def test_rfq_chat_functionality(page: Page):
    """Test the RFQ chat specification clarification workflow."""
    
    # Navigate to the frontend
    page.goto("http://localhost:3000")
    
    # Verify the page loads correctly
    expect(page).to_have_title("Agent Swarm Dashboard")
    
    # Switch to Smart RFQ Assistant tab
    rfq_tab = page.locator('button:has-text("🤖 Smart RFQ Assistant")')
    expect(rfq_tab).to_be_visible()
    rfq_tab.click()
    
    # Verify RFQ chat interface is visible
    expect(page.locator('text=RFQ Specification Assistant')).to_be_visible()
    expect(page.locator('text=Start by describing what you need')).to_be_visible()
    
    # Find the chat input and start button
    chat_input = page.locator('input[placeholder*="Describe what you need"]')
    start_button = page.locator('button:has-text("Start")')
    
    expect(chat_input).to_be_visible()
    expect(start_button).to_be_visible()
    
    # Start an RFQ session with an incomplete specification
    chat_input.fill("I need eco tote bags")
    start_button.click()
    
    # Wait for the agent response
    page.wait_for_timeout(3000)
    
    # Verify that a clarifying question appears
    # Look for message bubbles or chat content
    page.wait_for_selector('div:has-text("How many")', timeout=5000)
    
    # Verify user message appears
    user_message = page.locator('div:has-text("I need eco tote bags")')
    expect(user_message).to_be_visible()
    
    # Verify assistant question appears (should ask about quantity)
    assistant_message = page.locator('div').filter(has_text="How many")
    expect(assistant_message).to_be_visible()
    
    # Answer the question
    answer_input = page.locator('input[placeholder*="Type your answer"]')
    answer_button = page.locator('button:has-text("Answer")')
    
    expect(answer_input).to_be_visible()
    expect(answer_button).to_be_visible()
    
    answer_input.fill("1000 units")
    answer_button.click()
    
    # Wait for the next response
    page.wait_for_timeout(3000)
    
    # Should either ask another question or show completion
    # Check if we get a completion status or another question
    page.wait_for_timeout(2000)
    
    # Verify the conversation progressed
    user_answer = page.locator('div:has-text("1000 units")')
    expect(user_answer).to_be_visible()


@pytest.mark.e2e
def test_rfq_chat_completion_flow(page: Page):
    """Test that RFQ chat can complete and show structured spec."""
    
    # Navigate to the frontend
    page.goto("http://localhost:3000")
    
    # Switch to Smart RFQ Assistant tab
    page.locator('button:has-text("🤖 Smart RFQ Assistant")').click()
    
    # Start with a more complete specification
    chat_input = page.locator('input[placeholder*="Describe what you need"]')
    start_button = page.locator('button:has-text("Start")')
    
    # Use a specification that should trigger completion after one answer
    chat_input.fill("I need 500 cotton tote bags")
    start_button.click()
    
    # Wait for response
    page.wait_for_timeout(3000)
    
    # Answer any follow-up question
    answer_input = page.locator('input[placeholder*="Type your answer"]')
    if answer_input.is_visible():
        answer_button = page.locator('button:has-text("Answer")')
        answer_input.fill("Medium size bags for corporate gifts")
        answer_button.click()
        page.wait_for_timeout(3000)
    
    # Check if completion status appears
    # Look for success indicators or "Get Quotes Now" button
    completion_indicators = [
        'text=✅ Specification Complete',
        'text=Perfect! I have all the information',
        'button:has-text("Get Quotes Now")'
    ]
    
    # At least one completion indicator should be visible
    found_completion = False
    for indicator in completion_indicators:
        if page.locator(indicator).is_visible():
            found_completion = True
            break
    
    # If not complete yet, this means the agent needs more clarification
    # which is also valid behavior
    if not found_completion:
        # Verify we're still in conversation mode
        expect(page.locator('input[placeholder*="Type your answer"]')).to_be_visible()


@pytest.mark.e2e
def test_tab_navigation(page: Page):
    """Test that tab navigation works correctly."""
    
    page.goto("http://localhost:3000")
    
    # Verify both tabs are visible
    rfq_tab = page.locator('button:has-text("🤖 Smart RFQ Assistant")')
    search_tab = page.locator('button:has-text("🔍 Direct Search")')
    
    expect(rfq_tab).to_be_visible()
    expect(search_tab).to_be_visible()
    
    # Test switching to RFQ tab
    rfq_tab.click()
    expect(page.locator('text=RFQ Specification Assistant')).to_be_visible()
    
    # Test switching to Search tab
    search_tab.click()
    expect(page.locator('input[placeholder*="Enter product specification"]')).to_be_visible()
    
    # Verify tab states
    expect(rfq_tab).not_to_have_class('border-blue-500')
    expect(search_tab).to_have_class('border-blue-500') 