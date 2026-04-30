from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_visualizations(result: dict[str, Any], artifacts_dir: str | Path) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    if result.get("community_trends"):
        path = out_dir / "community_emergence_scores.png"
        _plot_emergence_scores(result["community_trends"], path, plt)
        artifacts["community_emergence_scores_png"] = str(path)

    rising_categories = [row for row in result.get("category_trends", []) if row.get("delta", 0) > 0]
    if rising_categories:
        path = out_dir / "category_growth.png"
        _plot_category_growth(rising_categories, path, plt)
        artifacts["category_growth_png"] = str(path)

    bridge_rows = result.get("bridge_author_trends", [])
    if bridge_rows:
        path = out_dir / "bridge_author_delta.png"
        _plot_bridge_author_delta(bridge_rows, path, plt)
        artifacts["bridge_author_delta_png"] = str(path)

    return artifacts


def _plot_emergence_scores(rows: list[dict[str, Any]], path: Path, plt: Any) -> None:
    top = rows[:10]
    labels = [str(row["community_id"]) for row in top]
    scores = [float(row["emergence_score"]) for row in top]
    colors = ["#d95f02" if row.get("lifecycle_event") in {"birth", "merge", "growth"} else "#1b9e77" for row in top]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(labels[::-1], scores[::-1], color=colors[::-1])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Emergence score")
    ax.set_title("Community emergence ranking")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_category_growth(rows: list[dict[str, Any]], path: Path, plt: Any) -> None:
    top = rows[:10]
    labels = [str(row["category"]) for row in top]
    deltas = [float(row["delta"]) for row in top]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(labels[::-1], deltas[::-1], color="#7570b3")
    ax.set_xlabel("Current count minus historical average")
    ax.set_title("Rising arXiv categories")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_bridge_author_delta(rows: list[dict[str, Any]], path: Path, plt: Any) -> None:
    top = rows[:10]
    labels = [str(row["author"]) for row in top]
    deltas = [float(row["delta"]) for row in top]
    colors = ["#e7298a" if delta >= 0 else "#66a61e" for delta in deltas]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(labels[::-1], deltas[::-1], color=colors[::-1])
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("Bridge score delta")
    ax.set_title("Bridge-author trend")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
