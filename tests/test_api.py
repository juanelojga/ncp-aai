from ncp_aai.main import health, import_objectives_endpoint, list_objectives


def test_health_and_objective_endpoint_logic(app_settings):
    health_response = health(app_settings)
    assert health_response.status == "ok"

    imported = import_objectives_endpoint(app_settings)
    assert imported["weight_total_percent"] == 92

    body = list_objectives(app_settings)
    assert len(body["domains"]) == 10
    assert body["metadata"]["exam_weight_discrepancy_flag"] is True
