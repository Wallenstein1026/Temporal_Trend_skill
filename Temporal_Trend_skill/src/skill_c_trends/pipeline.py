from __future__ import annotations

from copy import deepcopy
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from .extract import (
    bridge_pressure_by_community,
    extract_bridge_authors,
    extract_category_totals,
    extract_communities,
    load_paper_lookup,
)
from .io import read_json, write_json, write_text
from .metrics import (
    category_changes,
    community_similarity,
    emergence_score,
    growth_score,
    label_for,
    lifecycle_event,
    match_to_history,
    novelty_score,
    recency_score,
)
from .models import CommunitySnapshot
from .viz import generate_visualizations


def analyze_trends(
    current_path: str | Path,
    output_path: str | Path,
    history_paths: list[str | Path] | None = None,
    history_dir: str | Path | None = None,
    papers_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    enriched_network_path: str | Path | None = None,
    artifacts_dir: str | Path | None = None,
    window_days: int = 7,
) -> dict[str, Any]:
    current_payload = read_json(current_path)
    paper_payload = read_json(papers_path) if papers_path else None
    papers = load_paper_lookup(paper_payload)
    histories, history_warnings = _load_history(history_paths or [], history_dir, current_path)

    current_communities = extract_communities(current_payload)
    history_communities = [community for payload in histories for community in extract_communities(payload)]
    warnings = list(history_warnings)
    warnings.extend(str(warning) for warning in current_payload.get("warnings") or [])
    if not current_communities:
        warnings.append("No current communities found; output trend lists are empty.")
    if not histories:
        warnings.append("No historical snapshots provided; growth metrics are null and novelty is treated as high.")

    bridge_pressure = bridge_pressure_by_community(current_payload, current_communities)
    split_counts: Counter[tuple[str | None, str | None]] = Counter()
    preliminary_matches = {community.community_id: match_to_history(community, history_communities) for community in current_communities}
    for match in preliminary_matches.values():
        if match.community_id is not None:
            split_counts[(match.run_id, match.community_id)] += 1

    community_trends = []
    has_history = bool(history_communities)
    for community in current_communities:
        match = preliminary_matches[community.community_id]
        growth, growth_norm = growth_score(community.size, match.size)
        novelty = novelty_score(match, has_history)
        pressure = round(bridge_pressure.get(community.community_id, 0.0), 6)
        recency = recency_score(community, papers)
        score = emergence_score(growth_norm, novelty, pressure, recency)
        label = label_for(score, growth, novelty, pressure)
        multi_match_count = _significant_history_match_count(community, history_communities, match.similarity)
        split_count = split_counts[(match.run_id, match.community_id)] if match.community_id is not None else 0
        lifecycle, lifecycle_evidence = lifecycle_event(
            community.community_id,
            match,
            growth,
            novelty,
            multi_match_count,
            split_count,
        )
        community_trends.append(
            {
                "community_id": community.community_id,
                "size": community.size,
                "lifecycle_event": lifecycle,
                "lifecycle_evidence": lifecycle_evidence,
                "top_categories": _top_categories(community),
                "representative_papers": _paper_labels(community, papers),
                "matched_history": {
                    "run_id": match.run_id,
                    "community_id": match.community_id,
                    "similarity": match.similarity,
                    "size": match.size,
                },
                f"growth_{window_days}d": growth,
                "novelty_score": novelty,
                "bridge_pressure": pressure,
                "recency_score": recency,
                "emergence_score": score,
                "label": label,
                "explanation": _explain(community.community_id, growth, novelty, pressure, score, match),
            }
        )
    community_trends.sort(key=lambda row: row["emergence_score"], reverse=True)

    current_category_totals = extract_category_totals(current_communities)
    history_category_totals = [extract_category_totals(extract_communities(payload)) for payload in histories]
    category_trends = category_changes(current_category_totals, history_category_totals)
    bridge_author_trends = _bridge_author_trends(current_payload, histories)
    alerts = _alerts(community_trends, category_trends, bridge_author_trends)
    lifecycle_summary = dict(Counter(str(row["lifecycle_event"]) for row in community_trends))

    result = {
        "run_id": str(current_payload.get("run_id") or "unknown_run"),
        "window_days": max(1, int(window_days)),
        "community_trends": community_trends,
        "lifecycle_summary": lifecycle_summary,
        "category_trends": category_trends,
        "bridge_author_trends": bridge_author_trends,
        "alerts": alerts,
        "metrics": {
            "current_community_count": len(current_communities),
            "history_snapshot_count": len(histories),
            "history_community_count": len(history_communities),
            "matched_community_count": sum(1 for row in community_trends if row["matched_history"]["community_id"] is not None),
            "mean_emergence_score": round(mean([row["emergence_score"] for row in community_trends]), 6) if community_trends else 0.0,
            "alert_count": len(alerts),
        },
        "warnings": sorted(set(warnings)),
    }
    if artifacts_dir:
        try:
            result["artifacts"] = generate_visualizations(result, artifacts_dir)
        except Exception as exc:  # pragma: no cover - defensive path for optional plotting backends
            result["artifacts"] = {}
            result["warnings"] = sorted(set(result["warnings"] + [f"Visualization generation failed: {exc}"]))

    write_json(output_path, result)
    if enriched_network_path:
        enriched = _enrich_network_payload(current_payload, result)
        write_json(enriched_network_path, enriched)
    if markdown_path:
        write_text(markdown_path, render_markdown(result))
    return result


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Temporal Trend Analysis",
        "",
        f"- Run ID: `{result['run_id']}`",
        f"- History snapshots: {result['metrics']['history_snapshot_count']}",
        f"- Current communities: {result['metrics']['current_community_count']}",
        f"- Alerts: {result['metrics']['alert_count']}",
        "",
        "## Lifecycle Summary",
        "",
    ]
    if result.get("lifecycle_summary"):
        for event, count in sorted(result["lifecycle_summary"].items()):
            lines.append(f"- {event}: {count}")
    else:
        lines.append("No lifecycle events detected.")
    lines.extend(
        [
            "",
            "## Top Emerging Communities",
            "",
            "| Rank | Community | Lifecycle | Label | Score | Growth | Novelty | Bridge pressure | Main categories |",
            "|---:|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    growth_key = f"growth_{result['window_days']}d"
    for idx, item in enumerate(result["community_trends"][:10], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    _md(str(item["community_id"])),
                    _md(str(item["lifecycle_event"])),
                    _md(str(item["label"])),
                    str(item["emergence_score"]),
                    str(item[growth_key]),
                    str(item["novelty_score"]),
                    str(item["bridge_pressure"]),
                    _md(", ".join(f"{cat['category']} ({cat['count']})" for cat in item["top_categories"][:3])),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Alerts", ""])
    if result["alerts"]:
        for alert in result["alerts"]:
            lines.append(f"- **{_md(alert['type'])}**: {_md(alert['message'])}")
    else:
        lines.append("No high-priority alerts.")
    if result.get("artifacts"):
        lines.extend(["", "## Visualizations", ""])
        for name, path in result["artifacts"].items():
            lines.append(f"- {_md(str(name).replace('_', ' '))}: `{_md(str(path))}`")
    lines.extend(["", "## Warnings", ""])
    if result["warnings"]:
        lines.extend(f"- {_md(str(warning))}" for warning in result["warnings"])
    else:
        lines.append("None.")
    return "\n".join(lines).rstrip() + "\n"


def _load_history(history_paths: list[str | Path], history_dir: str | Path | None, current_path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    paths = [Path(path) for path in history_paths]
    if history_dir:
        paths.extend(sorted(Path(history_dir).glob("*.json")))
    current_resolved = Path(current_path).resolve()
    unique_paths = []
    seen = set()
    for path in paths:
        resolved = path.resolve()
        if resolved == current_resolved or resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)
    payloads = []
    warnings = []
    for path in unique_paths:
        try:
            payloads.append(read_json(path))
        except (OSError, ValueError) as exc:
            warnings.append(f"Ignored history snapshot {path}: {exc}")
    return payloads, warnings


def _top_categories(community: CommunitySnapshot) -> list[dict[str, int | str]]:
    return [
        {"category": category, "count": count}
        for category, count in sorted(community.categories.items(), key=lambda kv: kv[1], reverse=True)
    ]


def _paper_labels(community: CommunitySnapshot, papers: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for paper_id in sorted(community.representative_papers):
        info = papers.get(paper_id)
        rows.append(
            {
                "paper_id": paper_id,
                "title": info.title if info else "",
                "arxiv_id": info.arxiv_id if info else paper_id,
            }
        )
    return rows


def _explain(community_id: str, growth: float | None, novelty: float, pressure: float, score: float, match: Any) -> str:
    growth_text = "has no historical size baseline" if growth is None else f"changed by {growth * 100:.1f}% versus its closest historical match"
    match_text = "no matched prior community" if match.community_id is None else f"matched {match.community_id} from {match.run_id} with similarity {match.similarity}"
    return (
        f"Community {community_id} {growth_text}; {match_text}. "
        f"Novelty={novelty:.2f}, bridge_pressure={pressure:.2f}, emergence_score={score:.2f}."
    )


def _bridge_author_trends(current_payload: dict[str, Any], histories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = extract_bridge_authors(current_payload)
    history_scores: dict[str, list[float]] = {}
    for payload in histories:
        for author, metrics in extract_bridge_authors(payload).items():
            history_scores.setdefault(author, []).append(metrics["bridging_score"])
    rows = []
    for author, metrics in current.items():
        baseline_scores = history_scores.get(author, [])
        baseline = mean(baseline_scores) if baseline_scores else 0.0
        delta = metrics["bridging_score"] - baseline
        rows.append(
            {
                "author": author,
                "current_bridging_score": round(metrics["bridging_score"], 6),
                "history_avg_bridging_score": round(baseline, 6),
                "delta": round(delta, 6),
                "betweenness": round(metrics["betweenness"], 6),
                "cross_community_edge_ratio": round(metrics["cross_community_edge_ratio"], 6),
            }
        )
    return sorted(rows, key=lambda row: row["delta"], reverse=True)


def _significant_history_match_count(
    community: CommunitySnapshot,
    history_communities: list[CommunitySnapshot],
    best_similarity: float,
) -> int:
    if not history_communities or best_similarity <= 0:
        return 0
    threshold = max(0.25, best_similarity * 0.55)
    return sum(1 for historical in history_communities if community_similarity(community, historical) >= threshold)


def _alerts(
    community_trends: list[dict[str, Any]],
    category_trends: list[dict[str, Any]],
    bridge_author_trends: list[dict[str, Any]],
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    for row in community_trends[:5]:
        if row["emergence_score"] >= 0.7:
            alerts.append(
                {
                    "type": "strong_emerging_community",
                    "community_id": str(row["community_id"]),
                    "message": f"Community {row['community_id']} has emergence score {row['emergence_score']}.",
                }
            )
        elif row["bridge_pressure"] >= 0.5 and row["novelty_score"] >= 0.5:
            alerts.append(
                {
                    "type": "cross_domain_pressure",
                    "community_id": str(row["community_id"]),
                    "message": f"Community {row['community_id']} combines high novelty with bridge pressure {row['bridge_pressure']}.",
                }
            )
    for row in category_trends[:3]:
        growth = row.get("growth")
        if growth is not None and growth >= 0.5 and row.get("current_count", 0) >= 2:
            alerts.append(
                {
                    "type": "rising_category",
                    "category": str(row["category"]),
                    "message": f"Category {row['category']} rose by {growth * 100:.1f}% versus history.",
                }
            )
    for row in bridge_author_trends[:3]:
        if row["delta"] > 0.05:
            alerts.append(
                {
                    "type": "rising_bridge_author",
                    "author": str(row["author"]),
                    "message": f"Bridge author {row['author']} increased bridging score by {row['delta']}.",
                }
            )
    return alerts


def _enrich_network_payload(current_payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(current_payload)
    growth_key = f"growth_{result['window_days']}d"
    trend_by_id = {str(row["community_id"]): row for row in result.get("community_trends", [])}
    for community in enriched.get("emerging_communities") or []:
        if not isinstance(community, dict):
            continue
        community_id = str(community.get("community_id") or "")
        trend = trend_by_id.get(community_id)
        if not trend:
            continue
        community["growth_7d" if result["window_days"] == 7 else growth_key] = trend[growth_key]
        community["novelty_score"] = trend["novelty_score"]
        community["bridge_pressure"] = trend["bridge_pressure"]
        community["recency_score"] = trend["recency_score"]
        community["emergence_score"] = trend["emergence_score"]
        community["lifecycle_event"] = trend["lifecycle_event"]
        community["lifecycle_evidence"] = trend["lifecycle_evidence"]
        community["trend_label"] = trend["label"]
    enriched["temporal_trends"] = {
        "run_id": result["run_id"],
        "window_days": result["window_days"],
        "lifecycle_summary": result.get("lifecycle_summary", {}),
        "alerts": result.get("alerts", []),
        "artifacts": result.get("artifacts", {}),
        "metrics": result.get("metrics", {}),
    }
    return enriched


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
