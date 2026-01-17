"""
precompute.py

Pre-computes ~5,000 regression variations for the VBM visualizer.
Generates natural language descriptions and embeddings for semantic search.

Usage:
    python3 phase1_precompute/precompute.py
"""

import pandas as pd
import numpy as np
import pyfixest as pf
import json
import os
import warnings
from itertools import product
from datetime import datetime

warnings.filterwarnings('ignore')

# Paths
DATA_PATH = 'data/data/processed/analysis_extended.csv'
VCA_PATH = 'data/data/extension/california_vbm_adoption.csv'
OUTPUT_PATH = 'precomputed/results.json'

# Global data cache
_df = None
_vca = None


def load_data():
    """Load and cache the analysis data."""
    global _df, _vca
    if _df is None:
        print("Loading data...")
        _df = pd.read_csv(DATA_PATH)
        _vca = pd.read_csv(VCA_PATH, na_values=[], keep_default_na=False)

        # Merge VCA adoption info
        _df = _df.merge(_vca[['county', 'vca_first_year']], on='county', how='left')
        _df['vca_first_year'] = _df['vca_first_year'].fillna('Never')

        print(f"  Loaded {len(_df)} observations, {_df['county_id'].nunique()} counties")
    return _df.copy(), _vca


def filter_data(df, state_filter=None, time_window=None, race_type=None,
                exclude_large=False, exclude_small=False, vca_cohort=None):
    """Apply filters to the dataset.

    Args:
        df: DataFrame
        state_filter: 'CA', 'UT', 'WA', 'exclude_CA', 'exclude_UT', 'exclude_WA', or None (all)
        time_window: tuple (start_year, end_year) or None
        race_type: 'pres', 'gov', 'sen', or None (pooled)
        exclude_large: Exclude top 5 counties by CVAP
        exclude_small: Exclude counties below median CVAP
        vca_cohort: '2018', '2020', '2022', '2024', or None (all)

    Returns:
        Filtered DataFrame and description string
    """
    desc_parts = []

    # State filter
    if state_filter:
        if state_filter.startswith('exclude_'):
            exclude_state = state_filter.replace('exclude_', '')
            df = df[df['state'] != exclude_state]
            desc_parts.append(f"excluding {exclude_state}")
        else:
            df = df[df['state'] == state_filter]
            desc_parts.append(f"{state_filter} only")

    # Time window
    if time_window:
        start, end = time_window
        df = df[(df['year'] >= start) & (df['year'] <= end)]
        desc_parts.append(f"{start}-{end}")

    # VCA cohort filter (California only)
    if vca_cohort:
        df = df[df['vca_first_year'] == vca_cohort]
        desc_parts.append(f"{vca_cohort} VCA cohort only")

    # Size filters
    if exclude_large:
        # Get median CVAP per county
        county_cvap = df.groupby('county_id')['cvap'].median()
        large_counties = county_cvap.nlargest(5).index.tolist()
        df = df[~df['county_id'].isin(large_counties)]
        desc_parts.append("excluding 5 largest counties")

    if exclude_small:
        county_cvap = df.groupby('county_id')['cvap'].median()
        median_cvap = county_cvap.median()
        small_counties = county_cvap[county_cvap < median_cvap].index.tolist()
        df = df[~df['county_id'].isin(small_counties)]
        desc_parts.append("excluding small counties (below median CVAP)")

    return df, ", ".join(desc_parts) if desc_parts else "full sample"


def prepare_outcome_data(df, outcome):
    """Prepare data for a specific outcome variable.

    Args:
        df: DataFrame
        outcome: 'dem_share', 'turnout', 'dem_share_pres', 'dem_share_gov', 'dem_share_sen'

    Returns:
        DataFrame ready for regression
    """
    if outcome == 'dem_share':
        # Create long format pooling all race types
        df_vote = df[['state', 'county', 'county_id', 'year', 'state_year', 'treat',
                      'dem_share_gov', 'dem_share_pres', 'dem_share_sen',
                      'year_c', 'year_c2', 'cvap']].copy()
        df_long = pd.melt(df_vote,
                          id_vars=['state', 'county', 'county_id', 'year', 'state_year',
                                  'treat', 'year_c', 'year_c2', 'cvap'],
                          value_vars=['dem_share_gov', 'dem_share_pres', 'dem_share_sen'],
                          var_name='office', value_name='dem_share')
        return df_long[df_long['dem_share'].notna()].copy()
    elif outcome == 'turnout':
        return df[df['turnout_share'].notna()].copy()
    elif outcome in ['dem_share_pres', 'dem_share_gov', 'dem_share_sen']:
        return df[df[outcome].notna()].copy()
    else:
        raise ValueError(f"Unknown outcome: {outcome}")


