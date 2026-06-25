import uuid

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.models import ExerciseRecommendation


def create_exercise_recommendation(
    *,
    topic_id: str | None,
    objective_id: str | None,
    concept: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    exercise_id = f"exercise-{uuid.uuid4().hex}"
    with session(settings) as db:
        db.add(
            ExerciseRecommendation(
                id=exercise_id,
                topic_id=topic_id,
                objective_id=objective_id,
                title=f"Review {concept}",
                body=(
                    f"Write a short explanation of {concept} and attach at least one stored "
                    "citation."
                ),
                reason="Created from quiz or feedback signals.",
            )
        )
    return exercise_id
