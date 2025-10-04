from __future__ import annotations
import time
from pathlib import Path
from typing import Dict, Any, List
import engine
from io_utils import write_metadata_header_md, write_citations_list

def _build_review_corpus_text(items: List[Dict[str,Any]]) -> str:
    """
    Build a consistent, label-rich corpus for Phase 2.
    Each block starts with an index and a label (the filename),
    followed by the six Phase 1 fields.
    """
    blocks = []
    for i, it in enumerate(items, 1):
        s = it["summary"]; fn = it["file"]
        blocks.append(
            f"[{i}] {fn}\n"
            f"- Main idea: {s.get('main_idea','')}\n"
            f"- Objective: {s.get('objective','')}\n"
            f"- Design: {s.get('design','')}\n"
            f"- Methods: {s.get('methods','')}\n"
            f"- Results: {s.get('results','')}\n"
            f"- Main findings: {s.get('main_findings','')}"
        )
    return "\n\n".join(blocks)

def run_review(
    items: List[Dict[str,Any]],
    out_review_md: str,
    out_citations_md: str|None,
    context: str,
    mode: str,
    cfg: Dict[str,Any],
) -> Dict[str,Any]:

    start = time.time()
    text = _build_review_corpus_text(items)

    used_mode, out, usage = engine.summarize_text(text, context, mode, cfg)
    lit = out.get("literature_review") if out else ""
    cits = out.get("contextual_citations") if out else ""

    runtime = round(time.time() - start, 2)
    meta = {
        "Items": len(items),
        "Model": cfg["model"],
        "Mode": mode,
        "Prompt tokens": usage.get("prompt_tokens",0),
        "Completion tokens": usage.get("completion_tokens",0),
        "Total tokens": usage.get("total_tokens",0),
        "Runtime (s)": runtime,
    }

    out_md = Path(out_review_md)
    write_metadata_header_md(out_md, "Literature Review", meta)
    with out_md.open("a", encoding="utf-8") as f:
        f.write("## Literature Review\n\n")
        f.write((lit.strip() if lit else "Not reported") + "\n\n")
        f.write("## Contextual Citations\n\n")
        if cits:
            for ln in cits.splitlines(): f.write(f"- {ln}\n")
        else:
            f.write("_Not reported_\n")
        f.write("\n")

    if out_citations_md:
        write_citations_list(Path(out_citations_md), cits.splitlines() if cits else [])

    return {"meta": meta, "usage": usage}
