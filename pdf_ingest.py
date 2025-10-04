from __future__ import annotations
from typing import List, Dict, Tuple, Any
from pathlib import Path
import glob
import fitz  # PyMuPDF

# ---------- Core I/O ----------

class PDFReadError(Exception):
    pass

#def read_pdf_pages(path: str | Path) -> List[str]:
#    p = Path(path)
#    try:
#        with fitz.open(str(p)) as doc:
#            return [(page.get_text("text", flags=fitz.TEXT_PRESERVE_LIGATURES) or "").strip()
#                    for page in doc]
#    except Exception as e:
#        raise PDFReadError(f"Could not open PDF: {p}") from e

def read_pdf_pages(path: str | Path) -> List[str]:
    p = Path(path)
    try:
        with fitz.open(str(p)) as doc:
            pages = []
            for i in range(len(doc)):
                try:
                    text = doc[i].get_text("text", flags=fitz.TEXT_PRESERVE_LIGATURES) or ""
                except Exception:
                    text = ""  # keep pipeline flowing even if one page fails
                pages.append(text.strip())
            return pages
    except Exception as e:
        raise PDFReadError(f"Could not open PDF: {p}") from e


# ---------- Public API ----------

def load_corpus(pattern: str = "input/*.pdf") -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Returns:
      corpus: {
        "<filename>.pdf": {
          "pages": [str, ...],
          "text": str,                 # pages joined with page breaks
          "page_count": int,
        },
        ...
      }
      rows: ingest stats per file for reporting
    """
    corpus: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []

    for path in sorted(glob.glob(pattern)):
        name = Path(path).name
        try:
            pages = read_pdf_pages(path)
            joined = "\n\n----- PAGE BREAK -----\n\n".join(pages)
            corpus[name] = {"pages": pages, "text": joined, "page_count": len(pages)}
            chars_total = len(joined)
            rows.append({
                "file": name,
                "pages": len(pages),
                "chars_total": chars_total,
                "avg_chars_per_page": int(chars_total / len(pages)) if pages else 0,
                "status": "ok",
                "error": ""
            })
        except PDFReadError as e:
            rows.append({
                "file": name,
                "pages": 0,
                "chars_total": 0,
                "avg_chars_per_page": 0,
                "status": "error",
                "error": str(e)
            })
    return corpus, rows

def format_report(rows: List[Dict[str, Any]]) -> str:
    total = len(rows)
    ok = sum(1 for r in rows if r["status"] == "ok")
    pages_total = sum(r["pages"] for r in rows if r["status"] == "ok")
    chars_total = sum(r["chars_total"] for r in rows if r["status"] == "ok")

    lines = []
    lines.append("="*80)
    lines.append("Input scan summary")
    lines.append("-"*80)
    lines.append(f"Files found: {total}")
    lines.append(f"Successful:  {ok}")
    lines.append(f"Errors:      {total - ok}")
    if ok:
        lines.append(f"Total pages: {pages_total}")
        lines.append(f"Total chars: {chars_total}")
    lines.append("="*80)
    lines.append(f"{'File':50} {'Pg':>4} {'Chars':>10} {'Avg/pg':>7} {'Status':>8}")
    lines.append("-"*80)
    for r in rows:
        lines.append(f"{r['file'][:50]:50} {r['pages']:>4} {r['chars_total']:>10} {r['avg_chars_per_page']:>7} {r['status']:>8}")
        if r["status"] != "ok" and r["error"]:
            lines.append(f"  -> {r['error']}")
    lines.append("="*80)
    return "\n".join(lines)

# ---------- Optional CLI ----------

if __name__ == "__main__":
    _, rows = load_corpus("input/*.pdf")
    print(format_report(rows))
