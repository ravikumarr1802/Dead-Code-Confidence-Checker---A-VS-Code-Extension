"""
API Client for fetching remote datasets.
Demonstrates decorators and dynamic getattr calls.
"""
import time
import requests

def retry_request(max_retries=3):
    """Decorator to retry flaky API calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(1)
        return wrapper
    return decorator

class HTTPClient:
    def __init__(self, base_url):
        self.base_url = base_url

    @retry_request(max_retries=2)
    def fetch_data(self, endpoint, method="GET", payload=None):
        """
        Fetches data using a dynamic requests method call.
        Static analyzers might struggle to track which HTTP methods are actually used.
        """
        url = f"{self.base_url}/{endpoint}"
        
        # DYNAMIC CALL: Uses getattr to dynamically call requests.get, requests.post, etc.
        request_func = getattr(requests, method.lower())
        
        if method.upper() in ["POST", "PUT"]:
            response = request_func(url, json=payload)
        else:
            response = request_func(url)
            
        return response.json()

# DEAD CODE: Function is defined but never referenced in the project.
def build_auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
