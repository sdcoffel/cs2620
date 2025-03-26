import pytest

def pytest_configure(config):
    """Register custom markers with pytest."""
    config.addinivalue_line(
        "markers", 
        "integration: mark test as an integration test"
    )