def run_regression(df, outcome, specification, weighted=False, cluster='county'):
    """Run a single regression specification.

    Args:
        df: Prepared DataFrame
        outcome: outcome variable name
        specification: 'basic', 'linear', 'quadratic'
        weighted: Use CVAP weights
        cluster: 'county' or 'state' or 'state_year'

    Returns:
        dict with coefficient, SE, p-value, CI, N, etc.
    """
    # Determine outcome column
    if outcome == 'turnout':
        y_var = 'turnout_share'
    elif outcome == 'dem_share':
        y_var = 'dem_share'
    else:
        y_var = outcome

    # Build formula
    if specification == 'basic':
        formula = f"{y_var} ~ treat | county_id + state_year"
        spec_desc = "Basic: County FE + State×Year FE"
    elif specification == 'linear':
        formula = f"{y_var} ~ treat + i(county_id, year_c) | county_id + state_year"
        spec_desc = "Linear Trends: County FE + State×Year FE + County Linear Trends"
    elif specification == 'quadratic':
        formula = f"{y_var} ~ treat + i(county_id, year_c) + i(county_id, year_c2) | county_id + state_year"
        spec_desc = "Quadratic Trends: County FE + State×Year FE + County Linear + Quadratic Trends"
    else:
        raise ValueError(f"Unknown specification: {specification}")

    # Set up clustering
    if cluster == 'county':
        vcov = {"CRV1": "county_id"}
        cluster_desc = "county"
    elif cluster == 'state':
        vcov = {"CRV1": "state"}
        cluster_desc = "state"
    elif cluster == 'state_year':
        vcov = {"CRV1": "state_year"}
        cluster_desc = "state×year"
    else:
        raise ValueError(f"Unknown cluster: {cluster}")

    # Set up weights
    weights = df['cvap'].values if weighted else None

    try:
        if weighted:
            m = pf.feols(formula, data=df, vcov=vcov, weights=weights)
        else:
            m = pf.feols(formula, data=df, vcov=vcov)

        coef = m.coef()['treat']
        se = m.se()['treat']

        # Calculate p-value and CI
        t_stat = coef / se
        from scipy import stats
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=m._N - 2))
        ci_lower = coef - 1.96 * se
        ci_upper = coef + 1.96 * se

        return {
            'coefficient': float(coef),
            'std_error': float(se),
            'p_value': float(p_value),
            'ci_lower': float(ci_lower),
            'ci_upper': float(ci_upper),
            'n_obs': int(m._N),
            'n_clusters': int(df['county_id'].nunique()),
            'specification_desc': spec_desc,
            'cluster_desc': cluster_desc,
            'weighted': weighted,
            'success': True
        }
    except Exception as e:
        return {
            'coefficient': None,
            'std_error': None,
            'p_value': None,
            'ci_lower': None,
            'ci_upper': None,
            'n_obs': 0,
            'n_clusters': 0,
            'specification_desc': spec_desc,
            'cluster_desc': cluster_desc,
            'weighted': weighted,
            'success': False,
            'error': str(e)
        }


def generate_description(outcome, specification, filter_desc, time_window, weighted, cluster):
    """Generate natural language description for semantic search."""
    # Outcome name
    outcome_names = {
        'dem_share': 'Democratic Vote Share (pooled across all races)',
        'dem_share_pres': 'Democratic Vote Share (Presidential elections)',
        'dem_share_gov': 'Democratic Vote Share (Governor elections)',
        'dem_share_sen': 'Democratic Vote Share (Senate elections)',
        'turnout': 'Voter Turnout'
    }
    outcome_name = outcome_names.get(outcome, outcome)

    # Specification name
    spec_names = {
        'basic': 'Basic specification with County and State×Year fixed effects',
        'linear': 'Linear Trends specification with County, State×Year FE, and county-specific linear time trends',
        'quadratic': 'Quadratic Trends specification with County, State×Year FE, and county-specific linear and quadratic time trends'
    }
    spec_name = spec_names.get(specification, specification)

    # Time period
    if time_window:
        time_desc = f"for the period {time_window[0]}-{time_window[1]}"
    else:
        time_desc = "for all years (1996-2024)"

    # Weighted
    weight_desc = "Population-weighted by CVAP. " if weighted else ""

    # Clustering
    cluster_desc = f"Standard errors clustered by {cluster}."

    # Filter description
    if filter_desc and filter_desc != "full sample":
        filter_part = f"Sample: {filter_desc}."
    else:
        filter_part = "Full sample of CA, UT, and WA counties."

    description = f"{outcome_name} {time_desc}. {spec_name}. {weight_desc}{cluster_desc} {filter_part}"

    return description


