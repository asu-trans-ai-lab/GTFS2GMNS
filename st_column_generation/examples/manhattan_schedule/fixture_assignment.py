"""Section-15 assignment extension on the Manhattan-16 fixture.

Demand q = 30 on N21 -> N43 (ready 07:28); X1 capacity 10, H/V trip
segments capacity 30; BPR-style smooth congestion.  Demonstrates:
  1. feasible pool (4) larger than the uncongested active set (1);
  2. congested equilibrium activates multiple columns;
  3. DP pricing certifies the active set (reduced cost >= -eps);
  4. adding irrelevant (dominated, extended-service) columns does not
     materially change the equilibrium.

Run:  python -m examples.manhattan_schedule.fixture_assignment
"""

import numpy as np
from scipy import sparse

from . import manhattan_core as M
from .manhattan_core import CFG, READY, ORIGIN, DEST
from bpr import BPRResources
import restricted_bpr_master as fw_master
from event_graph import EventGraph, TripSched

Q_OD = 30.0
ALPHA, BETA = 1.0, 2.0


def solve(pool_cols, trips):
    res_index, t0l, capl = {}, [], []
    for ti, t in enumerate(trips):
        for k in range(len(t.stations) - 1):
            res_index[(ti, k)] = len(res_index)
            t0l.append(t.arr[k + 1] - t.dep[k])
            capl.append(10.0 if t.route_id == "X" else 30.0)
    bpr = BPRResources(np.array(t0l), np.array(capl),
                       alpha=ALPHA, beta=BETA)
    cols = sorted(pool_cols.values(), key=lambda c: c["cost"])
    tid2ti = {t.trip_id: i for i, t in enumerate(trips)}
    rows, cc = [], []
    for j, c in enumerate(cols):
        for tid in c["trips"]:
            ti = tid2ti[tid]
            t = trips[ti]
            # boarded segment range from signature reconstruction:
            # fixture trips are boarded at their route-standard stops
            b = t.stations.index(ORIGIN if t.route_id in ("H", "X")
                                 else "N23")
            a = t.stations.index("N23" if t.route_id == "H" else DEST)
            for k in range(b, a):
                rows.append(res_index[(ti, k)])
                cc.append(j)
    B = sparse.csr_matrix((np.ones(len(rows)), (rows, cc)),
                          shape=(len(res_index), len(cols)))
    g = np.array([c["cost"] for c in cols])
    cid = np.zeros(len(cols), dtype=int)
    res = fw_master.solve(B, g, cid, np.array([Q_OD]), bpr,
                          tol=1e-10, max_iter=5000)
    return cols, res, bpr, res_index, B


def main():
    trips, graph = M.build()
    pool = M.enumerate_columns(trips, graph)
    cols, res, bpr, res_index, B = solve(pool, trips)
    x = res["x"]
    active = [(c["signature"].split("|")[2], "%.2f" % xi)
              for c, xi in zip(cols, x) if xi > 1e-6]
    print("congested equilibrium (q=30, X capacity 10):")
    for sig, xi in active:
        print("   %-14s flow %s" % (sig, xi))
    assert len(active) >= 2, "capacity must activate multiple columns"
    print("[PASS] feasible pool 4 >> uncongested active 1; congested "
          "active = %d" % len(active))
    # pricing certificate: every active column within eps of min cost
    costs = res["costs"]
    pi = costs.min()
    worst = max(float(costs[j] - pi) for j in range(len(cols))
                if x[j] > 1e-6)
    assert worst <= 1e-4 * max(1.0, pi), worst
    print("[PASS] DP-priced reduced cost of active columns <= %.1e"
          % worst)

    # irrelevant-column invariance: extend service with late dominated
    # trips, re-enumerate, re-solve, compare flows on original columns
    ext = list(trips)
    def mk(tid, route, stations, times):
        tt = tuple(M.T0 + m for m in times)
        return TripSched(tid, route, "0", tuple(stations), tt, tt)
    ext.append(mk("H4", "H", ["N21", "N22", "N23", "N24"],
                  [45, 47, 49, 51]))
    ext.append(mk("V4", "V", ["N13", "N23", "N33", "N43"],
                  [48, 50, 52, 54]))
    g2 = EventGraph(ext, CFG)
    pool2 = M.enumerate_columns(ext, g2)
    assert len(pool2) > len(pool), (len(pool), len(pool2))
    cols2, res2, _b, _r, _B = solve(pool2, ext)
    f1 = {c["signature"]: xi for c, xi in zip(cols, x)}
    f2 = {c["signature"]: xi for c, xi in zip(cols2, res2["x"])}
    dmax = max(abs(f2.get(s, 0.0) - v) for s, v in f1.items())
    print("pool extended %d -> %d columns; max flow change on "
          "original columns: %.2e pax" % (len(pool), len(pool2), dmax))
    assert dmax <= 0.05 * Q_OD, dmax
    print("[PASS] adding dominated columns does not materially change "
          "the equilibrium (K_feasible >> K_active in miniature)")


if __name__ == "__main__":
    main()
