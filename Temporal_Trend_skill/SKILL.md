---
name: temporal-trend-detection
description: "Detects temporal trends and emerging research communities by comparing current Skill B arXiv network-analysis output against historical network snapshots; computes growth, novelty, bridge pressure, emergence scores, lifecycle events, category trends, bridge-author changes, enriched network JSON, PNG visualizations, and markdown summaries for StudyClawHub agents."
author: GreeWang
version: 1.0.0
tags:
  - temporal-analysis
  - emerging-communities
  - trend-detection
  - arxiv
  - network-analysis
---

# Temporal Trend Detection Skill

Use this Skill when an agent has current and historical Skill B `network_analysis.json` files and needs to identify which research communities are emerging, growing, or becoming more interdisciplinary.

## Inputs

Required:

- `--current`: current Skill B `network_analysis.json`.

Optional:

- `--history`: one or more previous Skill B `network_analysis.json` files.
- `--history-dir`: directory containing previous `.json` network snapshots.
- `--papers`: current Skill A or Skill B paper metadata JSON for paper-title explanations.
- `--enriched-network-output`: optional copy of the current Skill B JSON with trend fields injected into `emerging_communities[]`.
- `--artifacts-dir`: optional directory for PNG trend visualizations.
- `--window-days`: temporal window used in labels and metrics, default `7`.

The current and historical network files should contain Skill B-style fields:

- `run_id`
- `network_stats` or `graphs`
- `communities`
- `paper_sim_edges`
- `top_bridges`
- `emerging_communities`
- `warnings`

## Outputs

The Skill writes:

- `trend_analysis.json`: structured temporal metrics.
- optional `trend_report.md`: human-readable trend summary.
- optional enriched Skill B network JSON.
- optional trend PNG artifacts.

Main output fields:

- `community_trends[]`: matched current communities with lifecycle event, growth, novelty, bridge pressure, recency, emergence score, and explanation.
- `lifecycle_summary`: counts of `birth`, `growth`, `merge`, `split`, `decline`, `topic_shift`, and `stable`.
- `category_trends[]`: category counts and change against history.
- `bridge_author_trends[]`: bridge-author score changes.
- `alerts[]`: high-priority emerging-community or bridge-pressure alerts.
- `artifacts`: generated PNG paths when visualization is enabled.
- `metrics`: run-level evaluation and coverage metrics.
- `warnings`: recoverable input-quality notes.

## CLI

```bash
skill-c-trends analyze \
  --current outputs/network_analysis.json \
  --history history/day1.json history/day2.json \
  --papers skill_a_output.json \
  --output outputs/trend_analysis.json \
  --markdown outputs/trend_report.md \
  --enriched-network-output outputs/network_analysis_with_trends.json \
  --artifacts-dir outputs/artifacts
```

For local source checkout:

```bash
python -m skill_c_trends.cli analyze \
  --current examples/current_network.json \
  --history examples/history_day1.json examples/history_day2.json \
  --output outputs/trend_analysis.json
```

## Method

1. Extract current communities from Skill B `emerging_communities[]`; fall back to paper-community assignments if needed.
2. Extract historical community snapshots from previous Skill B outputs.
3. Match each current community to the most similar historical community using paper overlap and category-distribution cosine similarity.
4. Compute:
   - `growth_{window_days}d`: relative size change against the matched historical baseline.
   - `novelty_score`: one minus the strongest historical similarity.
   - `bridge_pressure`: current cross-community edge exposure from paper-similarity edges, with bridge-author evidence as fallback.
   - `recency_score`: higher when representative papers are recent inside the current snapshot.
   - `emergence_score`: weighted combination of growth, novelty, bridge pressure, and recency.
5. Classify lifecycle events:
   - `birth`: no sufficiently similar historical match.
   - `growth`: matched community grew by at least 25%.
   - `merge`: current community resembles multiple historical communities.
   - `split`: multiple current communities map to the same historical community.
   - `decline`: matched community shrank by at least 25%.
   - `topic_shift`: weak match with high novelty.
   - `stable`: no strong temporal change.
6. Emit explanations that cite observable metrics rather than unsupported claims.
7. If requested, write an enriched network JSON and PNG visualizations.

## References

- Community evolution analysis for dynamic networks.
- Jaccard similarity for set overlap.
- Cosine similarity for category-distribution comparison.
- Betweenness centrality and bridge pressure as signals of cross-community brokerage.

## Limitations

- Community matching is approximate because community IDs are not stable across runs.
- Strong temporal conclusions need multiple historical snapshots.
- If history is absent, growth is `null`; novelty is treated as high but marked with a warning.
