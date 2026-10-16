"""
ahp.py
======
Analytic Hierarchy Process (AHP) helper for the 3-criteria routing decision.

What is AHP?
------------
AHP (Analytic Hierarchy Process, developed by Thomas Saaty) is a structured
mathematical method for multi-criteria decision making.  It works by:
  1. Defining the criteria to compare (here: Criticality, Latency, Cost).
  2. Asking "how much more important is criterion A than criterion B?" for every
     pair, filling a square pairwise comparison matrix.
  3. Deriving a normalised weight vector (how important each criterion is overall)
     using the eigenvector of that matrix.
  4. Checking that the human judgements are consistent (Consistency Ratio < 0.1).

Why AHP for routing?
--------------------
Unlike binary threshold rules ("if latency > 100ms go to edge"), AHP balances
THREE criteria simultaneously and is fully explainable — important for clinical
and regulatory audits.

Criteria used
-------------
  C1 — Patient Criticality Score  (0-10 scale, 10 = cardiac arrest)
  C2 — Predicted Latency          (ms, from the LSTM forecasting module)
  C3 — Cloud Compute Cost Index   (0-1 normalised index)

Weights rationale (from literature survey)
------------------------------------------
  Criticality is "moderately more important" than Latency  → ratio 3
  Criticality is "much more important" than Cost           → ratio 5
  Latency is "moderately more important" than Cost         → ratio 3
"""

import numpy as np

# ---------------------------------------------------------------------------
# Default pairwise comparison matrix  [C1 vs C1, C1 vs C2, C1 vs C3]
#                                     [C2 vs C1, C2 vs C2, C2 vs C3]
#                                     [C3 vs C1, C3 vs C2, C3 vs C3]
# ---------------------------------------------------------------------------
DEFAULT_PAIRWISE_MATRIX: list = [
    [1,   3,   5  ],   # Criticality vs (Criticality, Latency, Cost)
    [1/3, 1,   3  ],   # Latency     vs (Criticality, Latency, Cost)
    [1/5, 1/3, 1  ],   # Cost        vs (Criticality, Latency, Cost)
]

# Random Index for n=3 (standard AHP lookup table value)
_RI_3 = 0.58


def get_ahp_weights(pairwise_matrix: list) -> list:
    """
    Derive normalised AHP criterion weights from a 3×3 pairwise comparison matrix.

    Algorithm (eigenvector approximation — standard in AHP literature):
      Step 1: Normalise each column by dividing every element by the column sum.
      Step 2: Average each row of the normalised matrix → that row's weight.

    Parameters
    ----------
    pairwise_matrix : list[list[float]]
        3×3 matrix where element [i][j] = "how much more important is i than j?"
        Diagonal must be 1.0.  Element [j][i] must equal 1 / [i][j].

    Returns
    -------
    list[float]
        Normalised weight vector summing to 1.0.
        Index 0 = Criticality weight, 1 = Latency weight, 2 = Cost weight.
    """
    M = np.array(pairwise_matrix, dtype=float)

    # Step 1 — Column normalisation
    col_sums = M.sum(axis=0)
    M_norm   = M / col_sums

    # Step 2 — Row averages = weights
    weights = M_norm.mean(axis=1).tolist()
    return weights


def consistency_ratio(pairwise_matrix: list, weights: list) -> float:
    """
    Compute the AHP Consistency Ratio (CR) for a 3-criterion problem.

    A CR < 0.10 confirms the pairwise judgements are acceptably consistent
    (i.e., human ratings don't contradict themselves too much).

    Formula
    -------
      λ_max = (1/n) * Σ (M · w)_i / w_i
      CI    = (λ_max - n) / (n - 1)
      CR    = CI / RI          where RI = 0.58 for n = 3

    Parameters
    ----------
    pairwise_matrix : list[list[float]]
    weights         : list[float]  Weights from get_ahp_weights().

    Returns
    -------
    float  Consistency Ratio (should be < 0.10).
    """
    M = np.array(pairwise_matrix, dtype=float)
    w = np.array(weights,         dtype=float)
    n = len(w)

    # Weighted sum vector
    Mw       = M @ w
    lambdas  = Mw / w        # element-wise ratio
    lambda_max = float(lambdas.mean())

    CI = (lambda_max - n) / (n - 1)
    CR = CI / _RI_3
    return CR


def normalize_criteria(
    criticality: float,
    latency_ms: float,
    cost_index: float,
) -> tuple:
    """
    Normalize the three raw input criteria to a comparable [0, 1] scale.

    Semantics
    ---------
    criticality : 0-10 scale → divide by 10.
                  Higher value = higher urgency to route to EDGE.

    latency_ms  : 0-500ms scale → divide by 500.
                  Higher value = network is degraded → stronger signal to use EDGE.
                  (So: high normalised latency "votes" for EDGE — direction is correct.)

    cost_index  : Already 0-1.  Higher value = cloud is expensive → slight preference for EDGE.

    Parameters
    ----------
    criticality : float  Patient criticality score (0-10).
    latency_ms  : float  Predicted latency in milliseconds.
    cost_index  : float  Cloud compute cost index (0-1).

    Returns
    -------
    tuple(float, float, float)  (norm_criticality, norm_latency, norm_cost)
    """
    norm_criticality = min(criticality / 10.0, 1.0)
    norm_latency     = min(latency_ms  / 500.0, 1.0)
    norm_cost        = min(max(cost_index, 0.0), 1.0)
    return norm_criticality, norm_latency, norm_cost


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    weights = get_ahp_weights(DEFAULT_PAIRWISE_MATRIX)
    cr      = consistency_ratio(DEFAULT_PAIRWISE_MATRIX, weights)

    print("AHP Weight Derivation for DEFAULT_PAIRWISE_MATRIX")
    print("=" * 50)
    criteria = ["Patient Criticality", "Predicted Latency", "Compute Cost"]
    for name, w in zip(criteria, weights):
        print(f"  {name:<25} : {w:.4f}  ({w*100:.1f}%)")
    print(f"\n  Consistency Ratio (CR) : {cr:.4f}  {'✓ PASS (< 0.10)' if cr < 0.1 else '✗ FAIL (>= 0.10)'}")

    print("\nNormalized criteria demo:")
    nc, nl, nco = normalize_criteria(8.5, 210.5, 0.4)
    print(f"  criticality=8.5 → {nc:.3f}")
    print(f"  latency=210.5ms → {nl:.3f}")
    print(f"  cost=0.4        → {nco:.3f}")
