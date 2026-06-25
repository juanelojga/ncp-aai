from ncp_aai.db import session
from ncp_aai.objectives import import_objectives


def test_objective_import_is_idempotent_and_flags_weight_discrepancy(app_settings):
    first = import_objectives(settings=app_settings)
    second = import_objectives(settings=app_settings)

    assert first == second
    assert first["domains_imported"] == 10
    assert first["objectives_imported"] == 53
    assert first["weight_total_percent"] == 92
    assert first["weight_discrepancy"] is True

    with session(app_settings) as conn:
        domain_count = conn.execute("SELECT COUNT(*) AS count FROM domains").fetchone()["count"]
        objective_count = conn.execute(
            "SELECT COUNT(*) AS count FROM objectives"
        ).fetchone()["count"]
        topic_count = conn.execute("SELECT COUNT(*) AS count FROM topics").fetchone()["count"]

    assert domain_count == 10
    assert objective_count == 53
    assert topic_count == 53
