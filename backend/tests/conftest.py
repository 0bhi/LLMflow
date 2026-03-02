import hashlib
import io
import json
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


@pytest.fixture
def mock_storage():
    """A mock MinIO client that stores objects in memory."""
    storage = MagicMock()
    _store: dict[str, bytes] = {}

    def put_object(bucket, path, data, length=None, **kwargs):
        if isinstance(data, io.BytesIO):
            _store[path] = data.read()
        else:
            _store[path] = data

    def get_object(bucket, path):
        content = _store.get(path, b"")
        resp = MagicMock()
        resp.read.return_value = content
        resp.close = MagicMock()
        resp.release_conn = MagicMock()
        return resp

    storage.put_object = MagicMock(side_effect=put_object)
    storage.get_object = MagicMock(side_effect=get_object)
    storage._store = _store
    return storage


@pytest.fixture
def sample_jsonl_content() -> bytes:
    rows = []
    for i in range(100):
        rows.append(json.dumps({
            "instruction": f"Explain concept {i}",
            "input": "",
            "output": f"Concept {i} is about topic {i}.",
        }))
    return "\n".join(rows).encode("utf-8")


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
