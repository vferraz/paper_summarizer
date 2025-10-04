from __future__ import annotations
import json, time, re
from pathlib import Path
from typing import Dict, Any, List
from pdf_ingest import load_corpus
import engine
from io_utils import write_metadata_header_md, format_summary_section

REF_HEAD_RE = re.compile(r'^\s*(references|bibliography|literature)\b', re.I | re.M)
PAGE_BREAK = "\n\n----- PAGE BREAK -----\n\n"

def _truncate_at_references(pages: List[str]) -> List[str]:
    for idx, p in enumerate(pages):
        if REF_HEAD_RE.search(p):
            return pages[:idx]
    return pages

def run_summaries(
    input_pattern: str,
    out_md: str,
    out_jsonl: str,
    mode: str,
    cfg: Dict[str,Any],
) -> Dict[str,Any]:

    start = time.time()
    corpus, scan_rows = load_corpus(input_pattern)
    pages_total = sum(v["page_count"] for v in corpus.values())
    chars_total = sum(len(v["text"]) for v in corpus.values())

    out_md_p = Path(out_md)
    out_jsonl_p = Path(out_jsonl)
    out_jsonl_p.parent.mkdir(parents=True, exist_ok=True)

    token_usage = {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
    sections: List[str] = []
    items_for_review: List[Dict[str,Any]] = []

    processed=success=0
    with out_jsonl_p.open("w", encoding="utf-8") as jf:
        for name, item in corpus.items():
            processed += 1
            pages = _truncate_at_references(item["pages"])
            # Build annotated text with explicit page anchors like <<p=5>> before each page
            annotated = []
            for i, page in enumerate(pages, 1):
                annotated.append(f"<<p={i}>>\n{page}")
            text = "\n\n".join(annotated)

            print(f"[SUM ] {name}  pages={len(pages)}  mode={mode}  chars={len(text)}")
            used_mode, summary, usage = engine.summarize_text(text, "", mode, cfg)
            token_usage = engine.add_usage(token_usage, usage)

            if summary:
                success += 1
                jf.write(json.dumps({"file": name, "summary": summary}, ensure_ascii=False) + "\n")
                sections.append(format_summary_section(name, summary, cfg["schema_keys"]))
                items_for_review.append({"file": name, "summary": summary})
            else:
                jf.write(json.dumps({"file": name, "summary": None}, ensure_ascii=False) + "\n")
                sections.append(f"## {name}\n\n**Error:** model returned no summary.\n")
                items_for_review.append({"file": name, "summary": {k: "Not reported" for k in cfg["schema_keys"]}})

    runtime = round(time.time() - start, 2)
    meta = {
        "Files processed": processed,
        "Successful": success,
        "Total pages": pages_total,
        "Total chars": chars_total,
        "Model": cfg["model"],
        "Mode": mode,
        "Prompt tokens": token_usage["prompt_tokens"],
        "Completion tokens": token_usage["completion_tokens"],
        "Total tokens": token_usage["total_tokens"],
        "Runtime (s)": runtime,
    }

    write_metadata_header_md(out_md_p, "Research Paper Summaries", meta)
    with out_md_p.open("a", encoding="utf-8") as f:
        f.write("\n".join(sections))

    return {"meta": meta, "items": items_for_review, "usage": token_usage}
