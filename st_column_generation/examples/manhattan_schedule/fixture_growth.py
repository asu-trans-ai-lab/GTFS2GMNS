"""Section-14 growth experiment: fixed Manhattan grid, vary ONLY
service richness (headway h in {10,5,2}) and transfer depth J in
{0..3}.  Exact counting DP (no materialization).

Run:  python -m examples.manhattan_schedule.fixture_growth
"""

from collections import deque

from . import manhattan_core as M
from .manhattan_core import T0, READY, ORIGIN, DEST, CFG
from event_graph import EventGraph, TripSched

HORIZON = 60          # 07:30 - 08:30 service
J_MAX = 3


def timetable(h):
    def mk(tid, route, stations, t_start, run):
        times = tuple(t_start + run * i for i in range(len(stations)))
        tt = tuple(T0 + m for m in times)
        return TripSched(tid, route, "0", tuple(stations), tt, tt)
    trips = []
    k = 0
    t = 30
    while t < 30 + HORIZON:
        trips.append(mk("H%d" % k, "H",
                        ["N21", "N22", "N23", "N24"], t, 2))
        trips.append(mk("V%d" % k, "V",
                        ["N13", "N23", "N33", "N43"], t + 3, 2))
        k += 1
        t += h
    t = 33
    while t < 30 + HORIZON:
        trips.append(mk("X%d" % len([x for x in trips
                                     if x.route_id == "X"]), "X",
                        ["N21", "N43"], t, 10))
        t += 10
    return trips


def count(graph, J_max):
    n = graph.n_nodes
    indeg = [0] * n
    for u in range(n):
        for (v, _c, _t) in graph.adj[u]:
            indeg[v] += 1
    q = deque(u for u in range(n) if indeg[u] == 0)
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for (v, _c, _t) in graph.adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    rev = order[::-1]
    term = [False] * n
    for node, _arr in graph.station_exits.get(DEST, []):
        term[node] = True
    N = [[0] * n for _ in range(J_max + 1)]
    for u in rev:
        base = 1 if term[u] else 0
        for r in range(J_max + 1):
            acc = base
            for (v, _c, tag) in graph.adj[u]:
                if tag == "transfer":
                    if r >= 1:
                        acc += N[r - 1][v]
                else:
                    acc += N[r][v]
            N[r][u] = acc
    ent = graph.entry_arcs(ORIGIN, READY, 0.0)
    if not ent:
        return [0] * (J_max + 1)
    e = ent[0][0]
    return [N[r][e] for r in range(J_max + 1)]


def main():
    print("h(min)  |V^ev|  |A^ev|   K<=0   K<=1   K<=2   K<=3")
    prev = None
    for h in (10, 5, 2):
        trips = timetable(h)
        g = EventGraph(trips, CFG)
        ks = count(g, J_MAX)
        arcs = sum(len(a) for a in g.adj)
        print("%5d %7d %7d %6d %6d %6d %6d"
              % (h, g.n_nodes, arcs, *ks))
        assert all(ks[j] <= ks[j + 1] for j in range(J_MAX)), ks
        if prev is not None:
            assert ks[J_MAX] > prev, "richer service must grow K"
        prev = ks[J_MAX]
        assert ks[J_MAX] > arcs or h == 10, \
            "column space should exceed graph size as service densifies"
    print("[PASS] K grows monotonically with J and with service "
          "richness; |event graph| << K at dense headways")


if __name__ == "__main__":
    main()
