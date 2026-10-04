import os
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import make_url

from app.database import Base
from app import models

config = context.config
url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL")
confirmed = config.attributes.get("migration_target") or os.environ.get("MIGRATION_DATABASE_URL")
if not url or url != confirmed:
    raise ValueError("Set DATABASE_URL and identical MIGRATION_DATABASE_URL explicitly")
parsed = make_url(url)
if parsed.drivername == "sqlite" and (not parsed.database or Path(parsed.database).resolve().name.casefold() == "scamshield.db"):
    raise ValueError("Refusing migrations against the protected local database")


def validate_existing_schema(connection):
    inspector = inspect(connection)
    if set(inspector.get_table_names()) - {"alembic_version"} != {"users", "analyses"}:
        raise ValueError("Existing schema does not match the approved baseline")
    expected = {
        "users": {"id": ("INTEGER", False), "email": ("VARCHAR(255)", False),
                  "password_hash": ("VARCHAR(255)", False), "created_at": ("DATETIME", False)},
        "analyses": {"id": ("INTEGER", False), "user_id": ("INTEGER", False), "content": ("TEXT", False),
                     "score": ("INTEGER", False), "verdict": ("VARCHAR(30)", False), "created_at": ("DATETIME", False)},
    }
    for table, columns in expected.items():
        found = {col["name"]: (str(col["type"]).replace("TIMESTAMP", "DATETIME"), col["nullable"]) for col in inspector.get_columns(table)}
        if found != columns or inspector.get_pk_constraint(table)["constrained_columns"] != ["id"]:
            raise ValueError("Existing columns do not match the approved baseline")
        indexes = inspector.get_indexes(table)
        wanted = {("ix_users_email", ("email",), True)} if table == "users" else {("ix_analyses_user_id", ("user_id",), False)}
        actual = {(index["name"], tuple(index["column_names"]), bool(index["unique"])) for index in indexes}
        if actual != wanted or inspector.get_unique_constraints(table):
            raise ValueError("Existing indexes do not match the approved baseline")
        if inspector.get_foreign_keys(table) or inspector.get_check_constraints(table):
            raise ValueError("Unexpected baseline constraints")


if context.is_offline_mode():
    raise ValueError("Offline migration cannot validate the database target")
else:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def sqlite_connect(connection, _):
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")

        @event.listens_for(engine, "begin")
        def sqlite_begin(connection):
            connection.exec_driver_sql("BEGIN")
    with engine.begin() as connection:
        adoption = config.attributes.get("adopt_existing_schema") or os.environ.get("ADOPT_EXISTING_SCHEMA") == "1"
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        stamping = context.get_context().opts["fn"].__name__ == "do_stamp"
        if stamping and not adoption:
            raise ValueError("Stamp requires explicit validated baseline adoption")
        if adoption:
            if context.get_revision_argument() != "0001":
                raise ValueError("Validated adoption may only stamp baseline revision 0001")
            validate_existing_schema(connection)
        elif "users" in inspect(connection).get_table_names() and "alembic_version" not in inspect(connection).get_table_names():
            raise ValueError("Existing unversioned schema requires explicit validated baseline adoption")
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
