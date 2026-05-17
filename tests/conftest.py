import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).parent.parent


@pytest.fixture()
def test_db_url(tmp_path):
    db_path = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        cwd=BACKEND_DIR,
    )
    assert result.returncode == 0, result.stderr.decode()
    return url


@pytest_asyncio.fixture()
async def client(test_db_url):
    from db.session import get_session
    from main import app

    engine = create_async_engine(test_db_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture()
async def auth_client(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@test.com", "password": "password123"},
    )
    assert resp.status_code == 201
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    client._test_user = resp.json()["user"]
    return client


SAMPLE_HTML = (Path(__file__).parent / "fixtures" / "sample_recipe.html").read_text()
SAMPLE_URL = "https://example.com/simple-pasta"
BOGUS_HTML = "<html><body>nothing here</body></html>"
