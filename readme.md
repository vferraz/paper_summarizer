# 📘 Automated Research Paper Summarizer & Literature Review Generator

This project automates the process of **summarizing research papers** and **synthesizing literature reviews** using Large Language Models (LLMs).  
It takes a collection of academic PDFs, produces structured per-paper summaries, and generates an aggregated literature review with contextual citations — all in Markdown and JSONL formats.

---

## 🧠 Overview

The pipeline operates in two main phases:

### **Phase 1 — Paper Summaries**
- Extracts text from PDFs using [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/).
- Annotates pages with explicit page anchors (`<<p=#>>`).
- Uses an LLM to produce structured JSON summaries with six fields:
  - `main_idea`
  - `objective`
  - `design`
  - `methods`
  - `results`
  - `main_findings`
- Each bullet is concise (≤25 words) and includes a page reference.

### **Phase 2 — Literature Review**
- Uses the structured outputs from Phase 1 to generate:
  1. **A synthesized literature review** (cross-paper analysis of findings, methods, and differences).
  2. **Contextual citations**, formatted as:
     ```
     [idx] <label> — Core: ...; Design: ...; Methods: ...; Key result: ... [p=#]
     ```

---

## 🏗️ Project Structure

````

paper_summarizer/
├── engine.py              # Core LLM logic (map-reduce, error handling, schema enforcement)
├── pdf_ingest.py          # PDF reading utilities (PyMuPDF)
├── io_utils.py            # Markdown + JSON I/O helpers
├── phase_summaries.py     # Phase 1: per-paper summaries
├── phase_review.py        # Phase 2: literature synthesis
├── run_pipeline.py        # Main entry point and configuration
└── .env                   # (Optional) contains OPENAI_API_KEY

````

---

## ⚙️ Setup

### 1. Create and activate the environment
```bash
conda create -n summarizer_env python=3.11
conda activate summarizer_env
````

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

*(If you don’t have a `requirements.txt`, install manually:)*

```bash
pip install openai python-dotenv PyMuPDF
```

### 3. Configure your OpenAI credentials

Add an `.env` file in the project root:

```
OPENAI_API_KEY=sk-yourkeyhere
```

Or export it directly:

```bash
export OPENAI_API_KEY="sk-yourkeyhere"
```

---

## 🚀 Usage

### Run both phases (summaries + review)

```bash
python run_pipeline.py
```

### Run only the summaries (Phase 1)

```bash
python run_pipeline.py  # edit CONFIG["run"] = "phase1" in run_pipeline.py
```

### Run only the review (Phase 2)

```bash
python run_pipeline.py  # edit CONFIG["run"] = "phase2"
```

Outputs are stored in the `output/` directory:

```
output/
├── summaries.md           # Human-readable summaries
├── summaries.jsonl        # Structured JSONL output
├── literature_review.md   # Synthesized review + citations
└── citations.md           # (Optional) Flat citation list
```

---

## 🧩 Configuration

All runtime settings are in `run_pipeline.py` under `CONFIG`.

Key parameters:

* `run`: `"phase1"`, `"phase2"`, or `"both"`.
* `input_pattern`: glob for PDFs, e.g. `"input/*.pdf"`.
* `model`: model name (e.g., `"gpt-4o-mini"` or `"gpt-5"`).
* `temperature`: LLM creativity; must be > 0 for GPT-5 models.
* `mode`: `"auto"`, `"always"`, or `"never"`, controlling fallback between single-pass and chunked summarization.
* `binary_overlap`: controls overlap between chunks when splitting long texts.

---

## 🛡️ Robustness Features

* ✅ **Automatic retry and chunking** for large PDFs (recursive map-reduce).
* ✅ **Graceful handling** of corrupted or partially unreadable pages.
* ✅ **Automatic truncation** before “References” sections.
* ✅ **Detailed error logs** (thanks to the improved `engine.py`):
  * Real API error messages are printed (no silent failures).
  * GPT-5 temperature guard prevents invalid parameter errors.
* ✅ **Token usage tracking** for every run.

---

## 🧰 Debugging

* All LLM and I/O errors are printed with context tags like `[ENGINE ERROR]`.
* To silence informational logs while keeping errors visible:

  ```bash
  export SUMMARIZER_DEBUG=0
  ```
* If a PDF triggers a `MuPDF error: could not parse color space`, you can:

  * Ignore it (usually harmless), or
  * Replace the PDF text extractor with a resilient per-page try/except (already implemented).

---

## 🧪 Example Output

```
# Research Paper Summaries

| Metric | Value |
|---|---|
| Files processed | 25 |
| Successful | 25 |
| Model | gpt-5 |
| Runtime (s) | 53.2 |

## 2305.12564v1.pdf
**Main idea:** Investigates how LLMs simulate group-level behavior [p=1]  
**Objective:** Evaluate alignment between simulated and empirical distributions [p=2]  
...
```

---

## 💡 Tips

* If `Prompt tokens = 0` → check your API key and model name.
* If using GPT-5 → ensure `temperature == 1`.
* For faster, cheaper tests, use `gpt-4o-mini`.
* If processing many PDFs, consider batching or adding delays to avoid rate limits.

---

## 🧾 License

MIT License © 2025 — you’re free to modify and distribute with attribution.

---


