"""API client for teapot-cli."""

from typing import Any, Dict, Optional
import httpx
from rich.console import Console

from teapot_cli.core.config import TeapotConfig

console = Console()


class APIError(Exception):
    """Custom exception for API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class APIClient:
    """HTTP client for API interactions."""
    
    def __init__(self, config: TeapotConfig):
        self.config = config
        self.client = httpx.Client(
            base_url=config.api.base_url,
            timeout=config.api.timeout,
            headers=self._get_headers(),
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {
            "User-Agent": "teapot-cli/0.1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        if self.config.api.api_key:
            headers["Authorization"] = f"Bearer {self.config.api.api_key}"
        
        return headers
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and raise errors if needed."""
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("message", f"HTTP {response.status_code}")
            except Exception:
                message = f"HTTP {response.status_code}: {response.text}"
            
            raise APIError(message, response.status_code)
        
        try:
            return response.json()
        except Exception:
            return {"data": response.text}
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request."""
        if self.config.verbose:
            console.print(f"[blue]GET[/blue] {endpoint}")
        
        response = self.client.get(endpoint, params=params)
        return self._handle_response(response)
    
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a POST request."""
        if self.config.verbose:
            console.print(f"[green]POST[/green] {endpoint}")
        
        response = self.client.post(endpoint, json=data)
        return self._handle_response(response)
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a PUT request."""
        if self.config.verbose:
            console.print(f"[yellow]PUT[/yellow] {endpoint}")
        
        response = self.client.put(endpoint, json=data)
        return self._handle_response(response)
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        if self.config.verbose:
            console.print(f"[red]DELETE[/red] {endpoint}")
        
        response = self.client.delete(endpoint)
        return self._handle_response(response)
    
    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()