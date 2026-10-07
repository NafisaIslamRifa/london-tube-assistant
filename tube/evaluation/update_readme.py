"""Write the latest evaluation results into README.md, between marker comments.

    python -m tube.evaluation.update_readme

So the README always shows numbers produced by the code, never hand-typed ones.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

README = Path("README.md")
RETRIEVAL = Path("eval/results_retrieval.json")
AGENT = Path("eval/results_agent.json")


def fmt(v) -> str:
    return "–" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


def retrieval_table(report: dict) -> str:
    keys = [("page_hit@1", "Right page first"), ("page_recall@5", "Right page in top 5"),
            ("section_hit@1", "**Right section first**"), ("section_hit@3", "Right section in top 3"),
            ("section_mrr", "Section MRR")]
    modes = report["modes"]
    n = next(iter(modes.values()))["summary"]["n"]
    lines = [f"Measured on {n} everyday-language questions, each mapped to the TfL page and "
             f"section that answers it ({report['run_at'][:10]}).", "",
             "| Search | " + " | ".join(label for _, label in keys) + " |",
             "|---|" + "---|" * len(keys)]
    for name, m in modes.items():
        s = m["summary"]
        lines.append(f"| {name} | " + " | ".join(fmt(s[k]) for k, _ in keys) + " |")
    return "\n".join(lines)


def agent_table(report: dict) -> str:
    s = report["summary"]
    rows = [("Questions passing every check", f"{round(s['pass_rate'] * s['n'])} / {s['n']}"),
            ("Tool selection accuracy", fmt(s["tool_selection"])),
            ("Citation accuracy (expected TfL page linked)", fmt(s["citation_accuracy"])),
            ("Live answers that state the data's time", fmt(s["live_timestamp_rate"])),
            ("Unknown station handled without inventing a fare", fmt(s["unknown_station_handled"])),
            ("Invented-link rate", fmt(s["invented_link_rate"])),
            ("Median time per question", f"{s['median_seconds']} s" if s["median_seconds"] else "–"),
            ("Average tokens per question", fmt(s["avg_tokens"]))]
    return "\n".join([f"Model: `{report['model']}` · run {report['run_at'][:10]} · "
                      f"{s['errors']} error{'' if s['errors'] == 1 else 's'}.", "", "| Metric | Result |", "|---|---|"]
                     + [f"| {a} | {b} |" for a, b in rows])


def replace_block(text: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- {name}:start -->)(.*?)(<!-- {name}:end -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"Markers for {name} not found in README.md")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def update(readme: str, retrieval: dict | None, agent: dict | None) -> str:
    if retrieval:
        readme = replace_block(readme, "retrieval-eval", retrieval_table(retrieval))
    if agent:
        readme = replace_block(readme, "agent-eval", agent_table(agent))
    return readme


def main() -> None:
    load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    README.write_text(update(README.read_text(encoding="utf-8"), load(RETRIEVAL), load(AGENT)),
                      encoding="utf-8")
    print("README.md updated with the latest evaluation results.")


if __name__ == "__main__":
    main()
