"""Tests for IMAP email polling and integration functionality."""

import pytest
import asyncio
from unittest.mock import patch, Mock, MagicMock, call
from datetime import datetime

from backend.agents.quote_agent import _poll_inbox, QuoteAgent, get_imap_config


class TestIMAPConfiguration:
    """Test IMAP configuration handling."""
    
    def test_get_imap_config_defaults(self):
        """Test IMAP configuration with default values."""
        with patch.dict('os.environ', {}, clear=True):
            config = get_imap_config()
            
            assert config["IMAP_HOST"] == "localhost"
            assert config["IMAP_PORT"] == "1143"
            assert config["IMAP_USER"] == "test@example.com"
            assert config["IMAP_PASS"] == ""
    
    def test_get_imap_config_custom(self):
        """Test IMAP configuration with custom values."""
        custom_config = {
            "IMAP_HOST": "mail.example.com",
            "IMAP_PORT": "993",
            "IMAP_USER": "user@example.com",
            "IMAP_PASS": "secret123"
        }
        
        with patch.dict('os.environ', custom_config):
            config = get_imap_config()
            
            assert config["IMAP_HOST"] == "mail.example.com"
            assert config["IMAP_PORT"] == "993"
            assert config["IMAP_USER"] == "user@example.com"
            assert config["IMAP_PASS"] == "secret123"


