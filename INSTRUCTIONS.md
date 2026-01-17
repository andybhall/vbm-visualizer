# Interactive Vote-by-Mail Paper Visualizer - MVP Instructions

## Project Overview

Create an interactive web-based visualizer for the vote-by-mail extension paper that allows users to explore alternative specifications and robustness checks through a chat interface. Users will see the paper's main results (Table 2 and Figure 1) and be able to ask questions like "what if we excluded California?" or "what would this look like with only presidential elections?" The system will match their query to pre-computed analyses and display modified results.

**IMPORTANT: Before starting implementation, read the paper PDF** (`vbm_extension_paper.pdf` in the repository) **to understand:**
- The research question and findings
- The structure of Table 2 and Figure 1
- The regression specifications used
- The data structure and treatment variables
- The interpretation of results

This context is essential for generating accurate analysis descriptions and ensuring the visualizer matches the paper's style and content.

## Core Architecture

### Two-Phase Approach

**Phase 1: Pre-computation** (Run once before deployment)
- Download replication data from GitHub automatically
- Run ~5,000 regression variations across key dimensions
- Generate natural language descriptions for each analysis
- Create embeddings for semantic search
- Store all results in a single JSON file
- Generate static assets (HTML tables/figures matching paper style)

**Phase 2: Web Application** (What users interact with)
- Single self-contained HTML page displaying Table 2 and Figure 1
- Embedded chat boxes (separate for each table/figure)
- Client-side semantic search using pre-loaded embeddings
- OpenAI API calls for generating natural language responses
- Inline display of modified results (side-by-side comparisons)

## Phase 1: Pre-computation Script

### Data Acquisition

1. **Download replication data** from: https://github.com/andybhall/vbm-replication-extension
   - Clone or download the repository automatically
   - Extract the necessary data files to `/data` folder
   - The repo contains the original Thompson et al. (2020) data plus extensions through 2024

2. **Data structure**:
   - County-level panel data (126 counties: 58 CA, 29 UT, 39 WA)
   - Years: 1996-2024
   - Key variables: Democratic vote share, turnout, VBM treatment indicator
   - County identifiers, state identifiers, year, CVAP

### Analysis Dimensions to Pre-compute

Run all combinations of the following dimensions for **both** outcomes (Democratic vote share and Turnout):

#### Tier 1: Core Variations (~2,000 analyses)

**State exclusions/restrictions:**
- Exclude California (UT + WA only)
- Exclude Utah (CA + WA only)
- Exclude Washington (CA + UT only)
- California only
- Utah only
- Washington only
- Full sample (baseline)

**Regression specifications:**
- Basic: County FE + State×Year FE
- Linear Trends: County FE + State×Year FE + County Linear Trends
- Quadratic Trends: County FE + State×Year FE + County Linear Trends + County Quadratic Trends
- Population-weighted (CVAP weights): County FE + State×Year FE

**Time windows:**
- Original period: 1996-2018
- Extended period: 1996-2024
- Post-2018 only: 2018-2024
- Exclude 2024: 1996-2022

**Race types:**
- All races pooled (Presidential, Governor, Senate)
- Presidential elections only
- Governor elections only (CA only)
- Senate elections only

**VCA cohort subgroups** (California only):
- 2018 adopters only (5 counties: Madera, Napa, Nevada, Sacramento, San Mateo)
- 2020 adopters only (10 counties)
- 2022 adopters only (12 counties)
- 2024 adopters only (3 counties)
- All cohorts with separate treatment indicators (interaction model)

#### Tier 2: Robustness Checks (~3,000 additional analyses)

**Alternative clustering:**
- Cluster by state (instead of county)
- Cluster by state×year

**Regional variations:**
- Exclude large counties (e.g., Los Angeles, Orange, San Diego, Sacramento, Alameda)
- Exclude small counties (below median CVAP)
- Exclude all 2018 pilot counties (test if they drive results)
- Include only 2018 pilot counties

### Regression Specifications

