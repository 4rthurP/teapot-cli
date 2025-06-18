"""Tests for API client."""

import pytest
from unittest.mock import Mock, patch
import httpx

from teapot_cli.core.api import APIClient, APIError


def test_api_client_initialization(mock_config):
    """Test API client initialization."""
    with patch('teapot_cli.core.api.httpx.Client') as mock_client_class:
        client = APIClient(mock_config)
        
        mock_client_class.assert_called_once_with(
            base_url="https://api.test.com",
            timeout=10,
            headers={
                "User-Agent": "teapot-cli/0.1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "Bearer test-key",
            }
        )


def test_api_client_get_request(mock_config):
    """Test GET request."""
    with patch('teapot_cli.core.api.httpx.Client') as mock_client_class:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        api_client = APIClient(mock_config)
        result = api_client.get("/test")
        
        assert result == {"data": "test"}
        mock_client.get.assert_called_once_with("/test", params=None)


def test_api_client_post_request(mock_config):
    """Test POST request."""
    with patch('teapot_cli.core.api.httpx.Client') as mock_client_class:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        api_client = APIClient(mock_config)
        result = api_client.post("/test", {"key": "value"})
        
        assert result == {"success": True}
        mock_client.post.assert_called_once_with("/test", json={"key": "value"})


def test_api_client_error_handling(mock_config):
    """Test API error handling."""
    with patch('teapot_cli.core.api.httpx.Client') as mock_client_class:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not found"}
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        api_client = APIClient(mock_config)
        
        with pytest.raises(APIError) as exc_info:
            api_client.get("/nonexistent")
        
        assert exc_info.value.status_code == 404
        assert str(exc_info.value) == "Not found"


def test_api_client_context_manager(mock_config):
    """Test API client as context manager."""
    with patch('teapot_cli.core.api.httpx.Client') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        with APIClient(mock_config) as api_client:
            pass
        
        mock_client.close.assert_called_once()