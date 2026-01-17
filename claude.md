# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

This is an interactive web visualizer for a vote-by-mail (VBM) research paper extension. The project allows users to explore alternative specifications and robustness checks through a chat interface, viewing modified versions of Table 2 and Figure 1 from the paper.

**Two-phase architecture:**
1. **Phase 1 (Pre-computation)**: Python scripts download replication data, run ~5,000 regression variations, generate embeddings, and store results in JSON
2. **Phase 2 (Web App)**: Static HTML/JS application with client-side semantic search and OpenAI API integration for chat responses

**Data source**: County-level panel data (126 counties: 58 CA, 29 UT, 39 WA) from 1996-2024, downloaded from https://github.com/andybhall/vbm-replication-extension

---

## Commands

```bash
# Always use python3 and pip3, never python/pip
python3 script.py
pip3 install -r requirements.txt

# Run pre-computation script
python3 phase1_precompute/precompute.py

# Install dependencies
pip3 install pandas numpy statsmodels openai requests
```

---

## Project Structure

```
/phase1_precompute/     # Python pre-computation scripts
  precompute.py         # Main script: downloads data, runs regressions, generates embeddings
  requirements.txt
/data/                  # Downloaded replication data (auto-fetched from GitHub)
/precomputed/           # Generated outputs
  results.json          # All ~5,000 analyses with embeddings (~10MB)
/app/                   # Static web application
  index.html            # Single-page app with embedded chat
  styles.css            # Paper-matching academic style
  app.js                # Client-side semantic search + OpenAI integration
```

---

## Key Technical Decisions

**Regression specification**: `Y_cst = β * VBM_cst + γ_c + δ_st + [trends] + ε_cst`
- County FE (γ_c), State×Year FE (δ_st), optional county trends
- Standard errors clustered by county
- Outcomes: Democratic vote share, turnout

**Embedding model**: `text-embedding-3-small` (OpenAI)
**Chat model**: `gpt-4o-mini` (OpenAI)
**Similarity threshold**: 0.7 cosine similarity for confident matches

**Rate limiting**: 20 queries per IP per hour (localStorage-based)

---

## Companion Documents

- **SOUL.md**: Core research principles and values. Governs judgment calls.
- **INSTRUCTIONS.md**: Detailed MVP specifications, analysis dimensions, and implementation checklist.

---

## Critical Workflow Requirements

1. **Never claim something works without running a test to prove it.** After writing any code, immediately run and verify it.

2. **Work modularly.** Complete one module at a time. Report what you built, show test results, wait for confirmation before proceeding.

3. **Iterate and fix errors yourself.** Run the code, observe output, fix problems before presenting results.

4. **Be explicit about unknowns.** If uncertain, say so. Don't guess or confabulate.

5. **Preserve raw data.** Never modify original data files. All transformations produce new files in Modified Data or /precomputed.

6. **Verify data completeness.** After collecting/transforming data, check observation counts, date ranges, and coverage.

7. **Sanity check results.** Verify coefficients have plausible signs and magnitudes. Compare to paper's published baseline results.

---

## Before Starting Implementation

1. **Read the paper PDF** (`vbm_extension_paper.pdf`) to understand Table 2, Figure 1, and regression specifications
2. **Verify replication data** matches expected structure (126 counties, 1996-2024)
3. **Match baseline results** to paper before running variations

---

## Code Standards

- Use relative paths from project root
- Print progress for long operations (5,000 regressions will take time)
- Comment the why, not the what
- One task per script
- Handle errors gracefully with explicit messages
