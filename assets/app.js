/**
 * VBM Interactive Paper Visualizer
 * Client-side application for exploring pre-computed regression analyses
 */

// Global state
let analysisData = null;
let queryCount = { table: 0 };
const MAX_QUERIES_PER_HOUR = 100;  // Higher limit for local use
const SIMILARITY_THRESHOLD = 0.5;

// DOM Elements
const elements = {};

/**
 * Initialize the application
 */
async function init() {
    console.log('Initializing VBM Visualizer...');

    // Cache DOM elements
    cacheElements();

    // Show loading overlay
    showLoading(true);

    // Load pre-computed data
    try {
        await loadAnalysisData();
    } catch (error) {
        console.error('Failed to load analysis data:', error);
        showError('Failed to load analysis data. Please refresh the page.');
        return;
    }

    // Note: API key is handled server-side via .env file

    // Initialize displays
    displayBaselineTable();

    // Set up event listeners
    setupEventListeners();

    // Load query counts from localStorage
    loadQueryCounts();

    // Hide loading overlay
    showLoading(false);

    console.log('Initialization complete');
}

/**
 * Cache frequently used DOM elements
 */
function cacheElements() {
    elements.loading = document.getElementById('loading');
    elements.tableBody = document.getElementById('table-body');
    elements.tableMessages = document.getElementById('table-messages');
    elements.tableInput = document.getElementById('table-input');
    elements.tableSubmit = document.getElementById('table-submit');
    elements.tableQueryCounter = document.getElementById('table-query-counter');
}

/**
 * Load pre-computed analysis data
 */
async function loadAnalysisData() {
    const response = await fetch('/precomputed/results.json');
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    analysisData = await response.json();
    console.log(`Loaded ${analysisData.analyses.length} analyses`);
}

/**
 * Load query counts from localStorage
 */
function loadQueryCounts() {
    const stored = localStorage.getItem('vbm_query_counts');
    if (stored) {
        const { counts, timestamp } = JSON.parse(stored);
        // Reset if more than 1 hour old
        if (Date.now() - timestamp < 3600000) {
            queryCount = counts;
        }
    }
    updateQueryCounters();
}

/**
 * Save query counts to localStorage
 */
function saveQueryCounts() {
    localStorage.setItem('vbm_query_counts', JSON.stringify({
        counts: queryCount,
        timestamp: Date.now()
    }));
}

/**
 * Update query counter displays
 */
function updateQueryCounters() {
    const tableRemaining = MAX_QUERIES_PER_HOUR - queryCount.table;
    elements.tableQueryCounter.textContent = `${tableRemaining} queries remaining`;
    elements.tableSubmit.disabled = tableRemaining <= 0;
}

/**
 * Show/hide loading overlay
 */
function showLoading(show) {
    elements.loading.classList.toggle('active', show);
}

/**
 * Show error message
 */
function showError(message) {
    alert(message); // Simple for now
}

/**
 * Display baseline Table 2
 */
function displayBaselineTable() {
    // Find baseline analyses for the table
    const specs = ['basic', 'linear', 'quadratic'];
    const specLabels = ['Basic', 'Linear Trends', 'Quadratic Trends'];

    let html = '';

    for (let i = 0; i < specs.length; i++) {
        const spec = specs[i];
        const label = specLabels[i];

        // Find analyses for this specification
        const demOrig = findAnalysis('dem_share', spec, null, [1996, 2018]);
        const demExt = findAnalysis('dem_share', spec, null, null);
        const turnOrig = findAnalysis('turnout', spec, null, [1996, 2018]);
        const turnExt = findAnalysis('turnout', spec, null, null);

        html += `
            <tr>
                <td>${label}</td>
                <td>${formatCell(demOrig)}</td>
                <td>${formatCell(demExt)}</td>
                <td>${formatCell(turnOrig)}</td>
                <td>${formatCell(turnExt)}</td>
            </tr>
        `;
    }

    // Add observation count row
    const demExtFull = findAnalysis('dem_share', 'basic', null, null);
    const turnExtFull = findAnalysis('turnout', 'basic', null, null);

    html += `
        <tr>
            <td>Observations</td>
            <td colspan="2">${demExtFull ? demExtFull.n_obs.toLocaleString() : 'N/A'}</td>
            <td colspan="2">${turnExtFull ? turnExtFull.n_obs.toLocaleString() : 'N/A'}</td>
        </tr>
    `;

    elements.tableBody.innerHTML = html;
}

