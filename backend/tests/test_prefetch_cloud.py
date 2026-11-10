from app import prefetch


def test_active_jobs_skip_ir_on_cloud(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("CLOUD_LIGHT", raising=False)
    names = {n for n, _ in prefetch.active_jobs()}
    assert {"insat", "gibs", "storm_india", "default_pin"} <= names
    monkeypatch.setenv("CLOUD_LIGHT", "1")
    cloud = {n for n, _ in prefetch.active_jobs()}
    assert "insat" not in cloud
    assert "gibs" not in cloud
    assert "storm_india" not in cloud
    assert "default_pin" in cloud
    assert "cyclones" in cloud
