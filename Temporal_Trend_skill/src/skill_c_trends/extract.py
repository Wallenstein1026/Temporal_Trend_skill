from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import CommunitySnapshot, PaperInfo


def load_paper_lookup(payload: dict[str, Any] | None) -> dict[str, PaperInfo]:
    if not payload:
        return {}
    raw = payload.get("papers_metadata")
    if raw is None:
        raw = payload.get("papers_ranked")
    if raw is None:
        raw = payload.get("papers")
    if not isinstance(raw, list):
        return {}

    lookup: dict[str, PaperInfo] = {}
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        source = item.get("paper") if isinstance(item.get("paper"), dict) else item
        arxiv_id = str(source.get("arxiv_id") or source.get("id") or source.get("paper_id") or "").strip()
        paper_id = str(source.get("paper_id") or arxiv_id or f"paper_{idx}").strip()
        if not paper_id and not arxiv_id:
            continue
        title = str(source.get("title") or "").strip()
        categories = tuple(str(cat).strip() for cat in source.get("categories", []) if str(cat).strip())
        published_at = str(source.get("published_at") or source.get("published") or "").strip()
        info = PaperInfo(paper_id=paper_id or arxiv_id, arxiv_id=arxiv_id or paper_id, title=title, categories=categories, published_at=published_at)
        lookup[info.paper_id] = info
        lookup[info.arxiv_id] = info
    return lookup


def extract_communities(payload: dict[str, Any]) -> list[CommunitySnapshot]:
    run_id = str(payload.get("run_id") or "unknown_run")
    records = payload.get("emerging_communities")
    communities: list[CommunitySnapshot] = []
    if isinstance(records, list) and records:
        for idx, item in enumerate(records):
            if not isinstance(item, dict):
                continue
            communities.append(
                CommunitySnapshot(
                    run_id=run_id,
                    community_id=str(item.get("community_id") or f"C{idx}"),
                    size=max(0, int(item.get("size") or 0)),
                    categories=_category_counter(item.get("top_categories")),
                    representative_papers={str(p) for p in item.get("representative_papers", []) if str(p).strip()},
                    avg_published_at=str(item.get("avg_published_at") or ""),
                )
            )
    if communities:
        return communities
    return _extract_from_assignments(payload, run_id)


def extract_category_totals(communities: list[CommunitySnapshot]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for community in communities:
        totals.update(community.categories)
    return dict(totals)


def extract_bridge_authors(payload: dict[str, Any]) -> dict[str, dict[str, float]]:
    bridges = payload.get("top_bridges") or []
    result: dict[str, dict[str, float]] = {}
    if not isinstance(bridges, list):
        return result
    for item in bridges:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name_norm") or item.get("node_id") or "").strip().lower()
        if not name:
            continue
        result[name] = {
            "bridging_score": _float(item.get("bridging_score")),
            "betweenness": _float(item.get("betweenness")),
            "cross_community_edge_ratio": _float(item.get("cross_community_edge_ratio")),
        }
    return result


def paper_assignments(payload: dict[str, Any]) -> dict[str, str]:
    communities = payload.get("communities") or {}
    paper_methods = communities.get("paper_similarity") if isinstance(communities, dict) else None
    if not isinstance(paper_methods, dict):
        return {}
    preferred = None
    for method in ("louvain", "label_propagation"):
        candidate = paper_methods.get(method)
        if isinstance(candidate, dict) and isinstance(candidate.get("assignments"), dict):
            preferred = candidate.get("assignments")
            break
    if preferred is None:
        for candidate in paper_methods.values():
            if isinstance(candidate, dict) and isinstance(candidate.get("assignments"), dict):
                preferred = candidate.get("assignments")
                break
    if not isinstance(preferred, dict):
        return {}
    return {str(paper): str(comm) for paper, comm in preferred.items()}


def bridge_pressure_by_community(payload: dict[str, Any], communities: list[CommunitySnapshot]) -> dict[str, float]:
    assignments = paper_assignments(payload)
    edge_pressure = _edge_bridge_pressure(payload, assignments)
    if edge_pressure:
        return _map_assignment_pressure_to_community_ids(edge_pressure, assignments, communities)
    return _bridge_author_pressure(payload, communities)


def _category_counter(raw: Any) -> dict[str, int]:
    counter: Counter[str] = Counter()
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                category = str(entry.get("category") or "").strip()
                if category:
                    counter[category] += int(entry.get("count") or 1)
            elif entry:
                counter[str(entry)] += 1
    elif isinstance(raw, dict):
        for category, count in raw.items():
            counter[str(category)] += int(count or 0)
    return dict(counter)


def _extract_from_assignments(payload: dict[str, Any], run_id: str) -> list[CommunitySnapshot]:
    assignments = paper_assignments(payload)
    if not assignments:
        return []
    grouped: dict[str, set[str]] = defaultdict(set)
    for paper_id, community_id in assignments.items():
        grouped[community_id].add(paper_id)
    return [
        CommunitySnapshot(run_id=run_id, community_id=f"C{community_id}", size=len(papers), representative_papers=papers)
        for community_id, papers in sorted(grouped.items(), key=lambda kv: kv[0])
    ]


def _edge_bridge_pressure(payload: dict[str, Any], assignments: dict[str, str]) -> dict[str, float]:
    if not assignments:
        return {}
    incident: Counter[str] = Counter()
    external: Counter[str] = Counter()
    for edge in payload.get("paper_sim_edges") or []:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("source") or "")
        dst = str(edge.get("target") or "")
        c_src = assignments.get(src)
        c_dst = assignments.get(dst)
        if c_src is None or c_dst is None:
            continue
        weight = _float(edge.get("weight") or edge.get("similarity") or 1.0)
        incident[c_src] += weight
        incident[c_dst] += weight
        if c_src != c_dst:
            external[c_src] += weight
            external[c_dst] += weight
    return {community_id: round(external[community_id] / incident[community_id], 6) for community_id in incident if incident[community_id] > 0}


def _map_assignment_pressure_to_community_ids(
    pressure: dict[str, float],
    assignments: dict[str, str],
    communities: list[CommunitySnapshot],
) -> dict[str, float]:
    mapped: dict[str, float] = {}
    for community in communities:
        assignment_ids = Counter(assignments.get(paper) for paper in community.representative_papers if assignments.get(paper))
        if not assignment_ids:
            mapped[community.community_id] = 0.0
            continue
        best_assignment, _ = assignment_ids.most_common(1)[0]
        mapped[community.community_id] = pressure.get(str(best_assignment), 0.0)
    return mapped


def _bridge_author_pressure(payload: dict[str, Any], communities: list[CommunitySnapshot]) -> dict[str, float]:
    pressure = {community.community_id: 0.0 for community in communities}
    bridges = payload.get("top_bridges") or []
    if not isinstance(bridges, list):
        return pressure
    for community in communities:
        papers = community.representative_papers
        scores: list[float] = []
        for bridge in bridges:
            if not isinstance(bridge, dict):
                continue
            bridge_papers = {str(p) for p in bridge.get("representative_papers", [])}
            if papers & bridge_papers:
                scores.append(_float(bridge.get("cross_community_edge_ratio") or bridge.get("bridging_score")))
        if scores:
            pressure[community.community_id] = round(sum(scores) / len(scores), 6)
    return pressure


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
