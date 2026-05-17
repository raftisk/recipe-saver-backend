import pytest

from tests.conftest import BOGUS_HTML, SAMPLE_HTML, SAMPLE_URL


async def test_save_recipe_parses_fields(auth_client):
    r = await auth_client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["partial"] is False
    assert data["duplicate_of"] is None
    assert data["recipe"]["title"] == "Simple Pasta"
    assert data["recipe"]["ingredients"] is not None
    assert data["recipe"]["instructions"] is not None


async def test_save_bogus_html_returns_partial(auth_client):
    r = await auth_client.post(
        "/api/v1/recipes",
        json={"url": "https://example.com/bogus", "html": BOGUS_HTML},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["partial"] is True
    assert data["recipe"]["source_url"] == "https://example.com/bogus"
    assert any("parse_failed" in w for w in data["recipe"]["warnings"])


async def test_save_oversize_html_returns_413(auth_client):
    big_html = "x" * (2 * 1024 * 1024 + 1)
    r = await auth_client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": big_html},
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


async def test_duplicate_save_sets_duplicate_of(auth_client):
    payload = {"url": SAMPLE_URL, "html": SAMPLE_HTML}
    r1 = await auth_client.post("/api/v1/recipes", json=payload)
    r2 = await auth_client.post("/api/v1/recipes", json=payload)
    first_id = r1.json()["recipe"]["id"]
    assert r2.json()["duplicate_of"] == first_id


async def test_list_recipes_pagination(auth_client):
    for i in range(3):
        await auth_client.post(
            "/api/v1/recipes",
            json={"url": f"https://example.com/r{i}", "html": SAMPLE_HTML},
        )
    r = await auth_client.get("/api/v1/recipes?limit=2&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2

    r2 = await auth_client.get("/api/v1/recipes?limit=2&offset=2")
    assert len(r2.json()["items"]) == 1


async def test_list_recipes_q_filter(auth_client):
    await auth_client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
    )
    r = await auth_client.get("/api/v1/recipes?q=Simple")
    assert r.json()["total"] == 1

    r2 = await auth_client.get("/api/v1/recipes?q=nothingmatches")
    assert r2.json()["total"] == 0


async def test_list_recipes_collection_id_filter(auth_client):
    r1 = await auth_client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
    )
    recipe_id = r1.json()["recipe"]["id"]

    col = await auth_client.post("/api/v1/collections", json={"name": "Test Col"})
    col_id = col.json()["id"]
    await auth_client.post(f"/api/v1/collections/{col_id}/recipes/{recipe_id}")

    r = await auth_client.get(f"/api/v1/recipes?collection_id={col_id}")
    assert r.json()["total"] == 1


async def test_get_recipe(auth_client):
    r = await auth_client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
    )
    rid = r.json()["recipe"]["id"]
    r2 = await auth_client.get(f"/api/v1/recipes/{rid}")
    assert r2.status_code == 200
    assert r2.json()["id"] == rid


async def test_get_other_user_recipe_returns_404(client):
    t1 = (await client.post(
        "/api/v1/auth/register",
        json={"email": "u1r@test.com", "password": "password123"},
    )).json()["token"]
    t2 = (await client.post(
        "/api/v1/auth/register",
        json={"email": "u2r@test.com", "password": "password123"},
    )).json()["token"]

    r = await client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
        headers={"Authorization": f"Bearer {t1}"},
    )
    rid = r.json()["recipe"]["id"]

    r2 = await client.get(f"/api/v1/recipes/{rid}", headers={"Authorization": f"Bearer {t2}"})
    assert r2.status_code == 404


async def test_patch_recipe(auth_client):
    r = await auth_client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
    )
    rid = r.json()["recipe"]["id"]

    r2 = await auth_client.patch(f"/api/v1/recipes/{rid}", json={"title": "Updated"})
    assert r2.status_code == 200
    assert r2.json()["title"] == "Updated"


async def test_patch_other_user_recipe_returns_404(client):
    t1 = (await client.post(
        "/api/v1/auth/register",
        json={"email": "u1p@test.com", "password": "password123"},
    )).json()["token"]
    t2 = (await client.post(
        "/api/v1/auth/register",
        json={"email": "u2p@test.com", "password": "password123"},
    )).json()["token"]

    r = await client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
        headers={"Authorization": f"Bearer {t1}"},
    )
    rid = r.json()["recipe"]["id"]

    r2 = await client.patch(
        f"/api/v1/recipes/{rid}",
        json={"title": "Hack"},
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert r2.status_code == 404


async def test_delete_recipe(auth_client):
    r = await auth_client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
    )
    rid = r.json()["recipe"]["id"]

    d = await auth_client.delete(f"/api/v1/recipes/{rid}")
    assert d.status_code == 204

    g = await auth_client.get(f"/api/v1/recipes/{rid}")
    assert g.status_code == 404


async def test_delete_other_user_recipe_returns_404(client):
    t1 = (await client.post(
        "/api/v1/auth/register",
        json={"email": "u1d@test.com", "password": "password123"},
    )).json()["token"]
    t2 = (await client.post(
        "/api/v1/auth/register",
        json={"email": "u2d@test.com", "password": "password123"},
    )).json()["token"]

    r = await client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
        headers={"Authorization": f"Bearer {t1}"},
    )
    rid = r.json()["recipe"]["id"]

    r2 = await client.delete(
        f"/api/v1/recipes/{rid}",
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert r2.status_code == 404


async def test_unauthenticated_requests_return_401(client):
    endpoints = [
        ("GET", "/api/v1/recipes"),
        ("POST", "/api/v1/recipes"),
        ("GET", "/api/v1/recipes/fake-id"),
        ("PATCH", "/api/v1/recipes/fake-id"),
        ("DELETE", "/api/v1/recipes/fake-id"),
    ]
    for method, path in endpoints:
        r = await client.request(method, path)
        assert r.status_code == 401, f"{method} {path} should be 401"
        assert r.json()["error"]["code"] == "unauthorized"
