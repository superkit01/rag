from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.workflows import worker


def test_worker_skips_temporal_connection_in_immediate_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr(worker, "get_settings", lambda: Settings(workflow_backend="immediate"))

    async def fail_connect(settings: Settings):
        raise AssertionError("Temporal should not be connected in immediate mode.")

    monkeypatch.setattr(worker, "connect_temporal_client", fail_connect)

    asyncio.run(worker.main())

    assert "Temporal worker skipped" in capsys.readouterr().out
