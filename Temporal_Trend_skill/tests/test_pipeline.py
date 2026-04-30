import json
from pathlib import Path

from skill_c_trends.pipeline import analyze_trends


def test_analyze_trends_outputs_lifecycle_enriched_network_and_artifacts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "trend_analysis.json"
    markdown = tmp_path / "trend_report.md"
    enriched = tmp_path / "network_with_trends.json"
    artifacts = tmp_path / "artifacts"

    result = analyze_trends(
        current_path=root / "examples" / "current_network.json",
        history_paths=[root / "examples" / "history_day1.json", root / "examples" / "history_day2.json"],
        papers_path=root / "examples" / "papers.json",
        output_path=output,
        markdown_path=markdown,
        enriched_network_path=enriched,
        artifacts_dir=artifacts,
    )

    assert output.exists()
    assert markdown.exists()
    assert enriched.exists()
    assert result["lifecycle_summary"]
    assert any(row["lifecycle_event"] in {"birth", "growth", "merge", "stable"} for row in result["community_trends"])
    assert result["artifacts"]["community_emergence_scores_png"]
    assert Path(result["artifacts"]["community_emergence_scores_png"]).exists()

    enriched_payload = json.loads(enriched.read_text(encoding="utf-8"))
    assert "temporal_trends" in enriched_payload
    assert "emergence_score" in enriched_payload["emerging_communities"][0]


def test_analyze_without_history_warns_and_marks_birth(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = analyze_trends(
        current_path=root / "examples" / "current_network.json",
        output_path=tmp_path / "trend_analysis.json",
    )

    assert result["metrics"]["history_snapshot_count"] == 0
    assert result["warnings"]
    assert all(row["lifecycle_event"] == "birth" for row in result["community_trends"])
