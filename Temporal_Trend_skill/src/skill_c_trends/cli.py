from __future__ import annotations

import argparse
import sys

from .pipeline import analyze_trends


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skill-c-trends", description="Skill C temporal trend detection CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze emerging communities across network snapshots.")
    analyze_parser.add_argument("--current", required=True, help="Current Skill B network_analysis.json path.")
    analyze_parser.add_argument("--history", nargs="*", default=[], help="Previous Skill B network_analysis.json paths.")
    analyze_parser.add_argument("--history-dir", default=None, help="Directory containing historical network_analysis JSON files.")
    analyze_parser.add_argument("--papers", default=None, help="Optional Skill A or Skill B paper metadata JSON.")
    analyze_parser.add_argument("--output", required=True, help="Output trend_analysis.json path.")
    analyze_parser.add_argument("--markdown", default=None, help="Optional Markdown trend report path.")
    analyze_parser.add_argument("--enriched-network-output", default=None, help="Optional Skill B network JSON enriched with trend fields.")
    analyze_parser.add_argument("--artifacts-dir", default=None, help="Optional directory for trend PNG visualizations.")
    analyze_parser.add_argument("--window-days", type=int, default=7, help="Temporal window label for growth metrics.")

    args = parser.parse_args(argv)
    if args.command == "analyze":
        result = analyze_trends(
            current_path=args.current,
            output_path=args.output,
            history_paths=args.history,
            history_dir=args.history_dir,
            papers_path=args.papers,
            markdown_path=args.markdown,
            enriched_network_path=args.enriched_network_output,
            artifacts_dir=args.artifacts_dir,
            window_days=args.window_days,
        )
        print(
            "Wrote trend analysis for "
            f"{result['metrics']['current_community_count']} communities with "
            f"{result['metrics']['alert_count']} alerts to {args.output}"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
