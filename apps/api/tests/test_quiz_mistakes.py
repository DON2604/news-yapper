from __future__ import annotations

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import MistakeVaultEntry, Question, QuizAttempt


def _answer_key() -> dict[str, int]:
    with SessionLocal() as db:
        return {str(q.id): q.correct_index for q in db.scalars(select(Question)).all()}


def test_daily_quiz_flow_records_mistakes_once(client, seeded, make_user, auth):
    headers = auth(make_user())
    overview = client.get("/api/v1/quizzes/daily", headers=headers).json()
    assert overview["session"] is None and overview["pool_size"] >= 10

    session = client.post("/api/v1/quizzes/sessions", json={"type": "daily"}, headers=headers).json()
    assert 10 <= session["question_count"] <= 15
    assert all("correct_index" not in q for q in session["questions"])
    assert (
        client.post("/api/v1/quizzes/sessions", json={"type": "daily"}, headers=headers).json()["id"]
        == session["id"]
    )

    key = _answer_key()
    first, second = session["questions"][0], session["questions"][1]
    wrong = (key[first["id"]] + 1) % 4
    res = client.post(
        f"/api/v1/quizzes/sessions/{session['id']}/answers",
        json={"question_id": first["id"], "selected_index": wrong, "response_ms": 4200},
        headers=headers,
    ).json()
    assert res["is_correct"] is False and res["correct_index"] == key[first["id"]]
    assert res["explanation"] and res["mistake"]["status"] == "active"

    repeat = client.post(
        f"/api/v1/quizzes/sessions/{session['id']}/answers",
        json={"question_id": first["id"], "selected_index": key[first["id"]]},
        headers=headers,
    ).json()
    assert repeat["already_answered"] is True and repeat["is_correct"] is False

    right = client.post(
        f"/api/v1/quizzes/sessions/{session['id']}/answers",
        json={"question_id": second["id"], "selected_index": key[second["id"]]},
        headers=headers,
    ).json()
    assert right["is_correct"] is True and right["progress"]["score"] == 1

    done = client.post(f"/api/v1/quizzes/sessions/{session['id']}/finish", headers=headers).json()
    assert done["xp_earned"] == 10 + 20
    assert done["session"]["completed_at"]

    with SessionLocal() as db:
        assert db.scalar(select(func.count(MistakeVaultEntry.id))) == 1
        assert db.scalar(select(func.count(QuizAttempt.id))) == 2

    mistakes = client.get("/api/v1/mistakes", headers=headers).json()
    assert len(mistakes) == 1 and mistakes[0]["incorrect_choice"] == wrong


def test_question_outside_session_and_foreign_session(client, seeded, make_user, auth):
    alice, bob = make_user("Alice"), make_user("Bob")
    session = client.post("/api/v1/quizzes/sessions", json={"type": "daily"}, headers=auth(alice)).json()
    qid = session["questions"][0]["id"]
    foreign = client.post(
        f"/api/v1/quizzes/sessions/{session['id']}/answers",
        json={"question_id": qid, "selected_index": 0},
        headers=auth(bob),
    )
    assert foreign.status_code == 404
    assert client.get(f"/api/v1/quizzes/sessions/{session['id']}", headers=auth(bob)).status_code == 404
    in_session = [q["id"] for q in session["questions"]]
    with SessionLocal() as db:
        outside = db.scalars(select(Question.id).where(Question.id.not_in(in_session))).first()
    res = client.post(
        f"/api/v1/quizzes/sessions/{session['id']}/answers",
        json={"question_id": str(outside), "selected_index": 0},
        headers=auth(alice),
    )
    assert res.status_code == 404


