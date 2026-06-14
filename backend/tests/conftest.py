import pytest
import asyncio
from typing import AsyncGenerator


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
async def db_session():
    # Setup test DB session (mock or real)
    # TODO: initialize test database connection
    yield None
    # TODO: cleanup
