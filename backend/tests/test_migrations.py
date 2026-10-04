from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.database import Base, validate_disposable_database


def migration_config(tmp_path, adoption=False):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    url = f"sqlite:///{tmp_path / 'synthetic.db'}"
    config.attributes.update(database_url=url, migration_target=url, adopt_existing_schema=adoption)
    return config


def test_fresh_migration_and_integrity(tmp_path):
    config = migration_config(tmp_path)
    command.upgrade(config, "head")
    engine = create_engine(config.attributes["database_url"])
    validate_disposable_database(engine, tmp_path)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        assert "auth_sessions" in inspect(connection).get_table_names()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users(email, password_hash) VALUES ('synthetic@example.com','unchanged')"))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO users(email, password_hash) VALUES ('synthetic@example.com','duplicate')"))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO auth_sessions(id,user_id,created_at,idle_expires_at,absolute_expires_at) VALUES ('synthetic',1,1,3,2)"))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO auth_sessions(id,user_id,created_at,idle_expires_at,absolute_expires_at) VALUES ('missing-owner',999,1,2,3)"))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO auth_challenges(digest,user_id,purpose,expires_at) VALUES ('synthetic',1,'access',3)"))
    engine.dispose()


def test_validated_existing_adoption_preserves_records(tmp_path):
    config = migration_config(tmp_path)
    command.upgrade(config, "0001")
    engine = create_engine(config.attributes["database_url"])
    validate_disposable_database(engine, tmp_path)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users(id,email,password_hash) VALUES (7,'legacy@example.com','legacy-hash')"))
        connection.execute(text("INSERT INTO analyses(id,user_id,content,score,verdict) VALUES (9,7,'synthetic original',85,'high-risk')"))
        before_users = connection.execute(text("SELECT * FROM users")).all()
        before_analyses = connection.execute(text("SELECT * FROM analyses")).all()
        connection.execute(text("DROP TABLE alembic_version"))
    with pytest.raises(ValueError, match="adoption"):
        command.upgrade(config, "head")
    config.attributes["adopt_existing_schema"] = True
    command.stamp(config, "0001")
    config.attributes["adopt_existing_schema"] = False
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id,email,password_hash,created_at FROM users")).all() == before_users
        assert connection.execute(text("SELECT * FROM analyses")).all() == before_analyses
        assert connection.execute(text("SELECT email_verified,is_active FROM users")).one() == (0, 1)
    engine.dispose()


def test_unknown_schema_cannot_be_stamped(tmp_path):
    config = migration_config(tmp_path, adoption=True)
    engine = create_engine(config.attributes["database_url"])
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE unexpected (id INTEGER)"))
    with pytest.raises(ValueError, match="baseline"):
        command.stamp(config, "0001")
    engine.dispose()


def test_stamping_without_explicit_adoption_is_rejected(tmp_path):
    config = migration_config(tmp_path)
    with pytest.raises(ValueError, match="explicit validated"):
        command.stamp(config, "head")


@pytest.mark.parametrize("drift", ["column", "index"])
def test_existing_schema_drift_prevents_adoption(tmp_path, drift):
    config = migration_config(tmp_path)
    command.upgrade(config, "0001")
    engine = create_engine(config.attributes["database_url"])
    validate_disposable_database(engine, tmp_path)
    with engine.begin() as connection:
        if drift == "column":
            connection.execute(text("ALTER TABLE users ADD COLUMN unexpected TEXT"))
        else:
            connection.execute(text("CREATE INDEX unexpected ON users(password_hash)"))
        connection.execute(text("DROP TABLE alembic_version"))
    config.attributes["adopt_existing_schema"] = True
    with pytest.raises(ValueError, match="columns|indexes"):
        command.stamp(config, "0001")
    engine.dispose()


def test_protected_database_alias_and_case_are_rejected(tmp_path):
    config = migration_config(tmp_path)
    protected = tmp_path / "SCAMSHIELD.DB"
    alias = tmp_path / "alias.db"
    alias.symlink_to(protected)
    url = f"sqlite:///{alias}"
    config.attributes.update(database_url=url, migration_target=url)
    with pytest.raises(ValueError, match="protected"):
        command.upgrade(config, "head")
    assert not protected.exists()


def test_target_confirmation_and_protected_database(tmp_path):
    config = migration_config(tmp_path)
    config.attributes["migration_target"] = "sqlite:///different.db"
    with pytest.raises(ValueError, match="identical"):
        command.upgrade(config, "head")
    url = f"sqlite:///{tmp_path / 'scamshield.db'}"
    config.attributes.update(database_url=url, migration_target=url)
    with pytest.raises(ValueError, match="protected"):
        command.upgrade(config, "head")
    assert not (tmp_path / "scamshield.db").exists()
