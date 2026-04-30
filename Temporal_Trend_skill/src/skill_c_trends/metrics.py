from __future__ import annotations

from collections import Counter
from datetime import date
from math import sqrt

from .models import CommunitySnapshot, MatchResult, PaperInfo


def match_to_history(current: CommunitySnapshot, history: list[CommunitySnapshot]) -> MatchResult:
    best = MatchResult(run_id=None, community_id=None, similarity=0.0, size=None)
    for candidate in history:
        similarity = community_similarity(current, candidate)
        if similarity > best.similarity:
            best = MatchResult(
                run_id=candidate.run_id,
                community_id=candidate.community_id,
                similarity=round(similarity, 6),
                size=candidate.size,
            )
    return best


def community_similarity(a: CommunitySnapshot, b: CommunitySnapshot) -> float:
    paper_sim = jaccard(a.representative_papers, b.representative_papers)
    category_sim = cosine_counter(a.categories, b.categories)
    return (0.65 * paper_sim) + (0.35 * category_sim)


def growth_score(current_size: int, matched_size: int | None) -> tuple[float | None, float]:
    if matched_size is None:
        return None, 0.5
    baseline = max(1, matched_size)
    growth = (current_size - baseline) / baseline
    normalized = max(0.0, min(1.0, (growth + 0.25) / 1.25))
    return round(growth, 6), round(normalized, 6)


def novelty_score(match: MatchResult, has_history: bool) -> float:
    if not has_history:
        return 1.0
    return round(max(0.0, min(1.0, 1.0 - match.similarity)), 6)


def recency_score(community: CommunitySnapshot, papers: dict[str, PaperInfo]) -> float:
    dates: list[date] = []
    for paper_id in community.representative_papers:
        info = papers.get(paper_id)
        raw_date = info.published_at if info else ""
        parsed = _parse_date(raw_date)
        if parsed:
            dates.append(parsed)
    if not dates:
        parsed_avg = _parse_date(community.avg_published_at)
        if parsed_avg:
            dates.append(parsed_avg)
    if not dates:
        return 0.5
    newest = max(dates)
    oldest = min(dates)
    if newest == oldest:
        return 0.85
    avg_offset = sum((newest - item).days for item in dates) / len(dates)
    return round(max(0.0, min(1.0, 1.0 - (avg_offset / 14.0))), 6)


def emergence_score(growth_norm: float, novelty: float, bridge_pressure: float, recency: float) -> float:
    score = (0.40 * growth_norm) + (0.30 * novelty) + (0.20 * max(0.0, min(1.0, bridge_pressure))) + (0.10 * recency)
    return round(score, 6)


def label_for(score: float, growth: float | None, novelty: float, bridge_pressure: float) -> str:
    if score >= 0.7:
        return "strongly_emerging"
    if score >= 0.5:
        return "emerging"
    if growth is not None and growth < -0.25:
        return "declining"
    if novelty >= 0.75 and bridge_pressure >= 0.25:
        return "new_cross_domain"
    return "stable"


def lifecycle_event(
    community_id: str,
    match: MatchResult,
    growth: float | None,
    novelty: float,
    multi_match_count: int,
    split_count: int,
) -> tuple[str, str]:
    if match.community_id is None or match.similarity < 0.2:
        return "birth", f"No sufficiently similar historical community was found for {community_id}."
    if multi_match_count >= 2:
        return "merge", f"{community_id} resembles {multi_match_count} historical communities, suggesting a merge."
    if split_count >= 2:
        return "split", f"{split_count} current communities map back to historical community {match.community_id}."
    if growth is not None and growth >= 0.25:
        return "growth", f"{community_id} grew by {growth * 100:.1f}% against its matched historical community."
    if growth is not None and growth <= -0.25:
        return "decline", f"{community_id} shrank by {abs(growth) * 100:.1f}% against its matched historical community."
    if novelty >= 0.65:
        return "topic_shift", f"{community_id} matched history weakly with novelty score {novelty:.2f}."
    return "stable", f"{community_id} remains close to historical community {match.community_id}."


def category_changes(current: dict[str, int], history_totals: list[dict[str, int]]) -> list[dict[str, float | int | str]]:
    baseline: Counter[str] = Counter()
    for item in history_totals:
        baseline.update(item)
    divisor = max(1, len(history_totals))
    all_categories = sorted(set(current) | set(baseline))
    rows = []
    for category in all_categories:
        current_count = int(current.get(category, 0))
        baseline_avg = baseline.get(category, 0) / divisor
        delta = current_count - baseline_avg
        growth = None if baseline_avg == 0 else delta / baseline_avg
        rows.append(
            {
                "category": category,
                "current_count": current_count,
                "history_avg_count": round(baseline_avg, 6),
                "delta": round(delta, 6),
                "growth": None if growth is None else round(growth, 6),
            }
        )
    return sorted(rows, key=lambda row: (row["delta"], row["current_count"]), reverse=True)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def cosine_counter(a: dict[str, int], b: dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a.get(key, 0) * b.get(key, 0) for key in keys)
    norm_a = sqrt(sum(value * value for value in a.values()))
    norm_b = sqrt(sum(value * value for value in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