class TestIMAPPolling:
    """Test IMAP inbox polling functionality."""
    
    @pytest.mark.asyncio
    async def test_poll_inbox_no_messages(self):
        """Test inbox polling when no messages are found."""
        spec = "test product"
        suppliers = [{"name": "Test Supplier", "url": "http://test.com"}]
        
        # Mock IMAP client
        mock_server = MagicMock()
        mock_server.search.return_value = []  # No messages
        mock_server.__enter__.return_value = mock_server
        mock_server.__exit__.return_value = None
        
        with patch('backend.agents.quote_agent.imapclient.IMAPClient') as mock_imap_client:
            mock_imap_client.return_value = mock_server
            
            # Run with short duration to speed up test
            offers = await _poll_inbox(spec, suppliers, max_duration=1)
            
            assert len(offers) == 0
            mock_server.select_folder.assert_called_with('INBOX')
            mock_server.search.assert_called()
    
    @pytest.mark.asyncio
    async def test_poll_inbox_with_valid_offer(self):
        """Test inbox polling with a valid offer email."""
        spec = "eco tote bags"
        suppliers = [{"name": "Green Supplier Co", "url": "http://green.com"}]
        
        # Mock email content with offer
        email_content = """From: green-supplier-co@example.com
Subject: Re: RFQ for eco tote bags

Thank you for your inquiry.

Our price is $25.50 per unit for the eco tote bags.
Lead time is 2 weeks from order confirmation.

Best regards,
Sales Team"""
        
        # Mock IMAP server responses
        mock_server = MagicMock()
        mock_server.search.return_value = [1]  # One message
        mock_server.fetch.return_value = {
            1: {b'RFC822': email_content.encode('utf-8')}
        }
        mock_server.__enter__.return_value = mock_server
        mock_server.__exit__.return_value = None
        
        # Mock the store_offer function to return a valid ID
        with patch('backend.agents.quote_agent.imapclient.IMAPClient') as mock_imap_client:
            mock_imap_client.return_value = mock_server
            
            with patch('backend.agents.quote_agent.store_offer') as mock_store:
                mock_store.return_value = 123  # Mock offer ID
                
                offers = await _poll_inbox(spec, suppliers, max_duration=1)
                
                assert len(offers) == 1
                assert offers[0]["price"] == 25.50
                assert offers[0]["currency"] == "$"
                assert offers[0]["lead_time"] == 2
                assert offers[0]["offer_id"] == 123
                assert offers[0]["from_email"] == "green-supplier-co@example.com"
                
                # Verify offer was stored
                mock_store.assert_called_once()
                store_call_args = mock_store.call_args[0]
                assert store_call_args[2] == spec  # spec parameter
    
    @pytest.mark.asyncio
    async def test_poll_inbox_email_without_pricing(self):
        """Test inbox polling with email that has no pricing info."""
        spec = "test product"
        suppliers = [{"name": "Test Supplier", "url": "http://test.com"}]
        
        # Mock email content without pricing
        email_content = """From: test-supplier@example.com
Subject: Re: Your inquiry

Thank you for contacting us. We will prepare a quote and send it separately.

Best regards,
Customer Service"""
        
        mock_server = MagicMock()
        mock_server.search.return_value = [1]
        mock_server.fetch.return_value = {
            1: {b'RFC822': email_content.encode('utf-8')}
        }
        mock_server.__enter__.return_value = mock_server
        mock_server.__exit__.return_value = None
        
        with patch('backend.agents.quote_agent.imapclient.IMAPClient') as mock_imap_client:
            mock_imap_client.return_value = mock_server
            
            with patch('backend.agents.quote_agent.store_offer') as mock_store:
                offers = await _poll_inbox(spec, suppliers, max_duration=1)
                
                # No offers should be stored since no pricing was found
                assert len(offers) == 0
                mock_store.assert_not_called()
                
                # Email should still be marked as read
                mock_server.add_flags.assert_called()
    
    @pytest.mark.asyncio
    async def test_poll_inbox_non_supplier_email(self):
        """Test inbox polling with email from non-supplier."""
        spec = "test product"
        suppliers = [{"name": "Expected Supplier", "url": "http://expected.com"}]
        
        # Mock email from different sender
        email_content = """From: spam@random.com
Subject: Buy our products now!

This is a spam email that should be ignored."""
        
        mock_server = MagicMock()
        mock_server.search.return_value = [1]
        mock_server.fetch.return_value = {
            1: {b'RFC822': email_content.encode('utf-8')}
        }
        mock_server.__enter__.return_value = mock_server
        mock_server.__exit__.return_value = None
        
        with patch('backend.agents.quote_agent.imapclient.IMAPClient') as mock_imap_client:
            mock_imap_client.return_value = mock_server
            
            offers = await _poll_inbox(spec, suppliers, max_duration=1)
            
            # No offers should be found
            assert len(offers) == 0
            
            # Email should be marked as read to avoid reprocessing
            mock_server.add_flags.assert_called()
    
    @pytest.mark.asyncio
    async def test_poll_inbox_imap_connection_error(self):
        """Test inbox polling with IMAP connection errors."""
        spec = "test product"
        suppliers = [{"name": "Test Supplier", "url": "http://test.com"}]
        
        # Mock IMAP client to raise connection error
        with patch('backend.agents.quote_agent.imapclient.IMAPClient') as mock_imap_client:
            mock_imap_client.side_effect = Exception("Connection failed")
            
            # Should not raise exception, just log error and continue
            offers = await _poll_inbox(spec, suppliers, max_duration=1)
            
            assert len(offers) == 0
    
    @pytest.mark.asyncio
    async def test_poll_inbox_message_processing_error(self):
        """Test inbox polling with message processing errors."""
        spec = "test product"
        suppliers = [{"name": "Test Supplier", "url": "http://test.com"}]
        
        # Mock server that fails during message fetch
        mock_server = MagicMock()
        mock_server.search.return_value = [1, 2]  # Two messages
        mock_server.fetch.side_effect = [
            Exception("Fetch failed"),  # First message fails
            {2: {b'RFC822': b'From: test-supplier@example.com\nValid email'}}  # Second succeeds
        ]
        mock_server.__enter__.return_value = mock_server
        mock_server.__exit__.return_value = None
        
        with patch('backend.agents.quote_agent.imapclient.IMAPClient') as mock_imap_client:
            mock_imap_client.return_value = mock_server
            
            # Should continue processing despite error on first message
            offers = await _poll_inbox(spec, suppliers, max_duration=1)
            
            # Should attempt to process both messages
            assert mock_server.fetch.call_count == 2
    
    @pytest.mark.asyncio
    async def test_poll_inbox_duplicate_message_handling(self):
        """Test that duplicate messages are handled correctly."""
        spec = "test product"
        suppliers = [{"name": "Test Supplier", "url": "http://test.com"}]
        
        email_content = """From: test-supplier@example.com
Subject: Re: RFQ
Price: $10.00"""
        
        mock_server = MagicMock()
        # Return the same message ID multiple times (simulating multiple polls)
        mock_server.search.return_value = [1]
        mock_server.fetch.return_value = {
            1: {b'RFC822': email_content.encode('utf-8')}
        }
        mock_server.__enter__.return_value = mock_server
        mock_server.__exit__.return_value = None
        
        with patch('backend.agents.quote_agent.imapclient.IMAPClient') as mock_imap_client:
            mock_imap_client.return_value = mock_server
            
            with patch('backend.agents.quote_agent.store_offer') as mock_store:
                mock_store.return_value = 123
                
                # Simulate multiple polling cycles by patching asyncio.sleep
                poll_count = 0
                
                async def mock_sleep(duration):
                    nonlocal poll_count
                    poll_count += 1
                    if poll_count >= 2:  # Stop after 2 cycles
                        raise asyncio.CancelledError()
                
                with patch('asyncio.sleep', side_effect=mock_sleep):
                    try:
                        await _poll_inbox(spec, suppliers, max_duration=30)
                    except asyncio.CancelledError:
                        pass  # Expected termination
                
                # Store should only be called once despite multiple polls
                assert mock_store.call_count <= 1


