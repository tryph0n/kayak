"""Pytest fixtures and configuration."""


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration (real API calls)"
    )
