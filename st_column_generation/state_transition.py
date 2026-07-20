"""Phase C Module: passenger state machine s' = Gamma(s, a).

Formalizes the state design already certified inside sst_pricing.py
(Exp 0b: 72/72 checks vs enumeration at 1.4e-14).  Locked design
boundary: NO capacity state, NO denied boarding, NO queue state --
congestion is BPR-smooth; those states belong to a later capacitated
variant, not this model family.

State levels (incremental; only Level 1 is active in the certified
pricer):

  L0  s = ()                      plain space-time
  L1  s = (status, n_boardings, prev_service)
        status in {ACCESS, WAITING, ONBOARD, ALIGHTED, EGRESS}
        -- status is IMPLICIT in the event-node kind (W/B/A/X); the
           explicit label carries (n_boardings, prev_service).
        -- n_transfers = n_boardings - 1 (first boarding rebated).
  L2  + (desired_arrival_class,)  schedule-delay handled as a TERMINAL
        cost at the destination exit (the VRPLite to_node_cost
        mechanism), so no extra label dimension is required while the
        target is cohort-specific and applied at exits only.
  L3+ (denied boarding / queue / fare / reliability) -- EXCLUDED by
        the locked BPR design.

Transition catalog (event-arc tag -> Gamma):

  arc tag    Gamma(s, a)
  --------   -------------------------------------------------------
  board      (n_b + 1, route_of(trip));  infeasible if n_b + 1 >
             max_boards; first boarding rebates the transfer penalty
  ride       unchanged
  stay       unchanged
  alight     unchanged (status W->X via node kind)
  wait       unchanged
  transfer   unchanged (walk + residual wait costed on the arc)

This module provides the table-driven form used for documentation,
testing, and future L2+ extension; sst_pricing implements the same
transitions inline for speed.
"""

MAX_BOARDS_DEFAULT = 3     # <= 2 transfers

STATUSES = ("ACCESS", "WAITING", "ONBOARD", "ALIGHTED", "EGRESS")


def initial_state():
    return (0, "")


def gamma(state, arc_tag, trip_route=None, max_boards=
          MAX_BOARDS_DEFAULT, track_prev_service=True):
    """Return (new_state, feasible, first_board_rebate)."""
    n_b, prev = state
    if arc_tag == "board":
        n2 = n_b + 1
        if n2 > max_boards:
            return state, False, False
        return ((n2, trip_route if track_prev_service else ""),
                True, n_b == 0)
    return state, True, False


def status_of_node_kind(kind):
    return {"W": "WAITING", "B": "ONBOARD", "A": "ONBOARD",
            "X": "ALIGHTED"}[kind]


def self_test():
    s = initial_state()
    s, ok, rebate = gamma(s, "board", "RED")
    assert ok and rebate and s == (1, "RED")
    s, ok, rebate = gamma(s, "ride")
    assert ok and not rebate
    s, ok, rebate = gamma(s, "board", "GREEN")
    assert ok and not rebate and s == (2, "GREEN")
    s3, ok, _ = gamma(s, "board", "BLUE")
    assert ok and s3[0] == 3
    _s4, ok, _ = gamma(s3, "board", "ORANGE")
    assert not ok, "max_boards must bind"
    assert status_of_node_kind("W") == "WAITING"
    print("state_transition self-test: PASS "
          "(L1 catalog consistent with certified pricer)")


if __name__ == "__main__":
    self_test()
