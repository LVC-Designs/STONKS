import pytest
import asyncio

# Use a single event loop for all tests so the SQLAlchemy async engine's
# connection pool doesn't get stranded on a closed loop between tests.
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
