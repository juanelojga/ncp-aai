import json
import uuid
from typing import Any

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session


def grade_quiz_attempt(
    *,
    quiz_question_id: str,
    selected_option: int,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    with session(settings) as conn:
        question = conn.execute(
            "SELECT * FROM quiz_questions WHERE id = ?", (quiz_question_id,)
        ).fetchone()
        if question is None:
            msg = f"Unknown quiz_question_id: {quiz_question_id}"
            raise ValueError(msg)
        is_correct = selected_option == question["correct_option"]
        score = 1.0 if is_correct else 0.0
        missed_concepts = [] if is_correct else [question["concept"] or question["prompt"][:80]]
        attempt_id = f"attempt-{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO quiz_attempts
                (id, topic_id, objective_id, quiz_question_id, selected_option, is_correct,
                 score, missed_concepts_json, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                question["topic_id"],
                question["objective_id"],
                quiz_question_id,
                selected_option,
                int(is_correct),
                score,
                json.dumps(missed_concepts),
                question["rationale"],
            ),
        )
    return {
        "attempt_id": attempt_id,
        "is_correct": is_correct,
        "score": score,
        "rationale": question["rationale"],
        "missed_concepts": missed_concepts,
    }
