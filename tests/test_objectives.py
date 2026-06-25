from sqlalchemy import func, select

from ncp_aai.db import session
from ncp_aai.models import Domain, Objective, Topic
from ncp_aai.objectives import import_objectives


def test_objective_import_is_idempotent_and_flags_weight_discrepancy(app_settings):
    first = import_objectives(settings=app_settings)
    second = import_objectives(settings=app_settings)

    assert first == second
    assert first["domains_imported"] == 10
    assert first["objectives_imported"] == 53
    assert first["weight_total_percent"] == 92
    assert first["weight_discrepancy"] is True

    with session(app_settings) as db:
        domain_count = db.scalar(select(func.count()).select_from(Domain))
        objective_count = db.scalar(select(func.count()).select_from(Objective))
        topic_count = db.scalar(select(func.count()).select_from(Topic))

    assert domain_count == 10
    assert objective_count == 53
    assert topic_count == 53
