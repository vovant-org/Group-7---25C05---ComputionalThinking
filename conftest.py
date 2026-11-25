

import pytest


@pytest.fixture(autouse=True)
def _no_tts_retry_pause(monkeypatch):
    """Tests use fake TTS engines: do not wait between retries."""
    from modules.providers import edge_tts_provider
    monkeypatch.setattr(edge_tts_provider, "RETRY_PAUSE_S", 0.0)
