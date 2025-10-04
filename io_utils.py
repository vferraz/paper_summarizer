from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List

def write_metadata_header_md(path: Path, title: str, meta: Dict[str,Any]) -> None:
    lines = [f"# {title}", ""]
    lines += ["| Metric | Value |","|---|---|"]
    for k,v in meta.items(): lines.append(f"| {k} | {v} |")
    lines += ["", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

def format_summary_section(filename: str, summary: Dict[str,str], schema_keys: List[str]) -> str:
    label = {
        "main_idea":"Main idea / summary",
        "objective":"Objective",
        "design":"Design",
        "methods":"Methods",
        "results":"Results",
        "main_findings":"Main findings",
        "contextual_citation":"Contextual citation",
    }
    lines = [f"## {filename}", ""]
    for k in schema_keys:
        lines.append(f"**{label.get(k,k)}:** {summary.get(k,'Not reported')}")
        lines.append("")
    return "\n".join(lines)

def write_citations_list(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
