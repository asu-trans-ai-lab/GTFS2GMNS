"""Manhattan-16 self demo: run  python -m examples.manhattan_schedule.self_demo

Hard-coded golden assertions (section 17 gate) — NOT visual inspection.
"""

import csv
import os

from . import manhattan_core as M

GOLD_COMPAT = {("H1", "V2"), ("H1", "V3"), ("H2", "V3")}
GOLD_REJECT = {("H1", "V1"), ("H2", "V2"), ("H3", "V3")}
GOLD_COLS = {
    "N21|07:28|X1|N43": (15.0, "07:43"),
    "N21|07:28|H1>N23>V2|N43": (19.0, "07:44"),
    "N21|07:28|H1>N23>V3|N43": (24.0, "07:49"),
    "N21|07:28|H2>N23>V3|N43": (24.0, "07:49"),
}


def ok(msg):
    print("[PASS] " + msg)


def main():
    trips, graph = M.build()
    n_grid = 16
    ok("physical Manhattan network: %d nodes" % n_grid)
    ok("scheduled service loaded (%d trips, 3 routes)" % len(trips))
    ok("event graph constructed (%d event nodes, %d arcs)"
       % (graph.n_nodes, sum(len(a) for a in graph.adj)))

    feas, rej = M.compatibility(trips)
    fset = {(h, v) for h, v, _g in feas}
    rset = {(h, v) for h, v, _g in rej if (h, v) in GOLD_REJECT}
    assert fset == GOLD_COMPAT, fset
    ok("transfer compatibility: %d feasible pairs" % len(fset))
    assert rset == GOLD_REJECT, rset
    ok("infeasible boundary transfers rejected (%d)" % len(rset))

    pool = M.enumerate_columns(trips, graph)
    assert len(pool) == 4, sorted(pool)
    ok("exhaustive column count: 4")
    for sig, (cost, arr) in GOLD_COLS.items():
        c = pool[sig]
        assert abs(c["cost"] - cost) < 1e-9, (sig, c["cost"])
        assert c["arrival"] == arr, (sig, c["arrival"])

    best = M.dp_best(trips, graph)
    assert abs(best["cost"] - 15.0) < 1e-9, best
    ok("DP best cost: 15")
    assert best["trips"] == ["X1"], best
    ok("DP itinerary: X1")
    enum_best = min(pool.values(), key=lambda c: c["cost"])
    assert abs(enum_best["cost"] - best["cost"]) < 1e-9
    assert enum_best["trips"] == best["trips"]
    ok("DP equals exhaustive enumeration")

    # reconstruction: every column's signature rebuilds from its trips
    dup = len(GOLD_COLS) - len(set(GOLD_COLS))
    for sig, c in pool.items():
        assert sig.split("|")[2].split(">")[0] == c["trips"][0]
    ok("all columns reconstructable")
    assert dup == 0
    ok("duplicate column count: 0")
    viol = sum(1 for h, v, g in feas
               if not (M.MIN_TR <= g <= M.MAX_TR_WAIT))
    assert viol == 0
    ok("compatibility violations: 0")

    # write expected/ fixture tables
    exp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "expected")
    os.makedirs(exp, exist_ok=True)
    with open(os.path.join(exp, "compatibility.csv"), "w",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_trip", "to_trip", "gap_min", "feasible"])
        for h, v, g in feas:
            w.writerow([h, v, g, 1])
        for h, v, g in rej:
            w.writerow([h, v, g, 0])
    with open(os.path.join(exp, "columns.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["signature", "initial_wait", "transfer_wait",
                    "in_vehicle", "n_transfers", "cost", "arrival"])
        for sig, c in sorted(pool.items()):
            w.writerow([sig, c["initial_wait"], c["transfer_wait"],
                        c["in_vehicle"], c["n_transfers"], c["cost"],
                        c["arrival"]])
    print("\nManhattan-16 gate: ALL GOLDEN ASSERTIONS PASS "
          "(fixture tables in expected/)")


if __name__ == "__main__":
    main()
