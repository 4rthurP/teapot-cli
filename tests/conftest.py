"""Test configuration and fixtures."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from teapot_cli.core.config import APIConfig, TeapotConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_dir):
    """Create a mock configuration for testing."""
    api_config = APIConfig(
        base_url="https://api.test.com",
        timeout=10,
        api_key="test-key",
    )

    config = TeapotConfig(
        api=api_config,
        verbosity=1,
    )

    return config


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for API testing."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response
    mock_client.put.return_value = mock_response
    mock_client.delete.return_value = mock_response

    return mock_client
