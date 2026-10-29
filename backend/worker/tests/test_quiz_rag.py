from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import AIJob, Article, Question
from pipeline.providers.base import GenerationResult, Usage
from pipeline.quiz_rag import QuizRagHandler, articles_needing_quiz, plan_quiz_jobs
from pipeline.validate import OutputRejected, StoredCorpus, validate_quiz_rag


def test_quiz_jobs_are_planned_once_from_saved_articles(make_event, settings, monkeypatch):
    event = make_event(status="published")
    monkeypatch.setattr("pipeline.quiz_rag.quiz_provider_ready", lambda _settings: True)
    with SessionLocal() as db:
        assert len(articles_needing_quiz(db)) == 1
        assert plan_quiz_jobs(db, settings) == 1
        assert plan_quiz_jobs(db, settings) == 0
        job = db.scalar(select(AIJob).where(AIJob.kind == "quiz_prep"))
        assert job is not None
        article = db.scalar(select(Article).where(Article.event_id == event.id))
        assert article is not None
        assert str(article.id) in job.payload["article_ids"]


def test_quiz_rag_rejects_invented_numbers_and_saves_grounded_ones(make_event, settings):
    event = make_event(status="published")
    with SessionLocal() as db:
        article = db.scalar(select(Article).where(Article.event_id == event.id))
        assert article is not None
        article_id = str(article.id)
        corpus = StoredCorpus(
            article_id=article_id,
            text="The Union Cabinet approved the National Fixture Mission with an outlay of 1500 crore.",
            sensitive=False,
        )
        try:
            validate_quiz_rag(
                {
                    "questions": [
                        {
                            "article_id": article_id,
                            "prompt": "Outlay koto chhilo according to the saved story?",
                            "options": ["9000 crore", "1500 crore", "20 crore", "4 crore"],
                            "correct_index": 0,
                            "explanation": "The Union Cabinet approved an outlay of 9000 crore for the mission.",
                        }
                    ]
                },
                {article_id: corpus},
            )
        except OutputRejected:
            pass
        else:
            raise AssertionError("invented outlay should be rejected")

        accepted = validate_quiz_rag(
            {
                "questions": [
                    {
                        "article_id": article_id,
                        "prompt": "National Fixture Mission-er outlay koto chhilo?",
                        "options": ["1500 crore", "500 crore", "2500 crore", "100 crore"],
                        "correct_index": 0,
                        "explanation": "The Union Cabinet approved the National Fixture Mission with an outlay of 1500 crore.",
                    }
                ]
            },
            {article_id: corpus},
        )
        assert accepted[0].correct_index == 0

        handler = QuizRagHandler(settings)
        job = AIJob(
            kind="quiz_prep",
            resource_type="article_batch",
            payload={"article_ids": [article_id]},
            dedupe_key=f"quiz:test:{uuid.uuid4()}",
            status="running",
        )
        db.add(job)
        db.commit()
        prepared_context = {
            "corpora": {
                article_id: {
                    "text": corpus.text,
                    "sensitive": False,
                    "event_id": str(event.id),
                    "event_date": event.date.isoformat(),
                    "category": "polity",
                    "source_urls": ["https://example.org/cabinet"],
                    "source_item_ids": [],
                }
            }
        }

        class _Prepared:
            context = prepared_context

        result = GenerationResult(
            data={
                "questions": [
                    {
                        "article_id": article_id,
                        "prompt": accepted[0].prompt,
                        "options": accepted[0].options,
                        "correct_index": 0,
                        "explanation": accepted[0].explanation,
                    }
                ]
            },
            raw_text="{}",
            usage=Usage(input_tokens=10, output_tokens=20, total_tokens=30),
            model="test-model",
        )
        ref = handler.accept(db, job, _Prepared(), result, "gemini", "test-model")
        assert ref == "questions:1"
        assert db.scalar(select(func.count(Question.id)).where(Question.article_id == article.id)) == 1
