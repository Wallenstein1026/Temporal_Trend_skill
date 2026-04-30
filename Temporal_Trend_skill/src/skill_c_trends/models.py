from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PaperInfo:
    paper_id: str
    arxiv_id: str
    title: str
    categories: tuple[str, ...] = ()
    published_at: str = ""


@dataclass
class CommunitySnapshot:
    run_id: str
    community_id: str
    size: int
    categories: dict[str, int] = field(default_factory=dict)
    representative_papers: set[str] = field(default_factory=set)
    avg_published_at: str = ""

    @property
    def total_category_count(self) -> int:
        return sum(self.categories.values())


@dataclass(frozen=True)
class MatchResult:
    run_id: str | None
    community_id: str | None
    similarity: float
    size: int | None