/**
 * Find a specific analysis
 */
function findAnalysis(outcome, specification, stateFilter, timeWindow) {
    return analysisData.analyses.find(a =>
        a.outcome === outcome &&
        a.specification === specification &&
        a.state_filter === stateFilter &&
        JSON.stringify(a.time_window) === JSON.stringify(timeWindow) &&
        !a.weighted &&
        a.cluster === 'county'
    );
}

/**
 * Format a table cell with coefficient and standard error
 */
function formatCell(analysis) {
    if (!analysis || !analysis.success) {
        return '—';
    }

    const coef = analysis.coefficient;
    const se = analysis.std_error;
    const pVal = analysis.p_value;

    let stars = '';
    if (pVal < 0.01) stars = '***';
    else if (pVal < 0.05) stars = '**';
    else if (pVal < 0.1) stars = '*';

    const sigClass = pVal < 0.05 ? 'significant' : '';

    return `
        <div class="coefficient ${sigClass}">${coef.toFixed(3)}${stars}</div>
        <div class="std-error">(${se.toFixed(3)})</div>
    `;
}


/**
 * Get significance stars
 */
function getSignificanceStars(analysis) {
    if (!analysis) return '';
    const p = analysis.p_value;
    if (p < 0.01) return '***';
    if (p < 0.05) return '**';
    if (p < 0.1) return '*';
    return '';
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Table chat
    elements.tableSubmit.addEventListener('click', () => handleQuery('table'));
    elements.tableInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleQuery('table');
    });

    // Example buttons
    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const query = e.target.dataset.query;
            elements.tableInput.value = query;
            handleQuery('table');
        });
    });
}

/**
 * Handle a user query
 */
