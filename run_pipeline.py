from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List

from phase_summaries import run_summaries
from phase_review import run_review

# ===================== EDIT ONLY THIS CONFIG =====================
CONFIG: Dict[str, Any] = {
    # Run mode: "phase1" (summaries only), "phase2" (review only), or "both"
    "run": "both",

    "input_pattern": "input/*.pdf",
    "outputs": {
        "summaries_md":    "output/summaries.md",
        "summaries_jsonl": "output/summaries.jsonl",
        "review_md":       "output/literature_review.md",
        "citations_md":    "output/citations.md",
    },

    # Phase 1 (per-paper summaries)
    "phase1": {
        "mode": "auto",  # "auto" | "always" | "never"
        "cfg": {
            "model": "gpt-5",
            "schema_keys": ["main_idea","objective","design","methods","results","main_findings"],
            "drop_refs_after_page": None,     # disable fixed-page truncation
            "cut_at_references": True,        # prefer semantic cut by heading
            "binary_overlap": 500,
            "temperature": 1,               # reduce fluff
            "prompts": {
                "system": (
                    "You are an expert scientific summarizer.\\n"
                    "Return a STRICT JSON object with EXACT keys:\\n"
                    "  main_idea, objective, design, methods, results, main_findings.\\n"
                    "For EACH value, write 2–4 ultra-concise bullets (max 25 words each).\\n"
                    "The text contains explicit page anchors in the form <<p=#>> before each page.\\n"
                    "After each bullet, append the page anchor [p=#] matching the most relevant page (pick one).\\n"
                    "Copy numbers/terms exactly; do NOT invent or infer. If nothing is reported, write 'Not reported'.\\n"
                    "No extra keys or commentary."
                ),
                # Phase 1 is context-free -> {context} is ignored here
                "single": (
                    "Summarize into the required fields using ONLY the text below.\\n"
                    "Prioritize research question(s), sample/population, design/manipulations, measures, statistical methods,\\n"
                    "key effect sizes/coefficients, and the main conclusion(s).\\n\\n"
                    "TEXT:\\n{text}"
                ),
                "map": (
                    "This is a PART of one paper. Extract ONLY what is present in this chunk.\\n"
                    "Return the same strict JSON with bullet style and page anchors.\\n\\n"
                    "CHUNK:\\n{chunk}"
                ),
                "reduce": (
                    "You are given multiple partial JSON summaries from chunks of the SAME paper.\\n"
                    "Merge into ONE final JSON with the exact keys. Remove duplicates, keep the most specific bullets,\\n"
                    "and preserve page anchors. If a field is never reported, write 'Not reported'.\\n\\n"
                    "PARTIALS:\\n{partials}"
                ),
            },
        },
    },

    # Phase 2 (synthesis + contextual citations)
    "phase2": {
        "context": "",
        "mode": "auto",
        "cfg": {
            "model": "gpt-5",
            "schema_keys": ["literature_review","contextual_citations"],
            "drop_refs_after_page": None,  # not used here
            "cut_at_references": False,
            "binary_overlap": 500,
            "temperature": 1,
            "prompts": {
                "system": (
                    "You are an expert reviewer.\\n"
                    "Return a STRICT JSON object with EXACT keys: literature_review, contextual_citations.\\n"
                    "literature_review: 1–2 paragraphs synthesizing similarities/differences across papers (methods, samples, results, disagreements).\\n"
                    "contextual_citations: newline-separated, ONE line per paper in EXACT format:\\n"
                    "[<idx>] <label> — Core: <1 short clause>; Design: <design/sample>; Methods: <method/model>; "
                    "Key result: <most important quantitative/result phrase> [p=# if known].\\n"
                    "<idx> is the paper number from the corpus; <label> is the file name unless an Author (Year) is explicit in the text.\\n"
                    "No extra keys or commentary."
                ),
                "single": (
                    'Context: "{context}"\\n\\n'
                    "You are given structured summaries of multiple papers.\\n"
                    "Produce the synthesis and the contextual citations in the exact format.\\n\\n"
                    "SUMMARIES:\\n{text}"
                ),
                "map": (
                    'Context: "{context}"\\n\\n'
                    "This is a PART of the summaries corpus. Extract ONLY what is present here and return the same strict JSON.\\n"
                    "For contextual_citations, include only items supported by this chunk.\\n\\n"
                    "CHUNK:\\n{chunk}"
                ),
                "reduce": (
                    'Context: "{context}"\\n\\n'
                    "You are given multiple partial JSON outputs for the same task.\\n"
                    "Merge into ONE final JSON with the exact keys. Concatenate literature_review coherently;\\n"
                    "deduplicate contextual_citations (newline-separated list).\\n\\n"
                    "PARTIALS:\\n{partials}"
                ),
            },
        },
    },
}
# =================== END EDITABLE CONFIG ===================

def main() -> None:
    outs = CONFIG["outputs"]
    if CONFIG["run"] == "phase1":
        _ = run_summaries(
            input_pattern = CONFIG["input_pattern"],
            out_md        = outs["summaries_md"],
            out_jsonl     = outs["summaries_jsonl"],
            mode          = CONFIG["phase1"]["mode"],
            cfg           = CONFIG["phase1"]["cfg"],
        )
        print("[PIPE] Done (phase1)")
        return

    if CONFIG["run"] == "phase2":
        # Load items from Phase 1 output
        items: List[Dict[str,Any]] = []
        with Path(outs["summaries_jsonl"]).open("r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("summary"): items.append(row)
        _ = run_review(
            items            = items,
            out_review_md    = outs["review_md"],
            out_citations_md = outs["citations_md"],
            context          = CONFIG["phase2"]["context"],
            mode             = CONFIG["phase2"]["mode"],
            cfg              = CONFIG["phase2"]["cfg"],
        )
        print("[PIPE] Done (phase2)")
        return

    # both
    s = run_summaries(
        input_pattern = CONFIG["input_pattern"],
        out_md        = outs["summaries_md"],
        out_jsonl     = outs["summaries_jsonl"],
        mode          = CONFIG["phase1"]["mode"],
        cfg           = CONFIG["phase1"]["cfg"],
    )
    _ = run_review(
        items            = s["items"],
        out_review_md    = outs["review_md"],
        out_citations_md = outs["citations_md"],
        context          = CONFIG["phase2"]["context"],
        mode             = CONFIG["phase2"]["mode"],
        cfg              = CONFIG["phase2"]["cfg"],
    )
    print("[PIPE] Done (both phases)")

if __name__ == "__main__":
    main()
