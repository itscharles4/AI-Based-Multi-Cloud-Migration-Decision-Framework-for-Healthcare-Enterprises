"""
override_rules.py
=================
Emergency override rules for the telemedicine routing system.

Clinical rationale
------------------
In a true medical emergency (e.g., "Code Blue" — cardiac arrest, severe
respiratory failure), every millisecond matters.  We must NOT allow
cost-optimisation mathematics to add ANY delay or routing risk to critical
alerts.  If patient criticality reaches ≥ 9.0 on the 0-10 scale, the
system immediately forces routing to the local EDGE node (hospital-side
processing) regardless of the AHP score, predicted latency, or cloud cost.

This mirrors how real-world clinical escalation protocols work: a "Code Blue"
overrides normal triage queuing and gets immediate, local response.

On AWS migration, this override logic would be evaluated in the Lambda
function BEFORE invoking the AHP scoring pipeline, ensuring zero latency
introduced by the decision math during emergencies.
"""

# Threshold above which a patient is considered in a life-threatening emergency.
EMERGENCY_CRITICALITY_THRESHOLD: float = 9.0


def check_emergency_override(patient_criticality_score: float) -> bool:
    """
    Determine whether an emergency override must be applied.

    An override is triggered when `patient_criticality_score` is at or above
    EMERGENCY_CRITICALITY_THRESHOLD (9.0), representing a "Code Blue" or
    equivalent life-threatening emergency.

    When this function returns True, the caller MUST route the data to EDGE
    without running the AHP scoring — no cost-optimisation logic should
    introduce any delay or risk of misrouting during a true emergency.

    Parameters
    ----------
    patient_criticality_score : float
        Criticality on a 0–10 scale.
        0 = routine checkup data.
        10 = cardiac arrest / immediate life threat.

    Returns
    -------
    bool
        True  → Emergency override: force EDGE routing immediately.
        False → Normal flow: proceed with AHP scoring.
    """
    return patient_criticality_score >= EMERGENCY_CRITICALITY_THRESHOLD


if __name__ == "__main__":
    test_scores = [0, 2, 5, 7, 8.9, 9.0, 9.5, 10]
    print("Emergency Override Check")
    print("-" * 35)
    for score in test_scores:
        override = check_emergency_override(score)
        status   = "⚠ OVERRIDE → EDGE" if override else "Normal AHP flow"
        print(f"  criticality={score:4.1f}  →  {status}")