def define_analysis_grid():
    """Define all analysis variations to run.

    Returns:
        List of dicts, each specifying one analysis
    """
    analyses = []
    analysis_id = 0

    # Outcomes
    outcomes = ['dem_share', 'turnout', 'dem_share_pres', 'dem_share_gov', 'dem_share_sen']

    # Specifications
    specifications = ['basic', 'linear', 'quadratic']

    # State filters
    state_filters = [
        None,  # full sample
        'CA', 'UT', 'WA',  # single state
        'exclude_CA', 'exclude_UT', 'exclude_WA'  # exclude one state
    ]

    # Time windows
    time_windows = [
        None,  # all years (1996-2024)
        (1996, 2018),  # original period
        (2018, 2024),  # post-2018 only
        (1996, 2022),  # exclude 2024
    ]

    # Weighting
    weighted_options = [False, True]

    # Clustering
    cluster_options = ['county', 'state']

    # Generate Tier 1: Core variations
    print("Generating Tier 1 analysis grid (core variations)...")
    tier1_count = 0

    for outcome, spec, state, time_win, weighted in product(
        outcomes, specifications, state_filters, time_windows, weighted_options
    ):
        # Skip some invalid combinations
        # Governor elections only exist in CA
        if outcome == 'dem_share_gov' and state in ['UT', 'WA', 'exclude_CA']:
            continue

        analyses.append({
            'id': f'analysis_{analysis_id:05d}',
            'tier': 1,
            'outcome': outcome,
            'specification': spec,
            'state_filter': state,
            'time_window': time_win,
            'weighted': weighted,
            'cluster': 'county',
            'exclude_large': False,
            'exclude_small': False,
            'vca_cohort': None
        })
        analysis_id += 1
        tier1_count += 1

    print(f"  Tier 1: {tier1_count} analyses")

    # Generate Tier 2: Robustness checks
    print("Generating Tier 2 analysis grid (robustness checks)...")
    tier2_count = 0

    # Alternative clustering (state-level)
    for outcome, spec in product(['dem_share', 'turnout'], specifications):
        analyses.append({
            'id': f'analysis_{analysis_id:05d}',
            'tier': 2,
            'outcome': outcome,
            'specification': spec,
            'state_filter': None,
            'time_window': None,
            'weighted': False,
            'cluster': 'state',
            'exclude_large': False,
            'exclude_small': False,
            'vca_cohort': None
        })
        analysis_id += 1
        tier2_count += 1

    # Size-based exclusions
    for outcome, spec in product(['dem_share', 'turnout'], ['basic', 'linear']):
        # Exclude large counties
        analyses.append({
            'id': f'analysis_{analysis_id:05d}',
            'tier': 2,
            'outcome': outcome,
            'specification': spec,
            'state_filter': None,
            'time_window': None,
            'weighted': False,
            'cluster': 'county',
            'exclude_large': True,
            'exclude_small': False,
            'vca_cohort': None
        })
        analysis_id += 1
        tier2_count += 1

        # Exclude small counties
        analyses.append({
            'id': f'analysis_{analysis_id:05d}',
            'tier': 2,
            'outcome': outcome,
            'specification': spec,
            'state_filter': None,
            'time_window': None,
            'weighted': False,
            'cluster': 'county',
            'exclude_large': False,
            'exclude_small': True,
            'vca_cohort': None
        })
        analysis_id += 1
        tier2_count += 1

    # VCA cohort-specific analyses (CA only)
    for outcome, cohort in product(['dem_share_pres', 'turnout'], ['2018', '2020', '2022', '2024']):
        analyses.append({
            'id': f'analysis_{analysis_id:05d}',
            'tier': 2,
            'outcome': outcome,
            'specification': 'basic',
            'state_filter': 'CA',
            'time_window': None,
            'weighted': False,
            'cluster': 'county',
            'exclude_large': False,
            'exclude_small': False,
            'vca_cohort': cohort
        })
        analysis_id += 1
        tier2_count += 1

    print(f"  Tier 2: {tier2_count} analyses")
    print(f"  Total: {len(analyses)} analyses")

    return analyses