For each analysis, estimate:

```
Y_cst = β * VBM_cst + γ_c + δ_st + [trends] + ε_cst
```

Where:
- Y_cst = outcome (Dem vote share or turnout) for county c, state s, year t
- VBM_cst = universal VBM treatment indicator
- γ_c = county fixed effects
- δ_st = state×year fixed effects
- [trends] = county-specific linear/quadratic trends (if specified)
- Standard errors clustered by county (or alternative as specified)

### Natural Language Description Format

For each pre-computed analysis, generate a rich description including ALL of:

```
"Table 2, Panel A, Column 2: Democratic Vote Share (1996-2024), Linear Trends specification. 
County fixed effects, State×Year fixed effects, County linear trends. 
Standard errors clustered by county. 
N=2,376 observations, 126 counties. 
Excluding California."
```

**Required fields in each description:**
1. Table/Panel/Column reference
2. Outcome variable name
3. Time period
4. Specification name (Basic/Linear Trends/Quadratic Trends)
5. All fixed effects included
6. Trend specifications
7. Standard error clustering method
8. Sample size (N observations)
9. Number of counties/clusters
10. Any exclusions, restrictions, or modifications
11. Weighting (if population-weighted)
12. Race type (if restricted to presidential/governor/senate only)

### Output Format

Store all pre-computed results in `/precomputed/results.json`:

```json
{
  "analyses": [
    {
      "id": "analysis_0001",
      "description": "Table 2, Panel A, Column 1: Democratic Vote Share...",
      "embedding": [0.123, -0.456, ...],  // 1536-dim vector
      "table_reference": "Table 2",
      "panel": "A",
      "column": 1,
      "outcome": "dem_vote_share",
      "time_period": "1996-2024",
      "specification": "basic",
      "fixed_effects": ["county", "state_year"],
      "trends": null,
      "clustering": "county",
      "n_obs": 2376,
      "n_clusters": 126,
      "exclusions": null,
      "weighted": false,
      "race_type": "pooled",
      "coefficient": 0.024,
      "std_error": 0.007,
      "p_value": 0.001,
      "ci_lower": 0.010,
      "ci_upper": 0.038,
      "table_html": "<table>...</table>",
      "figure_html": null
    },
    ...
  ],
  "metadata": {
    "total_analyses": 5000,
    "embedding_model": "text-embedding-3-small",
    "generated_date": "2026-01-17"
  }
}
```

### HTML Table/Figure Generation

For each analysis, generate:

1. **Tables**: HTML version of Table 2 (both Original and Extended columns side-by-side)
   - Match the exact styling from the PDF paper
   - Include all formatting (significance stars, standard errors in parentheses)
   - Panel structure (Panel A: Democratic Vote Share, Panel B: Turnout)
   - Notes section at bottom

2. **Figures**: HTML/SVG version of Figure 1 (both panels side-by-side)
   - Panel A: Democratic Vote Share comparison
   - Panel B: Turnout comparison  
   - Bar charts with error bars (95% CI)
   - Significance stars marked on bars
   - Match matplotlib style from PDF

### Embedding Generation

Use OpenAI's `text-embedding-3-small` model to generate embeddings for:
- All analysis descriptions (for semantic search)
- Store embeddings directly in the JSON file

## Phase 2: Web Application

### Application Structure

Create a single HTML file (`index.html`) with embedded JavaScript that is completely self-contained and works offline after initial load:

```
/app/
  index.html          # Main page
  /precomputed/
    results.json      # All pre-computed analyses with embeddings
  /assets/
    styles.css        # Styling to match paper aesthetics
    app.js           # Core application logic
```

### Page Layout

