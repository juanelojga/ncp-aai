from fastapi.testclient import TestClient

import ncp_aai.main as main_module
from ncp_aai.ingestion.service import ingest_inbox_file
from ncp_aai.main import app, health, import_objectives_endpoint, list_objectives, settings_dep
from ncp_aai.objectives import import_objectives


def test_health_and_objective_endpoint_logic(app_settings):
    health_response = health(app_settings)
    assert health_response.status == "ok"

    imported = import_objectives_endpoint(app_settings)
    assert imported["weight_total_percent"] == 92

    body = list_objectives(app_settings)
    assert len(body["domains"]) == 10
    assert body["metadata"]["exam_weight_discrepancy_flag"] is True


def test_static_spa_does_not_swallow_api_routes(app_settings, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=\"root\">NCP-AAI app</div>", encoding="utf-8")
    monkeypatch.setattr(main_module, "WEB_DIST_DIR", dist)

    app.dependency_overrides[settings_dep] = lambda: app_settings
    try:
        client = TestClient(app)
        import_response = client.post("/admin/import-objectives")
        assert import_response.status_code == 200

        spa_response = client.get("/")
        assert spa_response.status_code == 200
        assert "NCP-AAI app" in spa_response.text

        api_response = client.get("/api/objectives")
        assert api_response.status_code == 200
        assert api_response.headers["content-type"].startswith("application/json")
        assert len(api_response.json()["domains"]) == 10
    finally:
        app.dependency_overrides.clear()


def test_start_investigation_returns_completed_local_job(app_settings):
    import_objectives(settings=app_settings)
    source = app_settings.app_inbox_dir / "ui.txt"
    source.write_text(
        "Human-agent interaction design should expose progress, feedback, and oversight.",
        encoding="utf-8",
    )
    ingest_inbox_file(
        "ui.txt",
        objective_ids=["objective-1.1"],
        topic_ids=["topic-1.1"],
        settings=app_settings,
    )

    app.dependency_overrides[settings_dep] = lambda: app_settings
    try:
        client = TestClient(app)
        response = client.post(
            "/api/topics/topic-1.1/investigations",
            json={"auto_ingest": False},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "complete"

        job_response = client.get(f"/api/investigations/{body['job_id']}")
        assert job_response.status_code == 200
        job = job_response.json()
        assert job["status"] == "complete"
        assert job["artifact_ids"]
    finally:
        app.dependency_overrides.clear()
