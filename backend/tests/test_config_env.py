from __future__ import annotations

import importlib
from pathlib import Path


def test_settings_loads_dotenv_from_working_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WORKFLOW_BACKEND", raising=False)
    (tmp_path / ".env").write_text("WORKFLOW_BACKEND=immediate\n", encoding="utf-8")

    import app.core.config as config

    reloaded_config = importlib.reload(config)

    assert reloaded_config.Settings().workflow_backend == "immediate"