```
┌─────────────────────────────────────────────────┐
│  Replication and Extension of                   │
│  "Universal Vote-by-Mail Has No Impact..."      │
│                                                  │
│  [Brief intro paragraph from paper]             │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Table 2: Comparison of Original and Extended   │
│                                                  │
│  [Table 2 displayed - both Original and         │
│   Extended columns side by side]                │
│                                                  │
│  ┌──────────────────────────────┐              │
│  │ 💬 Chat: Ask about Table 2   │              │
│  │ "What if we excluded CA?"    │              │
│  │ [User input box]             │              │
│  └──────────────────────────────┘              │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Figure 1: Comparison of Original and Extended  │
│                                                  │
│  [Figure 1 displayed - both panels]             │
│                                                  │
│  ┌──────────────────────────────┐              │
│  │ 💬 Chat: Ask about Figure 1  │              │
│  │ "Show me just CA counties"   │              │
│  │ [User input box]             │              │
│  └──────────────────────────────┘              │
└─────────────────────────────────────────────────┘
```

### Chat Interface Implementation

**Separate chat box for each table/figure:**

1. **User input**:
   - Text input field (200 character limit)
   - Submit button
   - Clear conversation button
   - Query counter display ("3 queries remaining this hour")

2. **Conversation flow**:
   - User types query → embed query using OpenAI API
   - Client-side cosine similarity search against all pre-computed embeddings
   - Find top 3 nearest matches
   - If best match similarity > 0.7: Use that analysis
   - If best match similarity < 0.7: Tell user no good match, suggest available analyses
   - Call OpenAI API (GPT-4 or Claude) to generate natural language response
   - Display response (2-3 sentences) + modified table/figure inline

3. **Chat history**:
   - Optional: Maintain conversation history for follow-up questions
   - If implementing persistence: Keep last 5 exchanges in context
   - If too complex for MVP: Reset after each query

4. **Response format**:
   - Brief explanation (2-3 sentences)
   - Modified table/figure shown side-by-side with original
   - Highlight what changed (e.g., "The coefficient fell from 0.024 to 0.019")

### Cost Controls

Implement the following safeguards:

1. **Rate limiting**:
   - 20 queries per IP address per hour
   - Store in browser localStorage
   - Display remaining queries to user
   - Graceful error message when limit hit

2. **Token limits**:
   - Query limited to 200 characters
   - System prompts kept minimal
   - No long conversation history (or max 5 exchanges)

3. **API optimization**:
   - Use `text-embedding-3-small` for embeddings (cheap)
   - Use GPT-4o-mini for chat responses (cheaper than GPT-4)
   - Pre-compute all embeddings (never re-embed same analysis)
   - Do semantic search client-side (no API calls)

4. **User experience**:
   - Show "X queries remaining" counter
   - Explain rate limits clearly
   - Provide examples of good queries

### Semantic Search Logic

Client-side JavaScript implementation:

```javascript
async function findBestMatch(userQuery) {
  // 1. Embed user query via OpenAI API
  const queryEmbedding = await embedText(userQuery);
  
  // 2. Compute cosine similarity with all pre-computed embeddings
  const similarities = precomputedAnalyses.map(analysis => 
    cosineSimilarity(queryEmbedding, analysis.embedding)
  );
  
  // 3. Get top 3 matches
  const topMatches = getTopK(similarities, 3);
  
  // 4. Check if best match is confident enough
  if (topMatches[0].similarity < 0.7) {
    return {
      confident: false,
      matches: topMatches,
      message: "I don't have a pre-computed analysis that closely matches your query."
    };
  }
  
  return {
    confident: true,
    bestMatch: topMatches[0].analysis,
    alternatives: topMatches.slice(1, 3)
  };
}
```

### LLM Response Generation

System prompt for chat responses:

```
You are an assistant helping users explore robustness checks for a vote-by-mail study. 

The user is viewing Table 2 / Figure 1 from the paper. They asked: "{user_query}"

Based on semantic search, the closest pre-computed analysis is:
{analysis_description}

Results:
- Coefficient: {coefficient}
- Standard Error: {std_error}  
- P-value: {p_value}
- Original baseline: {original_coefficient} (SE: {original_se})

Provide a brief response (2-3 sentences max) that:
1. Directly answers their question
2. States the key result (coefficient and significance)
3. Compares to the baseline if relevant
4. Is written in clear, accessible language

The modified table/figure will be displayed automatically, so don't describe it in detail.
```

