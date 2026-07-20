"""Step 5.5 Module 4: schedule-expanded event graph + generalized-cost Dijkstra.

Every scheduled trip in the window is expanded into boarding, riding,
alighting and transfer-wait arcs.  Waiting is event-based: a passenger
reaching station s at time t can only board departure events with
dep >= t, and pays beta_wait per minute of the actual gap.  This replaces
the frequency-based 0.5*headway approximation of gtfs2gmns.

Node types per trip stop k (times from stop_times.txt):
  W(t,k)  on the platform, immediately before boarding trip t at stop k
  B(t,k)  on board, departing stop k
  A(t,k)  on board, arriving at stop k
  X(t,k)  just alighted at stop k

Arcs:
  W->B   board            cost beta_transfer   (charged per boarding;
                           reported cost subtracts one boarding so that
                           n_transfers = boardings - 1, as in the prototype)
  B->A   ride             beta_iv * run time
  A->B   stay on board    beta_iv * dwell
  A->X   alight           0
  W->W'  platform wait    beta_wait * gap (chain over the station's
                           departure events in time order)
  X->W   transfer         beta_walk*transfer_walk + beta_wait*residual wait
"""

import heapq
from bisect import bisect_left
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TripSched:
    trip_id: str
    route_id: str
    direction_id: str
    stations: tuple
    arr: tuple
    dep: tuple


def _hms_to_min(t):
    h, m, s = t.split(":")
    return int(h) * 60 + int(m) + int(s) / 60.0


def load_rail_trips(feed_path, service_id, t0, t1):
    """All trips of rail routes (route_type == 1) overlapping [t0, t1]."""
    import os
    routes = pd.read_csv(os.path.join(feed_path, "routes.txt"), dtype=str)
    rail_routes = set(routes[routes["route_type"] == "1"]["route_id"])
    trips = pd.read_csv(os.path.join(feed_path, "trips.txt"), dtype=str)
    trips = trips[(trips["service_id"] == service_id)
                  & trips["route_id"].isin(rail_routes)]
    stops = pd.read_csv(os.path.join(feed_path, "stops.txt"), dtype=str)
    name = dict(zip(stops["stop_id"], stops["stop_name"]))
    st = pd.read_csv(os.path.join(feed_path, "stop_times.txt"), dtype=str,
                     usecols=["trip_id", "arrival_time", "departure_time",
                              "stop_id", "stop_sequence"])
    st = st.merge(trips[["trip_id", "route_id", "direction_id"]], on="trip_id")
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    st["arr_min"] = st["arrival_time"].map(_hms_to_min)
    st["dep_min"] = st["departure_time"].map(_hms_to_min)

    out = []
    for trip_id, g in st.groupby("trip_id"):
        g = g.sort_values("stop_sequence")
        if g["dep_min"].min() > t1 or g["arr_min"].max() < t0:
            continue
        out.append(TripSched(
            trip_id, g["route_id"].iloc[0], g["direction_id"].iloc[0],
            tuple(name[s] for s in g["stop_id"]),
            tuple(g["arr_min"]), tuple(g["dep_min"])))
    out.sort(key=lambda t: t.dep[0])
    return out


