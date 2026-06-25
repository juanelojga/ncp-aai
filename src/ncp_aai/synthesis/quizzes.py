import json
import uuid
from typing import Any

from ncp_aai.config import Settings, get_settings
from ncp_aai.db import session
from ncp_aai.models import QuizAttempt, QuizQuestion


def grade_quiz_attempt(
    *,
    quiz_question_id: str,
    selected_option: int,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    with session(settings) as db:
        question = db.get(QuizQuestion, quiz_question_id)
        if question is None:
            msg = f"Unknown quiz_question_id: {quiz_question_id}"
            raise ValueError(msg)
        is_correct = selected_option == question.correct_option
        score = 1.0 if is_correct else 0.0
        missed_concepts = [] if is_correct else [question.concept or question.prompt[:80]]
        attempt_id = f"attempt-{uuid.uuid4().hex}"
        db.add(
            QuizAttempt(
                id=attempt_id,
                topic_id=question.topic_id,
                objective_id=question.objective_id,
                quiz_question_id=quiz_question_id,
                selected_option=selected_option,
                is_correct=int(is_correct),
                score=score,
                missed_concepts_json=json.dumps(missed_concepts),
                rationale=question.rationale,
            )
        )
    return {
        "attempt_id": attempt_id,
        "is_correct": is_correct,
        "score": score,
        "rationale": question.rationale,
        "missed_concepts": missed_concepts,
    }