### Handling "No Good Match" Scenarios

When similarity < 0.7:

```
System prompt:
The user asked: "{user_query}"
The best match has low confidence (similarity: {similarity})

Best available match: {best_match_description}
Other available analyses include:
- {example_1}
- {example_2}
- {example_3}

Respond (2-3 sentences) by:
1. Acknowledging you don't have that exact analysis
2. Suggesting the closest alternative OR
3. Explaining what analyses ARE available (e.g., "I can show you results excluding different states, time periods, or using different specifications")
```

### Styling Requirements

Match the paper's professional academic style:

1. **Typography**:
   - Use serif font (e.g., Computer Modern, Times New Roman)
   - Clear hierarchy (H1 for title, H2 for table/figure titles)

2. **Tables**:
   - Replicate exact formatting from PDF
   - Horizontal lines for table structure
   - Significance stars (*, **, ***)
   - Standard errors in parentheses
   - Notes section below table

3. **Figures**:
   - Clean bar charts with error bars
   - Axis labels and titles
   - Legend for Original vs Extended
   - Grid lines (light gray)
   - Color scheme: Blue for Original, Light Blue for Extended (Dem vote share), Green shades (Turnout)

4. **Chat interface**:
   - Clean, minimal design
   - Light border around chat boxes
   - Clear submit button
   - Conversation bubbles for Q&A history (if implementing persistence)

## Technical Requirements

### Dependencies

**Phase 1 (Pre-computation script):**
- Python 3.10+
- pandas, numpy, statsmodels (for regressions)
- requests (for downloading data from GitHub)
- openai (for embeddings)
- json (for output)

**Phase 2 (Web app):**
- No server-side dependencies
- Client-side only: vanilla JavaScript (or minimal framework like Alpine.js if needed)
- OpenAI API key (provided by user or hardcoded for MVP)

### File Structure

```
/vbm-interactive-paper/
  /phase1_precompute/
    precompute.py           # Main pre-computation script
    requirements.txt        # Python dependencies
    README.md              # Instructions for running pre-computation
  /data/
    [Downloaded from GitHub automatically]
  /precomputed/
    results.json           # All pre-computed analyses (generated)
  /app/
    index.html            # Main web application
    styles.css            # Styling
    app.js                # Client-side logic
  INSTRUCTIONS.md         # This file
  README.md              # User-facing documentation
```

### Deployment

Simplest approach for MVP:
- Host as static site on GitHub Pages
- All files in `/app` folder
- User visits single URL
- Everything works client-side (except OpenAI API calls)

Alternative: Could use Vercel/Netlify for same static hosting approach

## Implementation Checklist

### Phase 1: Pre-computation

- [ ] Create `precompute.py` script
- [ ] Download replication data from GitHub automatically
- [ ] Load and clean data
- [ ] Define all analysis variations (Tier 1 + Tier 2)
- [ ] Run all regressions (~5,000 total)
- [ ] Generate natural language descriptions
- [ ] Generate embeddings using OpenAI API
- [ ] Generate HTML tables for each variation
- [ ] Generate HTML/SVG figures for each variation
- [ ] Save everything to `results.json`
- [ ] Verify output format and completeness

### Phase 2: Web Application  

- [ ] Create basic HTML structure
- [ ] Display baseline Table 2 (from paper)
- [ ] Display baseline Figure 1 (from paper)
- [ ] Add chat interface UI (separate boxes for table/figure)
- [ ] Implement rate limiting (localStorage)
- [ ] Implement query character limit (200 chars)
- [ ] Load `results.json` on page load
- [ ] Implement semantic search (cosine similarity)
- [ ] Implement OpenAI API integration for embedding user queries
- [ ] Implement OpenAI API integration for generating chat responses
- [ ] Display modified tables/figures inline
- [ ] Handle low-confidence matches gracefully
- [ ] Add styling to match paper aesthetics
- [ ] Add user instructions and examples
- [ ] Test end-to-end flow
- [ ] Deploy to GitHub Pages or similar

