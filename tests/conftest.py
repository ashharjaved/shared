import os
import asyncio
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def require_test_db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; skipping DB-dependent tests")
    return url