async function handleQuery(section) {
    const inputEl = elements.tableInput;
    const messagesEl = elements.tableMessages;
    const query = inputEl.value.trim();

    if (!query) return;

    // Check rate limit
    if (queryCount[section] >= MAX_QUERIES_PER_HOUR) {
        addMessage(messagesEl, 'assistant', 'Query limit reached. Please try again in an hour.');
        return;
    }

    // Disable input
    inputEl.disabled = true;
    elements.tableSubmit.disabled = true;

    // Add user message
    addMessage(messagesEl, 'user', query);
    inputEl.value = '';

    // Show loading spinner
    const loadingEl = document.createElement('div');
    loadingEl.className = 'chat-loading';
    loadingEl.innerHTML = '<div class="chat-spinner"></div><span>Analyzing...</span>';
    messagesEl.appendChild(loadingEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    try {
        // Use keyword matching to find relevant analysis
        const match = findBestMatchKeyword(query, section);

        // Increment query count
        queryCount[section]++;
        saveQueryCounts();
        updateQueryCounters();

        if (match.similarity < SIMILARITY_THRESHOLD) {
            // No good match
            const response = await generateNoMatchResponse(query, match);
            addMessage(messagesEl, 'assistant', response);
        } else {
            // Good match found
            const response = await generateResponse(query, match.analysis);
            addMessage(messagesEl, 'assistant', response, match.analysis);
        }
    } catch (error) {
        console.error('Query failed:', error);
        addMessage(messagesEl, 'assistant', `Error: ${error.message}. Please check your API key and try again.`);
    }

    // Remove loading spinner
    const spinner = messagesEl.querySelector('.chat-loading');
    if (spinner) spinner.remove();

    // Re-enable input
    inputEl.disabled = false;
    elements.tableSubmit.disabled = queryCount.table >= MAX_QUERIES_PER_HOUR;
    inputEl.focus();
}

/**
 * Find best match using keyword search
 */
function findBestMatchKeyword(query, section) {
    const queryLower = query.toLowerCase();
    const relevantOutcomes = ['dem_share', 'turnout', 'dem_share_pres', 'dem_share_gov', 'dem_share_sen'];

    let bestMatch = null;
    let bestScore = 0;

    // Define keyword patterns - order matters! Exclude patterns must come first
    const patterns = [
        // Exclusion patterns (must be checked first)
        { regex: /exclud(e|ing)\s*(california|ca)\b/i, filter: 'exclude_CA' },
        { regex: /exclud(e|ing)\s*(utah|ut)\b/i, filter: 'exclude_UT' },
        { regex: /exclud(e|ing)\s*(washington|wa)\b/i, filter: 'exclude_WA' },
        { regex: /excl\.?\s*(ca|california)\b/i, filter: 'exclude_CA' },
        { regex: /excl\.?\s*(ut|utah)\b/i, filter: 'exclude_UT' },
        { regex: /excl\.?\s*(wa|washington)\b/i, filter: 'exclude_WA' },
        // Time periods
        { regex: /original|1996.?2018/i, time: [1996, 2018] },
        { regex: /post.?2018|after 2018|2018.?2024/i, time: [2018, 2024] },
        { regex: /without 2024|exclud.*2024|1996.?2022|excl.*2024/i, time: [1996, 2022] },
        // Outcomes
        { regex: /pres(ident(ial)?)?/i, outcome: 'dem_share_pres' },
        { regex: /gov(ernor)?/i, outcome: 'dem_share_gov' },
        { regex: /sen(at(e|or))?/i, outcome: 'dem_share_sen' },
        { regex: /turn(out)?/i, outcome: 'turnout' },
        { regex: /vote\s*share|partisan|democrat/i, outcome: 'dem_share' },
        // Specifications
        { regex: /linear/i, spec: 'linear' },
        { regex: /quadratic|quad\b/i, spec: 'quadratic' },
        { regex: /basic|simple/i, spec: 'basic' },
        // Other
        { regex: /weight(ed)?|population/i, weighted: true },
    ];

    // State inclusion patterns - checked separately to avoid conflict with exclude
    const statePatterns = [
        { regex: /\b(california|ca)\b/i, filter: 'CA' },
        { regex: /\b(utah|ut)\b/i, filter: 'UT' },
        { regex: /\b(washington|wa)\b/i, filter: 'WA' },
    ];

    // Extract criteria from query
    let targetFilter = null;
    let targetTime = null;
    let targetOutcome = null;
    let targetWeighted = false;
    let targetSpec = 'basic';

    // First pass: check all patterns
    for (const pattern of patterns) {
        if (pattern.regex.test(queryLower)) {
            if (pattern.filter) targetFilter = pattern.filter;
            if (pattern.time) targetTime = pattern.time;
            if (pattern.outcome) targetOutcome = pattern.outcome;
            if (pattern.weighted) targetWeighted = pattern.weighted;
            if (pattern.spec) targetSpec = pattern.spec;
        }
    }

    // Second pass: check state inclusion patterns only if no exclude filter was set
    if (!targetFilter || !targetFilter.startsWith('exclude_')) {
        for (const pattern of statePatterns) {
            if (pattern.regex.test(queryLower)) {
                // Only set if not already an exclude filter
                if (!targetFilter || !targetFilter.startsWith('exclude_')) {
                    targetFilter = pattern.filter;
                }
                break;
            }
        }
    }

    // Score each analysis
    for (const analysis of analysisData.analyses) {
        if (!relevantOutcomes.includes(analysis.outcome)) continue;

        let score = 0;

        // State filter match
        if (targetFilter && analysis.state_filter === targetFilter) score += 10;
        else if (!targetFilter && !analysis.state_filter) score += 2;

        // Time window match
        if (targetTime && JSON.stringify(analysis.time_window) === JSON.stringify(targetTime)) score += 10;
        else if (!targetTime && !analysis.time_window) score += 2;

        // Outcome match
        if (targetOutcome && analysis.outcome === targetOutcome) score += 10;
        else if (!targetOutcome && analysis.outcome === 'dem_share') score += 1;

        // Weighted match
        if (targetWeighted && analysis.weighted) score += 5;
        else if (!targetWeighted && !analysis.weighted) score += 1;

        // Specification match
        if (analysis.specification === targetSpec) score += 3;

        if (score > bestScore) {
            bestScore = score;
            bestMatch = analysis;
        }
    }

    // Normalize score to similarity-like value (0-1)
    const maxPossibleScore = 30;
    const similarity = bestScore / maxPossibleScore;

    return { analysis: bestMatch, similarity: similarity };
}

/**
 * Generate a response using Claude API (via local proxy)
 */
async function generateResponse(query, analysis) {
    const systemPrompt = `You are an assistant helping users explore robustness checks for a vote-by-mail study.

The user is viewing results from Thompson et al. (2020) "Universal Vote-by-Mail Has No Impact on Partisan Turnout or Vote Share".

Based on their query, you found a pre-computed analysis:
- Description: ${analysis.description}
- Coefficient: ${analysis.coefficient?.toFixed(4)}
- Standard Error: ${analysis.std_error?.toFixed(4)}
- P-value: ${analysis.p_value?.toFixed(4)}
- N observations: ${analysis.n_obs}
- Clusters: ${analysis.n_clusters}

Provide a brief response (2-3 sentences max) that:
1. Directly answers their question
2. States the key result (coefficient, significance level)
3. Notes how it compares to baseline if relevant
4. Is written in clear, accessible language

Keep it concise - the modified results will be displayed separately.`;

    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            system: systemPrompt,
            messages: [{ role: 'user', content: query }],
            max_tokens: 200
        })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || 'Chat completion failed');
    }

    const data = await response.json();
    return data.content;
}

