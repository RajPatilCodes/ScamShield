from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def migration_config(tmp_path):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    url = f"sqlite:///{tmp_path / 'catalog.db'}"
    config.attributes.update(database_url=url, migration_target=url)
    return config


def test_catalog_migration_is_additive(tmp_path):
    config = migration_config(tmp_path)
    command.upgrade(config, "head")
    engine = create_engine(config.attributes["database_url"])
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
        tables = set(inspect(db).get_table_names())
        assert {"users", "analyses", "catalog_publications", "catalog_guide_revisions", "emergency_playbook_revisions", "lesson_revisions", "checklist_revisions", "trusted_resource_revisions"}.issubset(tables)
        assert {column["name"] for column in inspect(db).get_columns("lesson_revisions")} >= {"sections", "knowledge_checks"}
        digest = next(column for column in inspect(db).get_columns("trusted_resource_revisions") if column["name"] == "content_digest")
        assert digest["nullable"] is True
    engine.dispose()
