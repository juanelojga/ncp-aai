import uuid

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session


def create_exercise_recommendation(
    *,
    topic_id: str | None,
    objective_id: str | None,
    concept: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    exercise_id = f"exercise-{uuid.uuid4().hex}"
    with session(settings) as conn:
        conn.execute(
            """
            INSERT INTO exercise_recommendations
                (id, topic_id, objective_id, title, body, reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                exercise_id,
                topic_id,
                objective_id,
                f"Review {concept}",
                f"Write a short explanation of {concept} and attach at least one stored citation.",
                "Created from quiz or feedback signals.",
            ),
        )
    return exercise_id