/**
 * Generate a response when no good match is found (via local proxy)
 */
async function generateNoMatchResponse(query, match) {
    const availableAnalyses = `
Available analyses include:
- Different state samples: CA only, UT only, WA only, or excluding any state
- Different time periods: 1996-2018 (original), 1996-2024 (extended), 2018-2024 (post-2018), 1996-2022
- Different specifications: Basic, Linear Trends, Quadratic Trends
- Population-weighted estimates
- Presidential, Governor, or Senate elections separately
`;

    const systemPrompt = `You are an assistant helping users explore robustness checks for a vote-by-mail study.

The user asked a question, but the best match has low confidence (similarity: ${match.similarity.toFixed(2)}).

Best available match: ${match.analysis?.description || 'None found'}

${availableAnalyses}

Respond briefly (2-3 sentences) by:
1. Acknowledging you don't have that exact analysis pre-computed
2. Suggesting the closest available alternative OR explaining what analyses ARE available`;

    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            system: systemPrompt,
            messages: [{ role: 'user', content: query }],
            max_tokens: 200
        })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || 'Chat completion failed');
    }

    const data = await response.json();
    return data.content;
}

/**
 * Add a message to the chat display
 */
function addMessage(container, role, text, analysis = null) {
    const messageEl = document.createElement('div');
    messageEl.className = `chat-message ${role}`;

    let html = text;

    if (analysis) {
        // Add result preview
        const stars = getSignificanceStars(analysis);
        html += `
            <div class="result-preview">
                <strong>Modified Result:</strong><br>
                ${analysis.filter_desc || 'Full sample'}<br>
                Coefficient: <span class="highlight-change">${analysis.coefficient?.toFixed(4)}${stars}</span>
                (SE: ${analysis.std_error?.toFixed(4)})<br>
                N = ${analysis.n_obs?.toLocaleString()}, Clusters = ${analysis.n_clusters}
            </div>
        `;
    }

    messageEl.innerHTML = html;
    container.appendChild(messageEl);
    container.scrollTop = container.scrollHeight;
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', init);