def run_all_analyses(analyses, progress_every=100):
    """Run all specified analyses.

    Args:
        analyses: List of analysis specifications
        progress_every: Print progress every N analyses

    Returns:
        List of completed analyses with results
    """
    df_base, vca = load_data()
    results = []

    total = len(analyses)
    success_count = 0
    fail_count = 0

    print(f"\nRunning {total} analyses...")

    for i, spec in enumerate(analyses):
        if (i + 1) % progress_every == 0:
            print(f"  Progress: {i+1}/{total} ({100*(i+1)/total:.1f}%) - {success_count} success, {fail_count} failed")

        # Apply filters
        df, filter_desc = filter_data(
            df_base.copy(),
            state_filter=spec['state_filter'],
            time_window=spec['time_window'],
            exclude_large=spec['exclude_large'],
            exclude_small=spec['exclude_small'],
            vca_cohort=spec['vca_cohort']
        )

        # Skip if too few observations
        if len(df) < 20:
            fail_count += 1
            continue

        # Prepare outcome data
        try:
            df_reg = prepare_outcome_data(df, spec['outcome'])
        except Exception as e:
            fail_count += 1
            continue

        if len(df_reg) < 20:
            fail_count += 1
            continue

        # Run regression
        result = run_regression(
            df_reg,
            spec['outcome'],
            spec['specification'],
            weighted=spec['weighted'],
            cluster=spec['cluster']
        )

        if not result['success']:
            fail_count += 1
            continue

        # Generate description
        description = generate_description(
            spec['outcome'],
            spec['specification'],
            filter_desc,
            spec['time_window'],
            spec['weighted'],
            spec['cluster']
        )

        # Compile full result
        full_result = {
            'id': spec['id'],
            'tier': spec['tier'],
            'description': description,
            'outcome': spec['outcome'],
            'specification': spec['specification'],
            'state_filter': spec['state_filter'],
            'time_window': spec['time_window'],
            'weighted': spec['weighted'],
            'cluster': spec['cluster'],
            'filter_desc': filter_desc,
            **result
        }

        results.append(full_result)
        success_count += 1

    print(f"\nCompleted: {success_count} successful, {fail_count} failed")
    return results


def generate_embeddings(results, batch_size=100):
    """Generate embeddings for all analysis descriptions using OpenAI API.

    Args:
        results: List of analysis results with descriptions
        batch_size: Number of texts to embed per API call

    Returns:
        results with embeddings added
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("WARNING: OPENAI_API_KEY not set. Skipping embedding generation.")
        print("  Set the environment variable and re-run, or generate embeddings later.")
        return results

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    print(f"\nGenerating embeddings for {len(results)} analyses...")

    descriptions = [r['description'] for r in results]
    embeddings = []

    for i in range(0, len(descriptions), batch_size):
        batch = descriptions[i:i+batch_size]
        print(f"  Embedding batch {i//batch_size + 1}/{(len(descriptions)-1)//batch_size + 1}")

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )

        batch_embeddings = [item.embedding for item in response.data]
        embeddings.extend(batch_embeddings)

    # Add embeddings to results
    for r, emb in zip(results, embeddings):
        r['embedding'] = emb

    print(f"  Generated {len(embeddings)} embeddings")
    return results


def clean_for_json(obj):
    """Replace NaN/Inf with None for JSON compatibility."""
    import math
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def save_results(results, output_path):
    """Save results to JSON file."""
    output = {
        'analyses': clean_for_json(results),
        'metadata': {
            'total_analyses': len(results),
            'generated_date': datetime.now().isoformat(),
            'data_source': 'github.com/andybhall/vbm-replication-extension'
        }
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(output, f)

    # Calculate file size
    file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
    print(f"\nSaved {len(results)} analyses to {output_path} ({file_size:.2f} MB)")


def main():
    """Main entry point."""
    print("=" * 70)
    print("VBM VISUALIZER - PRE-COMPUTATION")
    print("=" * 70)

    # Define analysis grid
    analyses = define_analysis_grid()

    # Run all analyses
    results = run_all_analyses(analyses)

    # Generate embeddings (if API key available)
    results = generate_embeddings(results)

    # Save results
    save_results(results, OUTPUT_PATH)

    print("\n" + "=" * 70)
    print("PRE-COMPUTATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
