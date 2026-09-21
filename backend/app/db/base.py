from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def ensure_schema_compatibility() -> None:
    """Apply the two small SQLite upgrades needed by the transport MVP.

    The project predates a migration framework and uses ``create_all``, which
    cannot alter an existing table. This preserves the local development data
    while making task_id nullable and adding transport-safe event metadata.
    Production databases should replace this with an Alembic migration.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "scheduled_events" in tables:
        columns = {column["name"]: column for column in inspector.get_columns("scheduled_events")}
        requires_rebuild = (
            "title" not in columns
            or "event_type" not in columns
            or not columns["task_id"].get("nullable", False)
        )
        if requires_rebuild:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE scheduled_events_transport_upgrade (
                        id INTEGER NOT NULL PRIMARY KEY,
                        task_id INTEGER,
                        user_id INTEGER NOT NULL,
                        event_type VARCHAR(20) NOT NULL DEFAULT 'task',
                        title VARCHAR(200) NOT NULL,
                        start_time DATETIME NOT NULL,
                        end_time DATETIME NOT NULL,
                        source VARCHAR(20) NOT NULL,
                        calendar_event_id VARCHAR(255),
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        FOREIGN KEY(task_id) REFERENCES tasks (id),
                        FOREIGN KEY(user_id) REFERENCES users (id)
                    )
                    """
                )
                connection.exec_driver_sql(
                    """
                    INSERT INTO scheduled_events_transport_upgrade
                    (id, task_id, user_id, event_type, title, start_time, end_time,
                     source, calendar_event_id, created_at, updated_at)
                    SELECT e.id, e.task_id, e.user_id, 'task',
                           COALESCE(t.title, 'Calendar event'),
                           e.start_time, e.end_time, e.source, e.calendar_event_id,
                           e.created_at, e.updated_at
                    FROM scheduled_events AS e
                    LEFT JOIN tasks AS t ON t.id = e.task_id
                    """
                )
                connection.exec_driver_sql("DROP TABLE scheduled_events")
                connection.exec_driver_sql(
                    "ALTER TABLE scheduled_events_transport_upgrade RENAME TO scheduled_events"
                )
                connection.exec_driver_sql(
                    "CREATE INDEX ix_scheduled_events_task_id ON scheduled_events (task_id)"
                )
                connection.exec_driver_sql(
                    "CREATE INDEX ix_scheduled_events_user_id ON scheduled_events (user_id)"
                )
                connection.exec_driver_sql(
                    "CREATE INDEX ix_scheduled_events_start_time ON scheduled_events (start_time)"
                )

    if "user_preferences" in tables:
        preference_columns = {column["name"] for column in inspector.get_columns("user_preferences")}
        if "timezone" not in preference_columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE user_preferences "
                    "ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'Europe/Warsaw'"
                )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