def test_mistake_review_resolves_without_erasing_history(client, seeded, make_user, auth):
    headers = auth(make_user())
    session = client.post("/api/v1/quizzes/sessions", json={"type": "daily"}, headers=headers).json()
    key = _answer_key()
    q = session["questions"][0]
    client.post(
        f"/api/v1/quizzes/sessions/{session['id']}/answers",
        json={"question_id": q["id"], "selected_index": (key[q["id"]] + 1) % 4},
        headers=headers,
    )
    mistake = client.get("/api/v1/mistakes", headers=headers).json()[0]

    snoozed = client.post(
        f"/api/v1/mistakes/{mistake['id']}/review", json={"action": "snooze"}, headers=headers
    ).json()
    assert snoozed["mistake"]["review_after"]

    wrong_again = client.post(
        f"/api/v1/mistakes/{mistake['id']}/review",
        json={"action": "answer", "selected_index": (key[q["id"]] + 2) % 4},
        headers=headers,
    ).json()
    assert wrong_again["is_correct"] is False and wrong_again["mistake"]["error_count"] == 2

    fixed = client.post(
        f"/api/v1/mistakes/{mistake['id']}/review",
        json={"action": "answer", "selected_index": key[q["id"]]},
        headers=headers,
    ).json()
    assert fixed["is_correct"] is True and fixed["mistake"]["status"] == "resolved"
    assert client.get("/api/v1/mistakes", headers=headers).json() == []
    assert len(client.get("/api/v1/mistakes", params={"status": "all"}, headers=headers).json()) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count(QuizAttempt.id))) == 3


def test_mistake_isolation(client, seeded, make_user, auth):
    alice, bob = make_user("Alice"), make_user("Bob")
    session = client.post("/api/v1/quizzes/sessions", json={"type": "daily"}, headers=auth(alice)).json()
    key = _answer_key()
    q = session["questions"][0]
    client.post(
        f"/api/v1/quizzes/sessions/{session['id']}/answers",
        json={"question_id": q["id"], "selected_index": (key[q["id"]] + 1) % 4},
        headers=auth(alice),
    )
    mistake_id = client.get("/api/v1/mistakes", headers=auth(alice)).json()[0]["id"]
    assert client.get("/api/v1/mistakes", headers=auth(bob)).json() == []
    res = client.post(f"/api/v1/mistakes/{mistake_id}/review", json={"action": "resolve"}, headers=auth(bob))
    assert res.status_code == 404


def test_practice_session_for_article(client, seeded, make_user, auth):
    headers = auth(make_user())
    res = client.post(
        "/api/v1/quizzes/sessions",
        json={"type": "practice", "article_slug": "demo-g20-new-delhi-african-union"},
        headers=headers,
    )
    assert res.status_code == 201 and res.json()["question_count"] == 2
    missing = client.post(
        "/api/v1/quizzes/sessions", json={"type": "practice", "article_slug": "nope"}, headers=headers
    )
    assert missing.status_code == 404


def test_weak_topics_are_prioritised(seeded, make_user, db):
    from datetime import date

    from app.models import QuizSession, UserPreferences
    from app.services.quiz import select_daily_questions, topic_accuracy, weak_topics

    user = make_user()
    polity = db.scalars(select(Question).where(Question.exam_topic == "polity").limit(4)).all()
    session = QuizSession(
        user_id=user.id, type="practice", session_date=date.today(), question_count=len(polity)
    )
    db.add(session)
    db.flush()
    for q in polity:
        db.add(
            QuizAttempt(
                session_id=session.id,
                user_id=user.id,
                question_id=q.id,
                selected_index=(q.correct_index + 1) % 4,
                is_correct=False,
            )
        )
    db.commit()

    assert weak_topics(topic_accuracy(db, user.id)) == ["polity"]
    prefs = db.scalar(select(UserPreferences).where(UserPreferences.user_id == user.id))
    picks = select_daily_questions(db, user, prefs, date.today())
    assert len({p.question.id for p in picks}) == len(picks) >= 10
    assert any(p.reason == "Weak topic boost" and p.question.exam_topic == "polity" for p in picks)
    assert select_daily_questions(db, user, prefs, date.today())[0].question.id == picks[0].question.id
