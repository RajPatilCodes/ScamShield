from pathlib import Path

from app.catalog_content import load_manifest, publish_bundle
from app.catalog_models import CatalogBase
from app.database import SessionLocal, engine


CONTENT_MANIFEST = Path(__file__).resolve().parents[2] / "content" / "phase4" / "manifest.json"


def install_catalog():
    CatalogBase.metadata.create_all(bind=engine)
    bundle = load_manifest(CONTENT_MANIFEST)
    with SessionLocal() as db:
        publish_bundle(db, bundle, now=1_700_000_000)


def remove_catalog():
    CatalogBase.metadata.drop_all(bind=engine)