class EventGraph:
    def __init__(self, trip_list, cfg):
        self.cfg = cfg
        self.trips = trip_list
        # node bookkeeping
        self.n_nodes = 0
        self.adj = []          # adj[u] = [(v, cost, arc_tag), ...]
        self.node_info = []    # (kind, trip_idx, k) for path extraction
        W, B, A, X = {}, {}, {}, {}

        def new_node(kind, ti, k):
            self.adj.append([])
            self.node_info.append((kind, ti, k))
            self.n_nodes += 1
            return self.n_nodes - 1

        bw, bi, bt, bwk = (cfg["beta_wait"], cfg["beta_iv"],
                           cfg["beta_transfer"], cfg["beta_walk"])
        twalk = cfg["transfer_walk"]

        for ti, t in enumerate(trip_list):
            n = len(t.stations)
            for k in range(n):
                if k < n - 1:
                    W[(ti, k)] = new_node("W", ti, k)
                    B[(ti, k)] = new_node("B", ti, k)
                if k > 0:
                    A[(ti, k)] = new_node("A", ti, k)
                    X[(ti, k)] = new_node("X", ti, k)
            for k in range(n - 1):
                # board / ride
                self.adj[W[(ti, k)]].append((B[(ti, k)], bt, "board"))
                self.adj[B[(ti, k)]].append(
                    (A[(ti, k + 1)], bi * (t.arr[k + 1] - t.dep[k]), "ride"))
                if 0 < k:
                    # arrived at k, stay on board through dwell
                    self.adj[A[(ti, k)]].append(
                        (B[(ti, k)], bi * (t.dep[k] - t.arr[k]), "stay"))
            for k in range(1, n):
                self.adj[A[(ti, k)]].append((X[(ti, k)], 0.0, "alight"))

        # station departure-event index: station -> sorted [(dep_time, Wnode)]
        self.station_deps = {}
        for ti, t in enumerate(trip_list):
            for k in range(len(t.stations) - 1):
                self.station_deps.setdefault(t.stations[k], []).append(
                    (t.dep[k], W[(ti, k)]))
        for s in self.station_deps:
            self.station_deps[s].sort()

        # platform waiting chains
        for s, evs in self.station_deps.items():
            for i in range(len(evs) - 1):
                gap = evs[i + 1][0] - evs[i][0]
                self.adj[evs[i][1]].append(
                    (evs[i + 1][1], bw * gap, "wait"))

        # transfer arcs: X(t,k) -> first departure at same station
        for ti, t in enumerate(trip_list):
            for k in range(1, len(t.stations)):
                s = t.stations[k]
                if s not in self.station_deps:
                    continue
                ready = t.arr[k] + twalk
                evs = self.station_deps[s]
                i = bisect_left(evs, (ready, -1))
                if i < len(evs):
                    dep_t, wnode = evs[i]
                    cost = bwk * twalk + bw * (dep_t - ready)
                    self.adj[X[(ti, k)]].append((wnode, cost, "transfer"))

        self.W, self.X = W, X
        # exits grouped by station for egress evaluation
        self.station_exits = {}
        for (ti, k), node in X.items():
            s = trip_list[ti].stations[k]
            self.station_exits.setdefault(s, []).append(
                (node, trip_list[ti].arr[k]))

    @property
    def stations(self):
        return set(self.station_deps) | set(self.station_exits)

    def entry_arcs(self, station, ready_time, base_cost):
        """Virtual-source arcs for a passenger reaching `station` at
        `ready_time` having already paid `base_cost` (access walk/drive)."""
        evs = self.station_deps.get(station)
        if not evs:
            return []
        i = bisect_left(evs, (ready_time, -1))
        if i >= len(evs):
            return []
        dep_t, wnode = evs[i]
        return [(wnode, base_cost
                 + self.cfg["beta_wait"] * (dep_t - ready_time))]

    def dijkstra(self, entries):
        """entries: [(node, initial_cost)].  Returns (dist, pred)."""
        INF = float("inf")
        dist = [INF] * self.n_nodes
        pred = [-1] * self.n_nodes
        pq = []
        for node, c in entries:
            if c < dist[node]:
                dist[node] = c
                heapq.heappush(pq, (c, node))
        while pq:
            c, u = heapq.heappop(pq)
            if c > dist[u]:
                continue
            for v, w, _tag in self.adj[u]:
                nc = c + w
                if nc < dist[v]:
                    dist[v] = nc
                    pred[v] = u
                    heapq.heappush(pq, (nc, v))
        return dist, pred

    def best_exit(self, dist, station):
        """(cost, arrival_minute, exit_node) of the cheapest alighting at
        the station, or None if unreachable."""
        best = None
        for node, arr in self.station_exits.get(station, []):
            if dist[node] < float("inf"):
                cand = (dist[node], arr, node)
                if best is None or cand < best:
                    best = cand
        return best

    def extract_legs(self, pred, exit_node):
        """Follow predecessors to the entry; return ((trip_idx, board_k,
        alight_k), ...) in travel order.

        The platform wait chain passes through W nodes of trips the
        passenger never boards, so a boarding is identified by the W->B
        arc (a B node whose predecessor is a W node), never by W-node
        identity alone.
        """
        chain = []
        node = exit_node
        while node != -1:
            chain.append(node)
            node = pred[node]
        chain.reverse()                      # travel order
        legs = []
        open_board = None
        for i, nd in enumerate(chain):
            kind, ti, k = self.node_info[nd]
            if kind == "B" and i > 0 \
                    and self.node_info[chain[i - 1]][0] == "W":
                open_board = (ti, k)         # boarded trip ti at stop k
            elif kind == "X" and open_board is not None \
                    and open_board[0] == ti:
                legs.append((ti, open_board[1], k))
                open_board = None
        return tuple(legs)
