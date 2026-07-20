"""Manhattan-16 schedule laboratory: core fixture logic (Release -1).

One synthetic service system, fully hand-checkable:
  4x4 Manhattan grid (2 min/block), OD N21 -> N43, ready 07:28,
  routes H (eastbound local), V (southbound local), X (direct express,
  no intermediate boarding), transfer station N23 with
  2 <= dep - arr <= 12.

Golden truth (hand-calculated, section 6-8 of the spec):
  Gamma = {(H1,V2),(H1,V3),(H2,V3)}          |Gamma| = 3
  columns C1..C4 with costs {15, 19, 24, 24}  |C| = 4
  unique minimum: C1 = [X1], cost 15, arrive 07:43

Cost convention: g = initial_wait + transfer_wait(full dep-arr gap)
+ in_vehicle + 3 * transfers.  Realized in the shared engine with
beta_wait = beta_walk = 1, beta_iv = 1, beta_transfer = 3,
transfer_walk = 2 (so walk 2 + residual wait = full gap).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)  # modules live at the st_column_generation root

from event_graph import EventGraph, TripSched          # noqa: E402
from sst_pricing import SSTPricer                      # noqa: E402

T0 = 7 * 60                       # minutes after midnight for 07:00
READY = T0 + 28                   # 07:28
ORIGIN, DEST, XFER = "N21", "N43", "N23"
MIN_TR, MAX_TR_WAIT = 2.0, 12.0

CFG = {"beta_iv": 1.0, "beta_wait": 1.0, "beta_walk": 1.0,
       "beta_transfer": 3.0, "beta_early": 0.0, "beta_late": 0.0,
       "arrival_target_offset": 0.0, "transfer_walk": MIN_TR,
       "access_walk": 0.0, "egress_walk": 0.0}


def timetable():
    def trip(tid, route, stations, times):
        tt = tuple(T0 + m for m in times)
        return TripSched(tid, route, "0", tuple(stations), tt, tt)
    H = [trip("H1", "H", ["N21", "N22", "N23", "N24"], [30, 32, 34, 36]),
         trip("H2", "H", ["N21", "N22", "N23", "N24"], [35, 37, 39, 41]),
         trip("H3", "H", ["N21", "N22", "N23", "N24"], [40, 42, 44, 46])]
    V = [trip("V1", "V", ["N13", "N23", "N33", "N43"], [33, 35, 37, 39]),
         trip("V2", "V", ["N13", "N23", "N33", "N43"], [38, 40, 42, 44]),
         trip("V3", "V", ["N13", "N23", "N33", "N43"], [43, 45, 47, 49])]
    X = [trip("X1", "X", ["N21", "N43"], [33, 43])]
    return H + V + X


def build():
    trips = timetable()
    graph = EventGraph(trips, CFG)
    return trips, graph


def compatibility(trips):
    """All (arrival event, departure event) pairs at N23 with
    2 <= dep - arr <= 12; plus the rejected boundary pairs."""
    arrs = [(t.trip_id, t.arr[t.stations.index(XFER)])
            for t in trips if t.route_id == "H"]
    deps = [(t.trip_id, t.dep[t.stations.index(XFER)])
            for t in trips if t.route_id == "V"]
    feasible, rejected = [], []
    for hid, ta in arrs:
        for vid, td in deps:
            gap = td - ta
            (feasible if MIN_TR <= gap <= MAX_TR_WAIT
             else rejected).append((hid, vid, gap))
    return feasible, rejected


def enumerate_columns(trips, graph):
    """Exhaustive DFS over the event DAG (the pool generator).
    Returns {signature: column dict}."""
    out = {}
    seen, stack = set(), []
    for node, _c in graph.entry_arcs(ORIGIN, READY, 0.0):
        stack.append((node, 0, ()))
    while stack:
        u, boards, legs = stack.pop()
        key = (u, boards, legs)
        if key in seen:
            continue
        seen.add(key)
        kind, ti, k = graph.node_info[u]
        if kind == "X" and legs and trips[ti].stations[k] == DEST:
            col = _cost(trips, legs)
            if col is not None:
                out[col["signature"]] = col
        for (v, _c, tag) in graph.adj[u]:
            b2, legs2 = boards, legs
            if tag == "board":
                b2 = boards + 1
                if b2 > 2:
                    continue
                _, ti2, k2 = graph.node_info[v]
                legs2 = legs + ((ti2, k2, None),)
            elif tag == "alight":
                _, ti2, k2 = graph.node_info[v]
                lt = legs[-1]
                legs2 = legs[:-1] + ((lt[0], lt[1], k2),)
            stack.append((v, b2, legs2))
    return out


def _cost(trips, legs):
    iv, waits, prev = 0.0, [], None
    for ti, bk, ak in legs:
        t = trips[ti]
        ready = READY if prev is None else prev
        gap = t.dep[bk] - ready
        if prev is not None and not (MIN_TR <= gap <= MAX_TR_WAIT):
            return None
        if gap < 0:
            return None
        waits.append(gap)
        iv += t.arr[ak] - t.dep[bk]
        prev = t.arr[ak]
    n_tr = len(legs) - 1
    cost = waits[0] + sum(waits[1:]) + iv + 3 * n_tr
    chain = ">".join([trips[legs[0][0]].trip_id]
                     + ["%s>%s" % (XFER, trips[ti].trip_id)
                        for ti, _b, _a in legs[1:]])
    return {"signature": "%s|07:28|%s|%s" % (ORIGIN, chain, DEST),
            "trips": [trips[ti].trip_id for ti, _b, _a in legs],
            "initial_wait": waits[0],
            "transfer_wait": sum(waits[1:]),
            "in_vehicle": iv, "n_transfers": n_tr, "cost": cost,
            "arrival": "07:%02d" % (prev - T0)}


def dp_best(trips, graph):
    pricer = SSTPricer(graph, CFG, max_transfers=1,
                       track_prev_service=True)
    cols = pricer.price_cohort(graph.entry_arcs(ORIGIN, READY, 0.0),
                               {DEST: 0.0}, {}, READY)
    best = cols[0]
    return {"cost": best["cost"], "trips": list(best["trip_seq"]),
            "arrival": "07:%02d" % (best["arr"] - T0)}
