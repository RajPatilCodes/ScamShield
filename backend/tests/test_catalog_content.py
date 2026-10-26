import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog_config import GUIDE_REVIEW_PENDING, REQUIRED_GUIDE_IDS, RESOURCE_UNVERIFIED, RESOURCE_VERIFIED
from app.catalog_content import ContentError, GuideContent, ResourceContent, load_manifest, resource_definition_digest, validate_bundle


MANIFEST = Path(__file__).resolve().parents[2] / "content" / "phase4" / "manifest.json"


def test_phase4_content_manifest_is_complete_and_honest():
    bundle = load_manifest(MANIFEST)
    assert bundle.manifest.publication_status == "draft"
    assert {item.id for item in bundle.guides if item.language == "en"} == set(REQUIRED_GUIDE_IDS)
    assert all(item.review_status == GUIDE_REVIEW_PENDING for item in bundle.guides)
    assert all(item.verification_status == RESOURCE_UNVERIFIED for item in bundle.resources)
    assert all(item.content_digest is None for item in bundle.resources)
    assert all(item.knowledge_checks for item in bundle.lessons)
    assert bundle.manifest.content_digest == bundle.digest


def test_manifest_rejects_unverified_content_as_published():
    bundle = load_manifest(MANIFEST)
    bundle.manifest.publication_status = "published"
    with pytest.raises(ContentError, match="Published content"):
        validate_bundle(bundle)


def test_manifest_rejects_path_escape(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version":1,"revision":1,"jurisdiction":"IN","languages":["en"],"files":{"categories":"../categories.json","guides":[],"playbooks":"x","lessons":"x","checklists":"x","resources":"x"}}')
    with pytest.raises(ContentError):
        load_manifest(path)


def test_content_models_reject_unknown_fields_and_non_https_destinations():
    guide_value = json.loads((MANIFEST.parent / "guides" / "SC-001.json").read_text())[0]
    with pytest.raises(ValidationError):
        GuideContent.model_validate({**guide_value, "unexpected": True})

    resource_value = {
        "id": "resource-example",
        "language": "en",
        "name": "Example",
        "jurisdiction": "IN",
        "destination": "http://example.invalid/report",
        "publisher": "Draft",
        "source_references": [],
        "verification_status": "unverified",
        "content_digest": "a" * 64,
        "withdrawn": False,
    }
    with pytest.raises(ValidationError):
        ResourceContent.model_validate(resource_value)


def test_resource_digest_is_canonical_and_verified_resources_require_it():
    bundle = load_manifest(MANIFEST)
    resource = bundle.resources[0]
    resource.content_digest = resource_definition_digest(resource)
    bundle.manifest.content_digest = bundle.digest
    validate_bundle(bundle)

    resource.content_digest = "0" * 64
    bundle.manifest.content_digest = bundle.digest
    with pytest.raises(ContentError, match="content digest"):
        validate_bundle(bundle)

    resource.verification_status = RESOURCE_VERIFIED
    resource.destination = "https://example.invalid/report"
    resource.source_references = ["https://example.invalid/source"]
    resource.verification_date = 1_700_000_000
    resource.content_digest = None
    bundle.manifest.content_digest = bundle.digest
    with pytest.raises(ContentError, match="cannot claim verification"):
        validate_bundle(bundle)


def test_manifest_rejects_duplicate_publication_records():
    bundle = load_manifest(MANIFEST)
    bundle.categories.append(bundle.categories[0])
    with pytest.raises(ContentError, match="Duplicate category"):
        validate_bundle(bundle)
