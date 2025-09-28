"""
Comprehensive tests for DataHTTPClient covering all functionality.
Tests HTTP operations, error handling, retry logic, and endpoint management.
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
        client = DataHTTPClient(default_timeout=10.0, max_retries=5, retry_delay=0.5)
        
        assert client._default_timeout == 10.0
        assert client._max_retries == 5
        assert client._retry_delay == 0.5
        assert client._endpoints == {}
        assert client._clients == {}
    
    def test_initialization_defaults(self):
        """Test client initialization with defaults."""
        client = DataHTTPClient()
        
        assert client._default_timeout == 30.0
        assert client._max_retries == 3
        assert client._retry_delay == 1.0
    
    @pytest.mark.asyncio
    async def test_add_endpoint_basic(self):
        """Test adding basic endpoints."""
        client = DataHTTPClient()
        
        await client.add_endpoint("api1", "https://api1.com")
        await client.add_endpoint("api2", "https://api2.com", headers={"Auth": "token"})
        
        assert "api1" in client._endpoints
        assert "api2" in client._endpoints
        assert client._endpoints["api1"]["base_url"] == "https://api1.com"
        assert client._endpoints["api2"]["headers"]["Auth"] == "token"
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_add_endpoint_with_timeout(self):
        """Test adding endpoint with custom timeout."""
        client = DataHTTPClient()
        
        await client.add_endpoint("api", "https://api.com", timeout=15.0)
        
        assert client._endpoints["api"]["timeout"] == 15.0
        
        await client.aclose()
    
    def test_get_endpoints(self):
        """Test getting endpoint summary."""
        client = DataHTTPClient()
        
        # Add endpoints synchronously for testing
        client._endpoints = {
            "api1": {"base_url": "https://api1.com"},
            "api2": {"base_url": "https://api2.com"}
        }
        
        endpoints = client.get_endpoints()
        assert endpoints == {
            "api1": "https://api1.com",
            "api2": "https://api2.com"
        }


class TestHTTPRequests:
    """Test HTTP request functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_get_request(self):
        """Test successful GET request."""
        client = DataHTTPClient()
        
        # Mock httpx client
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "data": "test"}
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            result = await client.get("test", "/data")
            
            assert result == {"success": True, "data": "test"}
            mock_httpx.request.assert_called_once_with(
                "GET", 
                "https://api.test.com/data",
                params=None,
                headers=None,
                timeout=30.0
            )
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_get_request_with_params(self):
        """Test GET request with parameters."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"data": "filtered"}
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            await client.get("test", "/data", params={"filter": "active", "limit": 10})
            
            mock_httpx.request.assert_called_with(
                "GET",
                "https://api.test.com/data", 
                params={"filter": "active", "limit": 10},
                headers=None,
                timeout=30.0
            )
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_post_request(self):
        """Test POST request."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"created": True}
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            result = await client.post("test", "/create", json={"name": "test"})
            
            assert result == {"created": True}
            mock_httpx.request.assert_called_with(
                "POST",
                "https://api.test.com/create",
                params=None,
                headers=None,
                timeout=30.0,
                json={"name": "test"}
            )
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_request_with_custom_headers(self):
        """Test request with custom headers."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"authenticated": True}
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com", headers={"Auth": "Bearer token"})
            await client.request("GET", "test", "/secure")
            
            # Should merge endpoint headers with request
            call_args = mock_httpx.request.call_args
            assert call_args[1]["headers"]["Auth"] == "Bearer token"
        
        await client.aclose()


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_http_status_error(self):
        """Test HTTP status error handling."""
        client = DataHTTPClient()
        
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
            assert "Not Found" in str(exc_info.value)
        
        await client.aclose()
    
    @pytest.mark.asyncio 
    async def test_timeout_error(self):
        """Test timeout error handling."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_httpx.request.side_effect = httpx.TimeoutException("Request timeout")
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get("test", "/slow")
            
            assert "timeout" in str(exc_info.value).lower()
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test connection error handling."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_httpx.request.side_effect = httpx.ConnectError("Connection failed")
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get("test", "/unreachable")
            
            assert "connection" in str(exc_info.value).lower()
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_unknown_endpoint_error(self):
        """Test unknown endpoint error."""
        client = DataHTTPClient()
        
        with pytest.raises(ValueError, match="Unknown endpoint"):
            await client.get("nonexistent", "/data")
    
    @pytest.mark.asyncio
    async def test_json_decode_error(self):
        """Test JSON decode error handling."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid response"
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get("test", "/invalid-json")
            
            assert "json" in str(exc_info.value).lower()
        
        await client.aclose()


class TestRetryLogic:
    """Test retry logic for transient errors."""
    
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        """Test retry logic for 5xx server errors."""
        client = DataHTTPClient(max_retries=2, retry_delay=0.1)
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        
        # First two calls fail, third succeeds
        error = httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response)
        success_response = Mock()
        success_response.json.return_value = {"success": True}
        success_response.raise_for_status = Mock()
        
        mock_httpx.request.side_effect = [error, error, success_response]
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            result = await client.get("test", "/data")
            
            assert result == {"success": True}
            assert mock_httpx.request.call_count == 3  # 1 initial + 2 retries
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self):
        """Test that 4xx errors are not retried."""
        client = DataHTTPClient(max_retries=2)
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        error = httpx.HTTPStatusError("400 Bad Request", request=Mock(), response=mock_response)
        mock_httpx.request.side_effect = error
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError):
                await client.get("test", "/data")
            
            assert mock_httpx.request.call_count == 1  # No retries for 4xx
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test behavior when all retries are exhausted."""
        client = DataHTTPClient(max_retries=2, retry_delay=0.1)
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        
        error = httpx.HTTPStatusError("503 Service Unavailable", request=Mock(), response=mock_response)
        mock_httpx.request.side_effect = error
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get("test", "/data")
            
            assert exc_info.value.status_code == 503
            assert mock_httpx.request.call_count == 3  # 1 initial + 2 retries
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test retry logic for timeout errors."""
        client = DataHTTPClient(max_retries=2, retry_delay=0.1)
        
        mock_httpx = AsyncMock()
        timeout_error = httpx.TimeoutException("Request timeout")
        success_response = Mock()
        success_response.json.return_value = {"success": True}
        success_response.raise_for_status = Mock()
        
        mock_httpx.request.side_effect = [timeout_error, success_response]
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            result = await client.get("test", "/data")
            
            assert result == {"success": True}
            assert mock_httpx.request.call_count == 2  # 1 initial + 1 retry
        
        await client.aclose()


class TestClientManagement:
    """Test HTTP client lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_client_creation_per_endpoint(self):
        """Test that clients are created per endpoint."""
        client = DataHTTPClient()
        
        with patch('httpx.AsyncClient') as mock_httpx_class:
            mock_client1 = AsyncMock()
            mock_client2 = AsyncMock()
            mock_httpx_class.side_effect = [mock_client1, mock_client2]
            
            await client.add_endpoint("api1", "https://api1.com")
            await client.add_endpoint("api2", "https://api2.com")
            
            assert "api1" in client._clients
            assert "api2" in client._clients
            assert client._clients["api1"] == mock_client1
            assert client._clients["api2"] == mock_client2
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_client_reuse_for_same_endpoint(self):
        """Test that the same client is reused for the same endpoint."""
        client = DataHTTPClient()
        
        with patch('httpx.AsyncClient') as mock_httpx_class:
            mock_httpx_instance = AsyncMock()
            mock_httpx_class.return_value = mock_httpx_instance
            
            await client.add_endpoint("api", "https://api.com")
            
            # Make multiple requests to same endpoint
            mock_response = Mock()
            mock_response.json.return_value = {"data": "test"}
            mock_response.raise_for_status = Mock()
            mock_httpx_instance.request.return_value = mock_response
            
            await client.get("api", "/data1")
            await client.get("api", "/data2")
            
            # Should create client only once
            assert mock_httpx_class.call_count == 1
            assert mock_httpx_instance.request.call_count == 2
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_client_cleanup(self):
        """Test proper client cleanup."""
        client = DataHTTPClient()
        
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        
        with patch('httpx.AsyncClient', side_effect=[mock_client1, mock_client2]):
            await client.add_endpoint("api1", "https://api1.com")
            await client.add_endpoint("api2", "https://api2.com")
            
            await client.aclose()
            
            # All clients should be closed
            mock_client1.aclose.assert_called_once()
            mock_client2.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager_usage(self):
        """Test using client as async context manager."""
        mock_client = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            async with DataHTTPClient() as client:
                await client.add_endpoint("api", "https://api.com")
                
                mock_response = Mock()
                mock_response.json.return_value = {"data": "test"}
                mock_response.raise_for_status = Mock()
                mock_client.request.return_value = mock_response
                
                result = await client.get("api", "/data")
                assert result == {"data": "test"}
            
            # Client should be automatically closed
            mock_client.aclose.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions and helpers."""
    
    def test_unix_to_iso8601_utility(self):
        """Test unix timestamp to ISO8601 conversion utility."""
        from sentientresearchagent.hierarchical_agent_framework.toolkits.utils.http_client import unix_to_iso8601
        
        # Test regular timestamp
        iso_string = unix_to_iso8601(1704067200)
        assert iso_string == "2024-01-01T00:00:00Z"
        
        # Test millisecond timestamp
        iso_string = unix_to_iso8601(1704067200000)
        assert iso_string == "2024-01-01T00:00:00Z"
    
    def test_iso8601_to_unix_utility(self):
        """Test ISO8601 to unix timestamp conversion utility."""
        from sentientresearchagent.hierarchical_agent_framework.toolkits.utils.http_client import iso8601_to_unix
        
        # Test with Z suffix
        unix_timestamp = iso8601_to_unix("2024-01-01T00:00:00Z")
        assert unix_timestamp == 1704067200
        
        # Test with timezone offset
        unix_timestamp = iso8601_to_unix("2024-01-01T00:00:00+00:00")
        assert unix_timestamp == 1704067200


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Test handling of empty responses."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.text = ""
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            result = await client.get("test", "/empty")
            
            assert result == {}
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_very_large_response(self):
        """Test handling of very large responses."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        # Simulate large response
        large_data = {"items": [{"id": i, "data": f"item_{i}"} for i in range(10000)]}
        mock_response.json.return_value = large_data
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            result = await client.get("test", "/large")
            
            assert len(result["items"]) == 10000
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_unicode_handling(self):
        """Test handling of unicode characters in responses."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"message": "Hello 世界", "emoji": "🚀"}
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            result = await client.get("test", "/unicode")
            
            assert result["message"] == "Hello 世界"
            assert result["emoji"] == "🚀"
        
        await client.aclose()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        client = DataHTTPClient()
        
        mock_httpx = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = Mock()
        mock_httpx.request.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_httpx):
            await client.add_endpoint("test", "https://api.test.com")
            
            # Make concurrent requests
            tasks = []
            for i in range(5):
                task = client.get("test", f"/data{i}")
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            assert all(result == {"success": True} for result in results)
            assert mock_httpx.request.call_count == 5
        
        await client.aclose()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])