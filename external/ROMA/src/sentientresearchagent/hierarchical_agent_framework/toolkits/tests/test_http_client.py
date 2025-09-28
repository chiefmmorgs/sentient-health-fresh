"""
Fixed tests for DataHTTPClient using simpler approach with self-contained test methods.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import httpx

from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import (
    DataHTTPClient, HTTPClientError
)


class TestHTTPClientBasics:
    """Test basic HTTP client functionality."""
    
    def test_initialization(self):
        """Test client initialization."""
        client = DataHTTPClient(default_timeout=10.0, max_retries=5)
        
        assert client._default_timeout == 10.0
        assert client._max_retries == 5
        assert client._endpoints == {}
        assert client._clients == {}
    
    @pytest.mark.asyncio
    async def test_add_and_get_endpoints(self):
        """Test adding endpoints and getting endpoint summary."""
        client = DataHTTPClient()
        
        await client.add_endpoint("api1", "https://api1.com")
        await client.add_endpoint("api2", "https://api2.com", headers={"Auth": "token"})
        
        endpoints = client.get_endpoints()
        assert endpoints == {
            "api1": "https://api1.com",
            "api2": "https://api2.com"
        }
        
        # Check endpoint configuration
        assert client._endpoints["api1"]["base_url"] == "https://api1.com"
        assert client._endpoints["api2"]["headers"]["Auth"] == "token"
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_successful_request(self):
        """Test successful HTTP request."""
        client = DataHTTPClient()
        
        # Mock httpx client
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            result = await client.get("test", "/data")
            
            assert result == {"success": True}
            mock_httpx.request.assert_called_once()
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self):
        """Test HTTP error handling."""
        client = DataHTTPClient()
        
        # Mock httpx client to raise HTTP error
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        
        error = httpx.HTTPStatusError("404 Not Found", request=Mock(), response=mock_response)
        mock_httpx.request.side_effect = error
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get("test", "/not-found")
            
            assert exc_info.value.status_code == 404
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_retry_logic(self):
        """Test retry logic for server errors."""
        client = DataHTTPClient(max_retries=2, retry_delay=0.1)
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        
        error = httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response)
        mock_httpx.request.side_effect = error
        
        with patch('httpx.AsyncClient', return_value=mock_httpx), \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError):
                await client.get("test", "/server-error")
            
            # Should retry: 1 initial + 2 retries = 3 total attempts
            assert mock_httpx.request.call_count == 3
            # Should sleep twice (between retries)
            assert mock_sleep.call_count == 2
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_header_management(self):
        """Test header update functionality."""
        client = DataHTTPClient()
        
        await client.add_endpoint("test", "https://api.test.com", headers={"Auth": "old_token"})
        
        # Update headers
        await client.update_endpoint_headers("test", {"Auth": "new_token"})
        
        assert client._endpoints["test"]["headers"]["Auth"] == "new_token"
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_endpoint_removal(self):
        """Test endpoint removal."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            # Simulate that a client was created by triggering _get_client
            client._get_client("test")
            
            # Endpoint should exist
            assert "test" in client._endpoints
            assert "test" in client._clients
            
            # Remove endpoint
            await client.remove_endpoint("test")
            
            # Endpoint should be gone
            assert "test" not in client._endpoints
            assert "test" not in client._clients
            # Mock client should be closed
            mock_httpx.aclose.assert_called_once()
        
        await client.aclose()
    
    def test_unknown_endpoint_error(self):
        """Test error when using unknown endpoint."""
        client = DataHTTPClient()
        
        with pytest.raises(ValueError, match="Endpoint 'unknown' not configured"):
            client._get_client("unknown")
    
    def test_unix_to_iso8601_utility(self):
        """Test Unix timestamp to ISO8601 conversion utility."""
        # Test with valid timestamp
        result = DataHTTPClient.unix_to_iso8601(1640995200000)  # 2022-01-01T00:00:00Z
        assert result == "2022-01-01T00:00:00Z"
        
        # Test with None
        result = DataHTTPClient.unix_to_iso8601(None)
        assert result is None
        
        # Test with zero/falsy values
        result = DataHTTPClient.unix_to_iso8601(0)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        mock_httpx = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            async with DataHTTPClient() as client:
                await client.add_endpoint("test", "https://api.test.com")
                assert "test" in client._endpoints
            
            # After context exit, should be cleaned up
            # The aclose should have been called automatically


class TestHTTPClientIntegration:
    """Integration tests for HTTP client."""
    
    @pytest.mark.asyncio
    async def test_multiple_endpoints_workflow(self):
        """Test workflow with multiple endpoints."""
        client = DataHTTPClient()
        
        # Mock responses for different endpoints
        mock_httpx1 = AsyncMock()
        mock_httpx2 = AsyncMock()
        
        mock_response1 = Mock()
        mock_response1.json.return_value = {"service": "api1"}
        mock_response1.raise_for_status = Mock()
        
        mock_response2 = Mock()
        mock_response2.json.return_value = {"service": "api2"}  
        mock_response2.raise_for_status = Mock()
        
        mock_httpx1.request.return_value = mock_response1
        mock_httpx2.request.return_value = mock_response2
        
        with patch('httpx.AsyncClient', side_effect=[mock_httpx1, mock_httpx2]):
            # Add multiple endpoints
            await client.add_endpoint("service1", "https://api1.com")
            await client.add_endpoint("service2", "https://api2.com")
            
            # Make requests to both
            result1 = await client.get("service1", "/data")
            result2 = await client.get("service2", "/info")
            
            assert result1 == {"service": "api1"}
            assert result2 == {"service": "api2"}
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_post_request_with_data(self):
        """Test POST request with JSON data."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"created": True, "id": 123}
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            post_data = {"name": "test", "value": 42}
            result = await client.post("test", "/create", json_data=post_data)
            
            assert result == {"created": True, "id": 123}
            
            # Verify POST was called correctly
            call_args = mock_httpx.request.call_args
            assert call_args.kwargs["method"] == "POST"
            assert call_args.kwargs["json"] == post_data
        
        await client.aclose()


class TestHTTPClientEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        """Test handling of invalid JSON responses."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Not JSON"
        mock_response.raise_for_status = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError, match="Invalid JSON response"):
                await client.get("test", "/invalid-json")
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_custom_timeout_and_retries(self):
        """Test custom timeout and retry parameters."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        error = httpx.RequestError("Timeout")
        mock_httpx.request.side_effect = error
        
        with patch('httpx.AsyncClient', return_value=mock_httpx), \
             patch('asyncio.sleep', new_callable=AsyncMock):
            
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError):
                await client.get("test", "/timeout", timeout=1.0, retries=1)
            
            # Should attempt 1 initial + 1 retry = 2 total
            assert mock_httpx.request.call_count == 2
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_endpoint_headers(self):
        """Test updating headers for non-existent endpoint."""
        client = DataHTTPClient()
        
        with pytest.raises(ValueError, match="Endpoint 'nonexistent' not configured"):
            await client.update_endpoint_headers("nonexistent", {"header": "value"})
        
        await client.aclose()