import pytest

from .catalog_fixtures import install_catalog, remove_catalog


@pytest.fixture(autouse=True)
def catalog_content():
    install_catalog()
    yield
    remove_catalog()


def test_public_catalog_is_guest_accessible_and_complete(client):
    response = client.get("/v1/catalog/guides?limit=50")
    assert response.status_code == 200
    assert response.headers["x-catalog-revision"] == "1"
    assert response.headers["x-catalog-status"] == "draft"
    assert len(response.json()["items"]) == 33
    assert response.json()["items"][0]["id"] == "SC-001"
    assert response.json()["items"][0]["review_status"] == "pending_editorial_review"
    assert response.headers["x-catalog-digest"]


def test_hindi_catalog_falls_back_visibly(client):
    response = client.get("/v1/catalog/guides/SC-001?language=hi")
    assert response.status_code == 200
    assert response.json()["language"] == {"requested_language": "hi", "content_language": "en", "fallback_used": True}


def test_category_cursor_follows_display_order(client):
    first = client.get("/v1/catalog/categories?limit=1")
    assert first.status_code == 200
    assert first.json()["items"][0]["id"] == "payments"
    cursor = first.json()["next_cursor"]
    assert cursor

    second = client.get(f"/v1/catalog/categories?limit=1&cursor={cursor}")
    assert second.status_code == 200
    assert second.json()["items"][0]["id"] == "offers"
    assert second.headers["x-catalog-revision"] == first.headers["x-catalog-revision"]
    assert second.headers["x-catalog-digest"] == first.headers["x-catalog-digest"]


def test_draft_publication_import_is_idempotent_and_revisioned(client):
    from pathlib import Path

    from app.catalog_content import load_manifest, publish_bundle
    from app.database import SessionLocal

    manifest = Path(__file__).resolve().parents[2] / "content" / "phase4" / "manifest.json"
    bundle = load_manifest(manifest)
    with SessionLocal() as db:
        assert publish_bundle(db, bundle, now=1_700_000_001) == bundle.digest
        bundle.manifest.revision = 2
        bundle.manifest.content_digest = None
        assert publish_bundle(db, bundle, now=1_700_000_002) == bundle.digest

    response = client.get("/v1/catalog/guides?limit=1")
    assert response.status_code == 200
    assert response.headers["x-catalog-revision"] == "2"
    assert response.headers["x-catalog-status"] == "draft"


def test_catalog_supports_category_filter_and_knowledge_checks(client):
    response = client.get("/v1/catalog/guides?limit=50&category_id=payments")
    assert response.status_code == 200
    assert response.json()["items"]
    assert all(item["category_id"] == "payments" for item in response.json()["items"])

    lesson = client.get("/v1/learning/lessons/lesson-pause-verify")
    assert lesson.status_code == 200
    assert lesson.json()["knowledge_checks"][0]["correct_option"] == 0


def test_public_endpoints_are_read_only_and_bounded(client):
    assert client.get("/v1/emergency/playbooks").status_code == 200
    assert client.get("/v1/learning/lessons").status_code == 200
    assert client.get("/v1/checklists").status_code == 200
    resources = client.get("/v1/resources").json()["items"]
    assert resources and all(item["verification_status"] == "unverified" for item in resources)
    assert all(item["content_digest"] is None for item in resources)
    assert client.get("/v1/catalog/search?q=payment").status_code == 200
    assert client.get("/v1/catalog/guides?limit=51").status_code == 422
    assert client.get("/v1/catalog/guides?category_id=not valid").status_code == 422
    assert client.get("/v1/catalog/guides/not-a-guide").status_code == 422
    assert client.get("/v1/catalog/search?q=").status_code == 422
    assert client.post("/v1/catalog/guides", json={}).status_code == 405
