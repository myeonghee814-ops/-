from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_missing_columns() -> None:
    """`Base.metadata.create_all` only creates tables that don't exist yet -
    it never alters an existing table's columns. There is no Alembic (or
    similar) migration tool in this project, so a lightweight ADD COLUMN
    pass runs here instead: harmless no-op when the column is already
    present, and it never touches existing rows/data.
    """

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if not inspector.has_table(table.name):
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                ddl_type = column.type.compile(dialect=engine.dialect)
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type}"
                # SQLite backfills existing rows with the DEFAULT given at
                # ADD COLUMN time (rather than leaving them NULL) - include
                # it for simple scalar defaults so old rows get "" instead
                # of None, which the response schemas (plain `str`, not
                # `str | None`) require.
                default = column.default.arg if column.default is not None else None
                if isinstance(default, str):
                    ddl += " DEFAULT '" + default.replace("'", "''") + "'"
                elif isinstance(default, bool):
                    ddl += f" DEFAULT {int(default)}"
                elif isinstance(default, (int, float)):
                    ddl += f" DEFAULT {default}"
                conn.execute(text(ddl))


def _drop_orphaned_columns() -> None:
    """Mirror of _add_missing_columns: a column removed from a model (e.g.
    performance_summary/innovation/advantages/limitations merged into
    result_summary) doesn't just become inert - if it was created NOT
    NULL, every future INSERT that no longer sets it fails outright with
    an IntegrityError, since SQLite has no concept of "this column isn't
    mapped anymore, ignore its constraint". Dropping it (supported since
    SQLite 3.35) keeps the live table's shape in sync with the current
    model instead of leaving that landmine behind.
    """

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if not inspector.has_table(table.name):
                continue
            model_columns = {column.name for column in table.columns}
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column_name in existing_columns - model_columns:
                conn.execute(text(f"ALTER TABLE {table.name} DROP COLUMN {column_name}"))


def init_db() -> None:
    from app.db import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _drop_orphaned_columns()
