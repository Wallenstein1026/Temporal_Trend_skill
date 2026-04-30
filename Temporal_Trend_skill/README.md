# Skill C: Temporal Trend / Emerging Community Detection

Skill C detects **emerging research communities** by comparing today's Skill B network-analysis output with historical network snapshots. It turns static graph analysis into temporal social-network analysis: which communities are growing, which topics are newly appearing, and which communities are under cross-community bridge pressure.

This repo is designed to be uploaded directly to GitHub and registered as a StudyClawHub Skill.

## What It Does

- Matches current research communities to historical communities.
- Computes temporal metrics:
  - `growth_7d`
  - `novelty_score`
  - `bridge_pressure`
  - `recency_score`
  - `emergence_score`
- Classifies community lifecycle events:
  - `birth`
  - `growth`
  - `merge`
  - `split`
  - `decline`
  - `topic_shift`
  - `stable`
- Detects rising arXiv categories and bridge-author changes.
- Emits machine-readable `trend_analysis.json`.
- Optionally writes an enriched Skill B network JSON with trend fields injected into `emerging_communities[]`.
- Optionally exports PNG visualizations for emergence scores, category growth, and bridge-author deltas.
- Optionally emits a compact Markdown trend report.
- Works with Skill B output and optionally uses Skill A paper metadata for better explanations.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Quickstart

```bash
skill-c-trends analyze \
  --current examples/current_network.json \
  --history examples/history_day1.json examples/history_day2.json \
  --papers examples/papers.json \
  --output outputs/trend_analysis.json \
  --markdown outputs/trend_report.md \
  --enriched-network-output outputs/network_analysis_with_trends.json \
  --artifacts-dir outputs/artifacts
```

Local module form:

```bash
python -m skill_c_trends.cli analyze \
  --current examples/current_network.json \
  --history examples/history_day1.json examples/history_day2.json \
  --output outputs/trend_analysis.json
```

You can also load a whole directory of prior snapshots:

```bash
skill-c-trends analyze \
  --current outputs/today/network_analysis.json \
  --history-dir outputs/history \
  --output outputs/today/trend_analysis.json \
  --artifacts-dir outputs/today/artifacts
```

## Input Schema

Required current input: Skill B `network_analysis.json`.

Important fields:

- `run_id`
- `emerging_communities[]`
- `paper_sim_edges[]`
- `communities.paper_similarity.<method>.assignments`
- `top_bridges[]`
- `network_stats` or `graphs`
- `warnings`

Example:

```json
{
  "run_id": "2026-04-18_slam",
  "emerging_communities": [
    {
      "community_id": "C2",
      "size": 8,
      "top_categories": [
        {"category": "cs.RO", "count": 5},
        {"category": "cs.CV", "count": 3}
      ],
      "representative_papers": ["2604.12942", "2604.14795"],
      "avg_published_at": "2026-04-16"
    }
  ],
  "paper_sim_edges": [],
  "top_bridges": []
}
```

Historical inputs use the same schema.

Optional `--papers` accepts Skill A or Skill B paper metadata:

- `papers_metadata[]`
- `papers_ranked[]`
- `papers[]` where each item may contain a nested `paper` object

## Output Schema

`trend_analysis.json` contains:

```json
{
  "run_id": "2026-04-18_slam",
  "window_days": 7,
  "community_trends": [
    {
      "community_id": "C2",
      "size": 8,
      "lifecycle_event": "growth",
      "lifecycle_evidence": "C2 grew by 60.0% against its matched historical community.",
      "matched_history": {
        "run_id": "2026-04-17_slam",
        "community_id": "C1",
        "similarity": 0.61
      },
      "growth_7d": 0.6,
      "novelty_score": 0.39,
      "bridge_pressure": 0.42,
      "recency_score": 0.9,
      "emergence_score": 0.58,
      "label": "emerging",
      "explanation": "Community C2 grew by 60.0% versus its closest historical match and has bridge pressure 0.42."
    }
  ],
  "lifecycle_summary": {
    "growth": 1
  },
  "category_trends": [],
  "bridge_author_trends": [],
  "alerts": [],
  "artifacts": {
    "community_emergence_scores_png": "outputs/artifacts/community_emergence_scores.png",
    "category_growth_png": "outputs/artifacts/category_growth.png",
    "bridge_author_delta_png": "outputs/artifacts/bridge_author_delta.png"
  },
  "metrics": {},
  "warnings": []
}
```

When `--enriched-network-output` is provided, the Skill copies the current Skill B JSON and enriches each matching `emerging_communities[]` record:

```json
{
  "community_id": "C2",
  "growth_7d": 0.6,
  "novelty_score": 0.39,
  "bridge_pressure": 0.42,
  "emergence_score": 0.58,
  "lifecycle_event": "growth",
  "trend_label": "emerging"
}
```

This file is convenient for Skill E because it can read one enhanced network-analysis file instead of joining Skill B and Skill C outputs.

## Lifecycle Events

- `birth`: no sufficiently similar historical community exists.
- `growth`: the matched community grew by at least 25%.
- `merge`: the current community resembles multiple historical communities.
- `split`: multiple current communities map back to the same historical community.
- `decline`: the matched community shrank by at least 25%.
- `topic_shift`: the match exists but novelty remains high.
- `stable`: no strong structural change is detected.

## Visualizations

When `--artifacts-dir` is provided, the Skill writes up to three PNG files:

- `community_emergence_scores.png`
- `category_growth.png`
- `bridge_author_delta.png`

## How It Fits the 5-Skill Workflow

Recommended workflow:

```text
Skill A: arXiv retrieval + paper metadata / summaries
  -> Skill D: ranking and diversification, if not already inside A
  -> Skill B: network construction, community detection, centrality, bridges
  -> Skill C: temporal trend and emerging-community detection
  -> Skill E: final briefing composition and visualization
```

Skill B answers: **what does today's research network look like?**  
Skill C answers: **what changed compared with previous snapshots?**

## Evaluation

Run tests:

```bash
python -m pytest
```

Suggested report metrics:

- `history_snapshot_count`: how much temporal evidence was available.
- `matched_community_count`: how many current communities could be matched to history.
- `mean_emergence_score`: average strength of emerging-community signals.
- `alert_count`: number of high-priority trend alerts.
- `lifecycle_summary`: counts of birth, growth, merge, split, decline, topic shift, and stable communities.
- Qualitative examples: top 2-3 communities with explanations and representative papers.

## References

- Palla et al. Uncovering the overlapping community structure of complex networks in nature and society. 2005.
- Greene et al. Tracking the evolution of communities in dynamic social networks. 2010.
- Brandes. A faster algorithm for betweenness centrality. 2001.
- Blondel et al. Fast unfolding of communities in large networks. 2008.

## Known Limits

- Community IDs are not stable across runs, so matching is approximate.
- With no historical snapshots, the Skill can rank novelty but cannot compute true growth.
- This Skill does not fetch papers and does not construct graphs; those are owned by Skills A and B.
