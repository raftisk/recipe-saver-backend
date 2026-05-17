import pytest


async def test_register_returns_token_and_me_works(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@test.com", "password": "password123"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "token" in data
    assert data["user"]["email"] == "a@test.com"

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "a@test.com"


async def test_duplicate_email_register_returns_auth_failed(client):
    payload = {"email": "dup@test.com", "password": "password123"}
    await client.post("/api/v1/auth/register", json=payload)
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "auth_failed"


async def test_weak_password_register_returns_auth_failed(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "b@test.com", "password": "short"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "auth_failed"


async def test_login_success(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "c@test.com", "password": "password123"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "c@test.com", "password": "password123"},
    )
    assert r.status_code == 200
    assert "token" in r.json()


async def test_login_wrong_password_returns_auth_failed(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "d@test.com", "password": "password123"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "d@test.com", "password": "wrongpass"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "auth_failed"


async def test_login_unknown_email_returns_auth_failed(client):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "password123"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "auth_failed"


async def test_logout_revokes_session(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "e@test.com", "password": "password123"},
    )
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 204

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 401


async def test_extension_token_mints_working_token(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "f@test.com", "password": "password123"},
    )
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    ext = await client.post("/api/v1/auth/extension-token", headers=headers)
    assert ext.status_code == 201
    ext_token = ext.json()["token"]
    assert ext_token != token

    # both tokens work
    me1 = await client.get("/api/v1/auth/me", headers=headers)
    me2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ext_token}"})
    assert me1.status_code == 200
    assert me2.status_code == 200


async def test_unauthenticated_me_returns_401(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
