from __future__ import annotations

from sqlalchemy import inspect, text


def ensure_runtime_schema(engine) -> None:
    inspector = inspect(engine)
    dialect = engine.dialect.name

    json_type = "JSON"
    if dialect == "postgresql":
        json_default = "'{}'::json"
    else:
        json_default = "'{}'"

    patches = {
        "ingestion_jobs": {
            "job_kind": "VARCHAR(32) NOT NULL DEFAULT 'import'",
            "workflow_id": "VARCHAR(160)",
            "request_payload": f"{json_type} NOT NULL DEFAULT {json_default}",
            "attempt_count": "INTEGER NOT NULL DEFAULT 1",
        },
        "eval_runs": {
            "workflow_id": "VARCHAR(160)",
            "request_payload": f"{json_type} NOT NULL DEFAULT {json_default}",
            "attempt_count": "INTEGER NOT NULL DEFAULT 1",
            "error_message": "TEXT",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in patches.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name in existing:
                    continue
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
