from pathlib import Path

from skill_c_trends.cli import main


def test_cli_analyze_generates_all_requested_outputs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "trend_analysis.json"
    markdown = tmp_path / "trend_report.md"
    enriched = tmp_path / "network_with_trends.json"

    status = main(
        [
            "analyze",
            "--current",
            str(root / "examples" / "current_network.json"),
            "--history",
            str(root / "examples" / "history_day1.json"),
            str(root / "examples" / "history_day2.json"),
            "--papers",
            str(root / "examples" / "papers.json"),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
            "--enriched-network-output",
            str(enriched),
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    assert status == 0
    assert output.exists()
    assert markdown.exists()
    assert enriched.exists()
