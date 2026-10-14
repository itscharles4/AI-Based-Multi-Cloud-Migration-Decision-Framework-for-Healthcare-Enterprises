import sys
sys.path.insert(0, '.')
from src.decision.ahp import get_ahp_weights, normalize_criteria, DEFAULT_PAIRWISE_MATRIX

weights = get_ahp_weights(DEFAULT_PAIRWISE_MATRIX)
w_crit, w_lat, w_cost = weights
print(f"Weights: crit={w_crit:.4f} lat={w_lat:.4f} cost={w_cost:.4f}")

def score(crit, lat, cost):
    nc, nl, nco = normalize_criteria(crit, lat, cost)
    edge  = w_crit*(nc**0.7) + w_lat*(nl**0.5) + w_cost*nco
    cloud = w_crit*((1-nc)**0.7) + w_lat*((1-nl)**0.5) + w_cost*(1-nco)
    decision = "EDGE" if edge >= cloud else "CLOUD"
    return nc, nl, nco, edge, cloud, decision

# Test cases
cases = [
    (1.0, 450.0, 0.2, "EDGE"),    # high latency should override
    (6.0, 80.0,  0.4, "EDGE"),    # moderate-high criticality
    (1.0, 15.0,  0.1, "CLOUD"),   # routine, healthy network
    (5.0, 100.0, 0.5, "ANY"),     # borderline
]

print("\nCase analysis:")
for crit, lat, cost, want in cases:
    nc, nl, nco, edge, cloud, decision = score(crit, lat, cost)
    ok = "OK" if (want == "ANY" or decision == want) else "FAIL"
    print(f"  crit={crit} lat={lat} cost={cost} | nc={nc:.3f} nl={nl:.3f} | edge={edge:.4f} cloud={cloud:.4f} -> {decision} [{ok}] (want {want})")
