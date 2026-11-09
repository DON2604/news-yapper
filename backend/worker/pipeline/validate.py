"""Validation of model output. Schema-shaped output is NOT verification: every claim is
also checked against the evidence the model was given."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from pipeline.normalize import STOPWORDS

Category = Literal[
    "polity", "economy", "science", "international", "environment", "awards", "sports", "other"
]
ExamTag = Literal["SSC", "UPSC", "STATE_PSC", "BANKING", "RAILWAYS", "GENERAL"]

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*%?")
_WORD = re.compile(r"[a-z0-9]+")
_EMOJI = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]")
SLANG = ("lol", "lmao", "dude", "dudee", "demn", "demnn", "bro", "yaar", "omg", "wtf")
MIN_OVERLAP = 0.35


class OutputRejected(Exception):
    """The whole response is unusable (wrong shape / wrong events) - try another model or retry."""


class KeyFactOut(BaseModel):
    claim: str = Field(min_length=10, max_length=320)
    source_item_ids: list[str] = Field(min_length=1, max_length=5)


class QuizOut(BaseModel):
    question: str = Field(min_length=10, max_length=300)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=10, max_length=500)
    evidence_source_item_ids: list[str] = Field(min_length=1, max_length=5)

    @field_validator("options")
    @classmethod
    def _options(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value]
        if any(not v or len(v) > 160 for v in cleaned):
            raise ValueError("options must be 1-160 chars")
        if len({v.lower() for v in cleaned}) != 4:
            raise ValueError("options must be unique")
        return cleaned


class ArticleOut(BaseModel):
    event_id: str
    headline_banglish: str = Field(min_length=8, max_length=180)
    neutral_summary: str = Field(min_length=40, max_length=1400)
    banglish_summary: str = Field(min_length=20, max_length=1000)
    category: Category
    published_event_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    key_facts: list[KeyFactOut] = Field(min_length=2, max_length=5)
    why_it_matters: str = Field(min_length=10, max_length=700)
    exam_tags: list[ExamTag] = Field(default_factory=list, max_length=6)
    importance_score: int = Field(ge=0, le=100)
    quiz: list[QuizOut] = Field(default_factory=list, max_length=3)
    uncertainties: list[str] = Field(default_factory=list, max_length=6)
    sensitive_story: bool = False


class NewsBatchOut(BaseModel):
    articles: list[ArticleOut] = Field(min_length=1, max_length=3)


class CrunchBulletOut(BaseModel):
    text: str = Field(min_length=3, max_length=320)
    source_refs: list[str] = Field(min_length=1, max_length=6)


class CrunchSectionOut(BaseModel):
    topic: str = Field(min_length=1, max_length=60)
    bullets: list[CrunchBulletOut] = Field(default_factory=list, max_length=12)


class CrunchFlashcardOut(BaseModel):
    front: str = Field(min_length=3, max_length=320)
    back: str = Field(min_length=1, max_length=480)
    source_refs: list[str] = Field(min_length=1, max_length=6)
    exam_topic: str | None = Field(default=None, max_length=32)


class CrunchOut(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    concise_bullets: list[CrunchBulletOut] = Field(min_length=1, max_length=25)
    topic_sections: list[CrunchSectionOut] = Field(default_factory=list, max_length=8)
    mnemonics: list[str] = Field(default_factory=list, max_length=6)
    exam_traps: list[CrunchBulletOut] = Field(default_factory=list, max_length=10)
    flashcards: list[CrunchFlashcardOut] = Field(default_factory=list, max_length=15)


# -- evidence helpers --------------------------------------------------------------------------


def numbers_in(text: str) -> set[str]:
    return {
        n.replace(",", "").rstrip("%")
        for n in _NUMBER.findall(text)
        if len(n.replace(",", "").rstrip("%")) >= 2
    }


def content_words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if len(w) >= 4 and w not in STOPWORDS]


def overlap_ratio(claim: str, evidence: str) -> float:
    words = content_words(claim)
    if not words:
        return 1.0
    evidence_words = set(content_words(evidence))
    prefixes = {w[:5] for w in evidence_words}
    hits = sum(1 for w in words if w in evidence_words or w[:5] in prefixes)
    return hits / len(words)


def unsupported_numbers(text: str, evidence: str) -> set[str]:
    return numbers_in(text) - numbers_in(evidence)


@dataclass
class EventEvidence:
    event_id: str
    sensitive: bool
    item_texts: dict[str, str]
    item_urls: dict[str, str]
    # Event + publication dates the model was shown; years/days from them are not invented numbers.
    known_dates: str = ""

    def text_for(self, ids: list[str]) -> str:
        return " ".join(self.item_texts.get(i, "") for i in ids)

    @property
    def all_text(self) -> str:
        return " ".join(self.item_texts.values())


@dataclass
class ValidatedQuestion:
    prompt: str
    options: list[str]
    correct_index: int
    explanation: str
    evidence_ids: list[str]
    status: str
    flags: list[str] = field(default_factory=list)


@dataclass
class ValidatedArticle:
    event_id: str
    article: ArticleOut
    key_facts: list[dict[str, Any]]
    questions: list[ValidatedQuestion]
    flags: list[str]
    sensitive: bool

    @property
    def publishable(self) -> bool:
        return not self.flags


def _tone_violations(text: str) -> bool:
    lowered = f" {text.lower()} "
    return bool(_EMOJI.search(text)) or any(f" {s} " in lowered for s in SLANG)


def validate_news_batch(
    data: dict[str, Any], evidence: dict[str, EventEvidence], today: date
) -> list[ValidatedArticle]:
    try:
        batch = NewsBatchOut.model_validate(data)
    except ValidationError as exc:
        raise OutputRejected(f"Schema validation failed: {exc.error_count()} errors") from exc
    ids = [a.event_id for a in batch.articles]
    if len(set(ids)) != len(ids) or not set(ids) <= set(evidence):
        raise OutputRejected("Output event_ids do not match the requested events")

    results: list[ValidatedArticle] = []
    for art in batch.articles:
        ev = evidence[art.event_id]
        flags: list[str] = []
        facts: list[dict[str, Any]] = []
        for fact in art.key_facts:
            refs = [r for r in fact.source_item_ids if r in ev.item_texts]
            if not refs:
                flags.append("fact_with_unknown_source")
                continue
            support = ev.text_for(refs)
            missing = unsupported_numbers(fact.claim, f"{support} {ev.known_dates}")
            if missing:
                flags.append(f"unsupported_number:{','.join(sorted(missing))}")
            if overlap_ratio(fact.claim, support) < MIN_OVERLAP:
                flags.append("low_evidence_overlap")
            facts.append({"claim": fact.claim, "source_item_ids": refs})
        if len(facts) < 2:
            flags.append("too_few_supported_facts")
        missing_summary = unsupported_numbers(art.neutral_summary, f"{ev.all_text} {ev.known_dates}")
        if missing_summary:
            flags.append(f"summary_unsupported_number:{','.join(sorted(missing_summary))}")
        if art.published_event_date and art.published_event_date > today.isoformat():
            flags.append("future_event_date")
        sensitive = ev.sensitive or art.sensitive_story
        if sensitive:
            flags.append("sensitive_story_needs_editor")
            if _tone_violations(art.headline_banglish + " " + art.banglish_summary):
                flags.append("tone_violation_on_sensitive_story")
        if art.uncertainties:
            flags.append("model_reported_uncertainty")

        questions: list[ValidatedQuestion] = []
        for quiz in art.quiz:
            refs = [r for r in quiz.evidence_source_item_ids if r in ev.item_texts]
            q_flags: list[str] = []
            if not refs:
                q_flags.append("no_valid_evidence")
            support = ev.text_for(refs) if refs else ev.all_text
            answer = quiz.options[quiz.correct_index]
            if overlap_ratio(answer, support) < 0.6 and not (
                numbers_in(answer) and numbers_in(answer) <= numbers_in(support)
            ):
                q_flags.append("answer_not_in_evidence")
            if unsupported_numbers(quiz.question, f"{support} {ev.known_dates}"):
                q_flags.append("question_unsupported_number")
            questions.append(
                ValidatedQuestion(
                    prompt=quiz.question,
                    options=quiz.options,
                    correct_index=quiz.correct_index,
                    explanation=quiz.explanation,
                    evidence_ids=refs,
                    status="validated" if not q_flags and not sensitive else "needs_review",
                    flags=q_flags,
                )
            )
        results.append(
            ValidatedArticle(
                event_id=art.event_id,
                article=art,
                key_facts=facts,
                questions=questions,
                flags=sorted(set(flags)),
                sensitive=sensitive,
            )
        )
    return results


@dataclass
class ValidatedCrunch:
    output: CrunchOut
    warnings: list[str]


def validate_crunch(data: dict[str, Any], allowed_refs: set[str], max_flashcards: int) -> ValidatedCrunch:
    try:
        out = CrunchOut.model_validate(data)
    except ValidationError as exc:
        raise OutputRejected(f"Schema validation failed: {exc.error_count()} errors") from exc
    warnings: list[str] = []
    total = 0
    dropped = 0

    def keep(items: list[Any]) -> list[Any]:
        nonlocal total, dropped
        kept = []
        for item in items:
            total += 1
            refs = [r for r in item.source_refs if r in allowed_refs]
            if not refs:
                dropped += 1
                continue
            item.source_refs = refs
            kept.append(item)
        return kept

    out.concise_bullets = keep(out.concise_bullets)
    out.exam_traps = keep(out.exam_traps)
    out.flashcards = keep(out.flashcards)
    for section in out.topic_sections:
        section.bullets = keep(section.bullets)
    if total and dropped / total > 0.3:
        raise OutputRejected(f"{dropped}/{total} items cited unknown sources")
    if dropped:
        warnings.append(f"Dropped {dropped} item(s) that cited unknown sources.")
    if not out.concise_bullets:
        raise OutputRejected("No supported bullets left after validation")
    if len(out.flashcards) > max_flashcards:
        out.flashcards = out.flashcards[:max_flashcards]
    return ValidatedCrunch(output=out, warnings=warnings)


class RagQuestionOut(BaseModel):
    article_id: str
    prompt: str = Field(min_length=10, max_length=300)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=10, max_length=500)

    @field_validator("options")
    @classmethod
    def _options(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value]
        if any(not v or len(v) > 160 for v in cleaned):
            raise ValueError("options must be 1-160 chars")
        if len({v.lower() for v in cleaned}) != 4:
            raise ValueError("options must be unique")
        return cleaned


class RagQuizBatchOut(BaseModel):
    questions: list[RagQuestionOut] = Field(min_length=1, max_length=8)


class ChatAnswerOut(BaseModel):
    answer: str = Field(min_length=20, max_length=900)


@dataclass
class StoredCorpus:
    article_id: str
    text: str
    sensitive: bool


@dataclass
class AcceptedQuizQuestion:
    article_id: str
    prompt: str
    options: list[str]
    correct_index: int
    explanation: str


def _too_casual(text: str, sensitive: bool) -> bool:
    if not sensitive:
        return False
    lowered = text.lower()
    return bool(_EMOJI.search(text)) or any(word in lowered.split() for word in SLANG)


def validate_quiz_rag(data: dict[str, Any], corpora: dict[str, StoredCorpus]) -> list[AcceptedQuizQuestion]:
    try:
        batch = RagQuizBatchOut.model_validate(data)
    except ValidationError as exc:
        raise OutputRejected(f"Schema validation failed: {exc.error_count()} errors") from exc
    accepted: list[AcceptedQuizQuestion] = []
    for item in batch.questions:
        corpus = corpora.get(item.article_id)
        if corpus is None:
            continue
        answer = item.options[item.correct_index]
        grounded = " ".join([item.prompt, answer, item.explanation])
        if unsupported_numbers(grounded, corpus.text):
            continue
        if _too_casual(item.prompt, corpus.sensitive) or _too_casual(item.explanation, corpus.sensitive):
            continue
        if (
            overlap_ratio(item.explanation, corpus.text) < 0.3
            and overlap_ratio(item.prompt, corpus.text) < 0.3
        ):
            continue
        accepted.append(
            AcceptedQuizQuestion(
                article_id=item.article_id,
                prompt=item.prompt.strip(),
                options=item.options,
                correct_index=item.correct_index,
                explanation=item.explanation.strip(),
            )
        )
    if not accepted:
        raise OutputRejected("No quiz question was supported by the saved stories")
    return accepted


_URL = re.compile(r"https?://[^\s)>\"]+")


def validate_chat_answer(data: dict[str, Any], corpus: str, *, sensitive: bool) -> str:
    try:
        out = ChatAnswerOut.model_validate(data)
    except ValidationError as exc:
        raise OutputRejected(f"Schema validation failed: {exc.error_count()} errors") from exc
    answer = out.answer.strip()
    if unsupported_numbers(answer, corpus):
        raise OutputRejected("Answer cites numbers that are not in the saved stories")
    if _too_casual(answer, sensitive):
        raise OutputRejected("Sensitive story reply used a casual tone")
    allowed = {u.rstrip(".,)") for u in _URL.findall(corpus)}
    extra = {u.rstrip(".,)") for u in _URL.findall(answer)} - allowed
    if extra:
        raise OutputRejected("Answer cited a link that is not in the saved stories")
    return answer
