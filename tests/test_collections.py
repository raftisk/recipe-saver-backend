import pytest

from tests.conftest import SAMPLE_HTML, SAMPLE_URL


async def _save_recipe(client, url=SAMPLE_URL):
    r = await client.post("/api/v1/recipes", json={"url": url, "html": SAMPLE_HTML})
    assert r.status_code == 201
    return r.json()["recipe"]["id"]


async def _create_col(client, name="My Col"):
    r = await client.post("/api/v1/collections", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


async def test_create_collection(auth_client):
    r = await auth_client.post("/api/v1/collections", json={"name": "Favourites"})
    assert r.status_code == 201
    assert r.json()["name"] == "Favourites"


async def test_create_duplicate_name_returns_409(auth_client):
    await auth_client.post("/api/v1/collections", json={"name": "Dupe"})
    r = await auth_client.post("/api/v1/collections", json={"name": "Dupe"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "collection_name_taken"


async def test_list_collections(auth_client):
    await auth_client.post("/api/v1/collections", json={"name": "B"})
    await auth_client.post("/api/v1/collections", json={"name": "A"})
    r = await auth_client.get("/api/v1/collections")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert names == sorted(names)


async def test_rename_collection(auth_client):
    cid = await _create_col(auth_client, "Old")
    r = await auth_client.patch(f"/api/v1/collections/{cid}", json={"name": "New"})
    assert r.status_code == 200
    assert r.json()["name"] == "New"


async def test_rename_collision_returns_409(auth_client):
    await _create_col(auth_client, "Taken")
    cid = await _create_col(auth_client, "Other")
    r = await auth_client.patch(f"/api/v1/collections/{cid}", json={"name": "Taken"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "collection_name_taken"


async def test_delete_collection_recipes_survive(auth_client):
    rid = await _save_recipe(auth_client)
    cid = await _create_col(auth_client)
    await auth_client.post(f"/api/v1/collections/{cid}/recipes/{rid}")

    d = await auth_client.delete(f"/api/v1/collections/{cid}")
    assert d.status_code == 204

    r = await auth_client.get(f"/api/v1/recipes/{rid}")
    assert r.status_code == 200


async def test_add_recipe_to_collection_idempotent(auth_client):
    rid = await _save_recipe(auth_client)
    cid = await _create_col(auth_client)

    r1 = await auth_client.post(f"/api/v1/collections/{cid}/recipes/{rid}")
    r2 = await auth_client.post(f"/api/v1/collections/{cid}/recipes/{rid}")
    assert r1.status_code == 204
    assert r2.status_code == 204

    listed = await auth_client.get(f"/api/v1/recipes?collection_id={cid}")
    assert listed.json()["total"] == 1


async def test_remove_recipe_from_collection(auth_client):
    rid = await _save_recipe(auth_client)
    cid = await _create_col(auth_client)
    await auth_client.post(f"/api/v1/collections/{cid}/recipes/{rid}")

    r = await auth_client.delete(f"/api/v1/collections/{cid}/recipes/{rid}")
    assert r.status_code == 204

    listed = await auth_client.get(f"/api/v1/recipes?collection_id={cid}")
    assert listed.json()["total"] == 0


async def test_cross_user_add_recipe_returns_404(client):
    t1 = (await client.post(
        "/api/v1/auth/register",
        json={"email": "cu1@test.com", "password": "password123"},
    )).json()["token"]
    t2 = (await client.post(
        "/api/v1/auth/register",
        json={"email": "cu2@test.com", "password": "password123"},
    )).json()["token"]

    rid = (await client.post(
        "/api/v1/recipes",
        json={"url": SAMPLE_URL, "html": SAMPLE_HTML},
        headers={"Authorization": f"Bearer {t1}"},
    )).json()["recipe"]["id"]

    cid = (await client.post(
        "/api/v1/collections",
        json={"name": "U2 col"},
        headers={"Authorization": f"Bearer {t2}"},
    )).json()["id"]

    r = await client.post(
        f"/api/v1/collections/{cid}/recipes/{rid}",
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
