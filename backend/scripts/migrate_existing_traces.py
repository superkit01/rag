#!/usr/bin/env python3
"""
Migrate existing AnswerTrace records to sessions.
Groups traces by knowledge space and date, creating Session records.
"""
import sys
from datetime import timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, UTC
from app.db.session import build_session_factory, build_engine
from app.models.entities import Session, AnswerTrace
from app.core.config import get_settings


def migrate_traces_to_sessions():
    """Group existing traces into sessions by knowledge space and time."""
    settings = get_settings()
    engine = build_engine(settings)
    session_factory = build_session_factory(settings, engine)
    db = session_factory()

    try:
        # Get all existing traces without session_id
        traces_without_session = db.query(AnswerTrace).filter(
            AnswerTrace.session_id.is_(None)
        ).order_by(AnswerTrace.created_at).all()

        if not traces_without_session:
            print("No traces to migrate.")
            return

        print(f"Found {len(traces_without_session)} traces to migrate.")

        # Group traces by knowledge space and time windows
        # Traces within 1 hour go to same session, on same day, for same space
        sessions_created = 0
        traces_migrated = 0

        current_session_key = None
        current_session = None

        for trace in traces_without_session:
            # Create session key: knowledge_space_id + date + hour window
            trace_date = trace.created_at.date()
            trace_hour = trace.created_at.hour

            session_key = f"{trace.knowledge_space_id}_{trace_date}_{trace_hour // 2}"  # 2-hour windows

            # Create new session if key changed
            if session_key != current_session_key:
                # Create session
                current_session = Session(
                    name=f"历史会话 {trace_date.strftime('%Y-%m-%d')}",
                    knowledge_space_id=trace.knowledge_space_id,
                    created_at=trace.created_at,
                    updated_at=trace.created_at
                )
                db.add(current_session)
                db.flush()  # Get the ID
                sessions_created += 1
                current_session_key = session_key
                print(f"Created session: {current_session.name}")

            # Link trace to session
            trace.session_id = current_session.id
            traces_migrated += 1

        # Commit all changes
        db.commit()

        print(f"\nMigration complete:")
        print(f"  - Sessions created: {sessions_created}")
        print(f"  - Traces migrated: {traces_migrated}")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_traces_to_sessions()
