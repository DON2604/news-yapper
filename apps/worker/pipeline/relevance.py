"""Deterministic relevance scoring. The score is a labelled HEURISTIC (0-100) for ranking,
never an exam-probability claim."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "polity": (
        "bill", "act", "parliament", "lok sabha", "rajya sabha", "supreme court", "high court", "judgment",
        "verdict", "constitution", "article", "election commission", "ordinance", "governor", "cabinet",
        "ministry", "minister", "appointed", "sworn in", "scheme", "yojana", "policy", "amendment", "president",
    ),
    "economy": (
        "rbi", "reserve bank", "repo", "inflation", "gdp", "fiscal", "budget", "gst", "sebi", "bank", "rupee",
        "monetary", "tax", "export", "import", "msme", "fdi", "npci", "upi", "growth", "credit", "deficit",
        "trade", "economy", "economic", "financial", "nbfc", "co-operative bank", "cooperative bank",
        "bond", "treasury", "t-bill", "auction", "yield", "money market", "liquidity", "forex", "gold",
        "redemption", "securities", "banking regulation", "deposit", "lending", "monetary penalty",
    ),
    "science": (
        "isro", "launch", "satellite", "mission", "drdo", "missile", "space", "research", "vaccine", "quantum",
        "scientist", "rocket", "telescope", "technology", "artificial intelligence", "semiconductor",
    ),
    "international": (
        "united nations", "un ", "summit", "g20", "brics", "sco", "bilateral", "treaty", "visit", "mou",
        "foreign minister", "embassy", "unesco", "who", "imf", "world bank", "nato", "sanctions", "ceasefire",
    ),
    "environment": (
        "climate", "emission", "forest", "wildlife", "tiger", "biodiversity", "pollution", "monsoon", "cop",
        "renewable", "solar", "heatwave", "wetland", "ramsar", "species", "conservation", "carbon",
    ),
    "awards": ("award", "prize", "nobel", "padma", "bharat ratna", "honour", "honor", "conferred", "laureate"),
    "sports": (
        "cup", "olympic", "championship", "medal", "tournament", "league", "grand slam", "chess", "cricket",
        "football", "hockey", "athlete", "badminton", "wrestling", "javelin",
    ),
}  # fmt: skip

EXAM_SIGNALS: dict[str, int] = {
    "scheme": 8, "yojana": 8, "appointed": 8, "bill": 7, "act": 4, "judgment": 7, "verdict": 6, "index": 6,
    "report": 5, "ranking": 6, "summit": 6, "launched": 6, "inaugurated": 5, "first": 5, "largest": 4,
    "record": 4, "mou": 6, "agreement": 5, "award": 6, "mission": 5, "policy": 5, "theme": 6,
    "international day": 7, "national day": 6, "repo": 7, "monetary policy": 7, "amendment": 6,
}  # fmt: skip

GOSSIP = (
    "bollywood", "actor", "actress", "celebrity", "viral", "dating", "gossip", "box office", "trolled",
    "reality show", "wardrobe", "breakup", "influencer",
)  # fmt: skip

SENSITIVE = (
    "killed", "killing", "dead", "death", "deaths", "death toll", "died", "dies", "fatal", "fatalities",
    "victims", "injured", "murder", "rape", "suicide", "terror", "blast", "bomb",
    "earthquake", "flood", "cyclone", "stampede", "crash", "riot", "lynching", "massacre", "casualties",
    "landslide", "shooting", "assault", "genocide", "war",
)  # fmt: skip

INDIA_HINTS = (
    "india",
    "indian",
    "delhi",
    "mumbai",
    "kolkata",
    "bengal",
    "centre",
    "union government",
    "rbi",
    "isro",
)


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(phrase.strip())}(?![a-z])", text) is not None


def categorize(text: str, default: str | None = None) -> tuple[str, list[str]]:
    lowered = f" {text.lower()} "
    best, hits = (default or "other"), []
    best_count = 0
    for category, words in CATEGORY_KEYWORDS.items():
        found = [w.strip() for w in words if _contains(lowered, w)]
        if len(found) > best_count:
            best, best_count, hits = category, len(found), found
    return best, hits


def is_sensitive(text: str) -> bool:
    lowered = text.lower()
    return any(_contains(lowered, w) for w in SENSITIVE)


@dataclass
class RelevanceResult:
    category: str
    score: float
    sensitive: bool
    region: str
    reasons: list[str] = field(default_factory=list)


def score(
    *,
    titles: list[str],
    excerpts: list[str],
    tiers: list[str],
    authority: list[float],
    publishers: set[str],
    latest: datetime | None,
    now: datetime,
    default_topic: str | None = None,
    source_country: str | None = None,
) -> RelevanceResult:
    text = " ".join(titles + excerpts)
    lowered = text.lower()
    category, hits = categorize(text, default_topic)
    reasons: list[str] = []
    value = 10.0
    if hits:
        value += min(20, 5 * len(hits))
        reasons.append(f"{category} keywords: {', '.join(hits[:4])}")
    exam = [(k, w) for k, w in EXAM_SIGNALS.items() if _contains(lowered, k)]
    if exam:
        value += min(25, sum(w for _, w in exam))
        reasons.append(f"exam signals: {', '.join(k for k, _ in exam[:4])}")
    if "A" in tiers:
        value += 25 * max(authority or [1.0])
        reasons.append("Tier A official source")
    else:
        value += 10 * max(authority or [0.4])
        reasons.append("Tier B discovery source")
    if len(publishers) > 1:
        bonus = min(15, 5 * (len(publishers) - 1))
        value += bonus
        reasons.append(f"corroborated by {len(publishers)} publishers")
    gossip = [g for g in GOSSIP if _contains(lowered, g)]
    if gossip:
        value -= 30
        reasons.append(f"gossip penalty: {', '.join(gossip[:3])}")
    if latest is not None:
        age_hours = max(0.0, (now - latest).total_seconds() / 3600)
        decay = math.exp(-age_hours / 72)
        value *= 0.5 + 0.5 * decay
        if age_hours > 24:
            reasons.append(f"time decay ({int(age_hours)}h old)")
    sensitive = is_sensitive(text)
    if sensitive:
        reasons.append("sensitive story: serious tone + editorial review")
    region = (
        "india" if (source_country == "IN" or any(_contains(lowered, h) for h in INDIA_HINTS)) else "world"
    )
    reasons.append("heuristic relevance score - not an exam probability")
    return RelevanceResult(
        category=category,
        score=round(max(0.0, min(100.0, value)), 1),
        sensitive=sensitive,
        region=region,
        reasons=reasons,
    )