class TestIMAPIntegration:
    """Integration tests for IMAP functionality."""
    
    @pytest.mark.asyncio
    async def test_quote_agent_with_imap_polling(self):
        """Test complete quote agent workflow with IMAP polling."""
        # Mock all external dependencies
        mock_suppliers = [
            {"name": "IMAP Test Supplier", "url": "http://imaptest.com", "source": "test"}
        ]
        
        with patch('backend.agents.quote_agent.find_suppliers_async') as mock_find:
            mock_find.return_value = mock_suppliers
            
            with patch('backend.agents.quote_agent.send_rfq') as mock_send:
                mock_send.return_value = None
                
                # Mock IMAP polling to return a sample offer
                mock_offers = [{
                    "price": 15.50,
                    "currency": "USD",
                    "lead_time": 7,
                    "lead_time_unit": "days",
                    "from_email": "imap-test-supplier@example.com",
                    "offer_id": 456
                }]
                
                with patch('backend.agents.quote_agent._poll_inbox') as mock_poll:
                    mock_poll.return_value = mock_offers
                    
                    agent = QuoteAgent()
                    results = await agent.process_quotes("test product", max_suppliers=1, poll_duration=1)
                    
                    assert results["suppliers_found"] == 1
                    assert results["rfqs_sent"] == 1
                    assert results["offers_received"] == 1
                    assert len(results["offers"]) == 1
                    assert results["offers"][0]["price"] == 15.50
    
    @pytest.mark.skip(reason="Requires MailHog running - enable for full integration testing")
    @pytest.mark.asyncio
    async def test_real_mailhog_integration(self):
        """Test with real MailHog instance."""
        # This test requires MailHog to be running on localhost:1025 (SMTP) and :1143 (IMAP)
        # Enable by removing @pytest.mark.skip and ensuring MailHog is running
        
        from backend.email.outgoing import send_rfq
        
        # Send a test RFQ
        test_email = "integration-test@example.com"
        test_spec = "integration test product"
        
        await send_rfq(test_email, test_spec)
        
        # Wait for email to be processed
        await asyncio.sleep(2)
        
        # Now test IMAP polling
        suppliers = [{"name": "Integration Test", "url": "http://test.com"}]
        
        # This would poll the actual MailHog IMAP server
        offers = await _poll_inbox(test_spec, suppliers, max_duration=5)
        
        # In a real test, you'd manually send a response email through MailHog
        # and verify it gets processed correctly
        pass 