## Example User Flows

### Flow 1: Simple Exclusion Query

1. User sees Table 2 on the page
2. User types in chat box: "What if we excluded California?"
3. System embeds query, finds best match (similarity: 0.92)
4. Best match: "Table 2, Panel A, Column 1: Democratic Vote Share (1996-2024), Basic specification... Excluding California"
5. LLM generates response: "When excluding California and analyzing only Utah and Washington counties, the effect on Democratic vote share is 0.029 (SE: 0.010, p=0.004), slightly larger than the full-sample estimate of 0.024. The result remains statistically significant."
6. Modified Table 2 appears side-by-side with original, highlighting the changed coefficient

### Flow 2: Specification Change

1. User sees Figure 1 on the page
2. User types: "Show me this with only presidential elections"
3. System finds match (similarity: 0.88)
4. LLM responds: "Restricting to presidential elections only, the turnout effect is 0.023 (SE: 0.008, p=0.003), nearly identical to the pooled estimate. The partisan effect remains near zero at 0.016."
5. Modified Figure 1 appears showing only presidential election results

### Flow 3: No Good Match

1. User types: "What about third-party vote share?"
2. System finds best match (similarity: 0.51)
3. LLM responds: "I don't have a pre-computed analysis for third-party vote share. The available outcomes are Democratic vote share (two-party) and turnout. I can show you how results vary by excluding different states, time periods, or using different specifications for these outcomes."

### Flow 4: Time Period Question

1. User types: "Did the effect change after 2018?"
2. System finds match (similarity: 0.86)
3. LLM responds: "For the post-2018 period only (2018-2024), the effect on Democratic vote share is actually slightly negative at -0.011 (SE: 0.005), compared to the positive effect of 0.024 in the full sample. This suggests the partisan effect does not persist in later years."
4. Modified table shows post-2018 results only

## Success Criteria for MVP

The MVP is successful if:

1. ✅ Users can visit a single URL and immediately interact with the visualizer
2. ✅ No setup required (data is bundled, everything works client-side)
3. ✅ Chat interface correctly matches at least 80% of reasonable queries to appropriate analyses
4. ✅ Modified tables/figures display correctly with paper-quality formatting
5. ✅ Rate limiting prevents excessive API costs
6. ✅ Page loads in <3 seconds (JSON file should be <10MB)
7. ✅ Works on mobile and desktop browsers
8. ✅ Users can understand what analyses are available when queries don't match well

## Future Enhancements (Post-MVP)

- Add underlying data for dynamic re-computation
- Expand to all tables and figures in the paper
- Add more sophisticated analysis dimensions
- Implement conversation history and follow-up questions
- Add data export functionality (download modified tables/figures)
- Create shareable links to specific analyses
- Add visualizations beyond the paper (custom scatter plots, etc.)
- Implement backend vector database for faster search at scale

## Notes for Claude Code

- Prioritize getting Phase 1 working first (pre-computation)
- Verify regressions match the paper's published results before running variations
- Test semantic search with sample queries before building full web app
- Keep the web app as simple as possible - vanilla JS preferred over frameworks
- Match the paper's visual style exactly - users should feel like the paper "comes alive"
- Be conservative with API calls during testing - use mock data when possible
- Document any assumptions or limitations clearly

## API Keys and Configuration

For OpenAI API:
- Embeddings: `text-embedding-3-small` (~$0.02 per 1M tokens)
- Chat: `gpt-4o-mini` (~$0.15 per 1M input tokens)
- Expected cost for pre-computation: ~$5 (5,000 descriptions × ~200 tokens × $0.02/1M)
- Expected cost per user session: ~$0.01 (20 queries × ~500 tokens × $0.15/1M)

User should provide their OpenAI API key or hardcode for MVP testing.
