"""SST dynamic-programming pricing oracle (VRPLite lineage).

Re-architecture of the VRPLite kernel
(VRPLite-master/VersionPartB/cpp_source_code/AgentPlus/AgentPlus.cpp):

  VRPLite                                   here
  ---------------------------------------   --------------------------------
  lp_state_node_label_cost[p][i][t][w]      sparse label[(event, state)]
  CVRState carrying-state catalog (l.76+)   lazy passenger state
                                            (n_boardings, prev_service)
  movement transition (l.729):              priced arc relaxation; BPR
    label + arc_cost + to_node_cost           marginal cost injected on
    (multiplier prices in to_node_cost)       scheduled ride arcs
  waiting transition (l.762)                platform W->W chain arcs
  predecessor arrays -> trajectory          pred[(event,state)] backtrace
  one DP per vehicle, OpenMP parallel       one DP per cohort (parallel-
                                            izable across cohorts)
  subgradient multiplier update             REPLACED by fully corrective
                                            BPR restricted master

Passenger state (no carrying capacity, no denied boarding — locked
design): status is implicit in the event kind (W=waiting, B/A=onboard,
X=alighted); the explicit state is

    s = (n_boardings, prev_service)

with transition Gamma on the board arc only.  The boarding penalty is
charged on boardings after the first, so DP costs match the enumeration
convention n_transfers = boardings - 1 exactly.

Terminal costs that depend on final arrival time (schedule delay) are
applied at the destination exit — the VRPLite to_node_cost mechanism.
"""

import heapq


class SSTPricer:
    def __init__(self, graph, cfg, max_transfers=None,
                 track_prev_service=True):
        """graph: event_graph.EventGraph.  Builds the per-arc resource map
        (scheduled trip segment (ti, k) for ride arcs, else None).

        track_prev_service=False collapses the state to the transfer
        count alone (valid while no line-dependent transfer penalty is
        priced; keeps the lazy product small on regional graphs)."""
        self.g = graph
        self.cfg = cfg
        self.track_prev = track_prev_service
        self.max_boards = (max_transfers if max_transfers is not None
                           else cfg.get("max_transfers", 1)) + 1
        # arc -> resource key: ride arc leaving B(ti,k) covers segment
        # (ti, k); identified by the tail node's info + "ride" tag.
        self.arc_resource = []
        for u, arcs in enumerate(graph.adj):
            kind, ti, k = graph.node_info[u]
            row = []
            for (v, cost, tag) in arcs:
                row.append((ti, k) if tag == "ride" else None)
            self.arc_resource.append(row)

    def price_cohort(self, entries, dest_stations, marginal, tau,
                     terminal_cost=None, ban_transfer_stations=(),
                     ban_first_routes=()):
        """Forward DP over (event, state) labels.

        entries        [(node, base_cost)] from EventGraph.entry_arcs
        dest_stations  {station_name: egress_minutes}
        marginal       {(ti, k): BPR marginal cost} (missing -> 0)
        terminal_cost  optional f(arr_minute) added at the exit
                       (schedule delay etc.)
        Returns list of candidate columns, best first:
          dict(cost, arr, legs, n_tr, exit_station, state)
        one per distinct (exit station, n_boardings) — the natural
        multi-column output per pricing call.
        """
        g = self.g
        cfg = self.cfg
        bt = cfg["beta_transfer"]
        s0 = (0, "")
        dist = {}
        pred = {}
        pq = []
        for node, c0 in entries:
            key = (node, s0)
            if c0 < dist.get(key, float("inf")):
                dist[key] = c0
                pred[key] = None
                heapq.heappush(pq, (c0, node, s0))

        while pq:
            c, u, s = heapq.heappop(pq)
            if c > dist.get((u, s), float("inf")):
                continue
            arcs = g.adj[u]
            res_row = self.arc_resource[u]
            for ai, (v, w, tag) in enumerate(arcs):
                s2 = s
                w2 = w
                if tag == "transfer" and ban_transfer_stations:
                    # head of a transfer arc is W(ti, k); its station is
                    # the banned-transfer-location check (diversified
                    # pricing, Stage A)
                    _, ti_t, k_t = g.node_info[v]
                    if g.trips[ti_t].stations[k_t] \
                            in ban_transfer_stations:
                        continue
                if tag == "board":
                    n_b = s[0] + 1
                    if n_b > self.max_boards:
                        continue
                    _, ti, _k = g.node_info[v]
                    if (s[0] == 0 and ban_first_routes
                            and g.trips[ti].route_id in ban_first_routes):
                        continue
                    s2 = (n_b, g.trips[ti].route_id
                          if self.track_prev else "")
                    # graph pre-charges beta_transfer on every board arc;
                    # first boarding is free under the n_tr = boards-1
                    # convention, so rebate it via the state machine
                    if s[0] == 0:
                        w2 = w - bt
                elif res_row[ai] is not None:
                    w2 = w + marginal.get(res_row[ai], 0.0)
                key = (v, s2)
                nc = c + w2
                if nc < dist.get(key, float("inf")) - 1e-15:
                    dist[key] = nc
                    # pred carries the arc metadata (tag + resource) so
                    # every projection is accumulated during recovery,
                    # never reconstructed afterward
                    pred[key] = (u, s, tag, res_row[ai])
                    heapq.heappush(pq, (nc, v, s2))

        # collect exits: best per (station, n_boardings).
        # group labels by node once -- O(labels + exits)
        by_node = {}
        for (node, s_), c_ in dist.items():
            by_node.setdefault(node, []).append((s_, c_))
        out = {}
        for station, egr_min in dest_stations.items():
            for node, arr in self.g.station_exits.get(station, []):
                for s_, c_ in by_node.get(node, []):
                    total = c_ + cfg["beta_walk"] * egr_min
                    if terminal_cost is not None:
                        total += terminal_cost(arr + egr_min)
                    bucket = (station, s_[0])
                    if total < out.get(bucket, (float("inf"),))[0]:
                        out[bucket] = (total, arr + egr_min, (node, s_))
        cols = []
        for (station, n_b), (total, arr, s_key) in out.items():
            rec = self._recover(pred, s_key)
            rec.update({"cost": total, "arr": arr, "n_tr": n_b - 1,
                        "exit_station": station, "state": s_key[1],
                        "exit_key": s_key})
            cols.append(rec)
        cols.sort(key=lambda d: d["cost"])
        return cols

    def _recover(self, pred, key):
        """VRPLite trajectory recovery over (event, state) predecessors.

        All projections (legs, stop/route/trip sequences, waiting
        intervals, resource incidence, state sequence) are accumulated
        HERE, during recovery -- the synchronization invariant.
        """
        g = self.g
        nodes_states = []                 # (event node, state), travel order
        arcs = []                         # (tag, resource): arc i -> i+1
        k2 = key
        while True:
            nodes_states.append(k2)
            prev = pred.get(k2)
            if prev is None:
                break
            u, s, tag, res = prev
            arcs.append((tag, res))
            k2 = (u, s)
        nodes_states.reverse()
        arcs.reverse()                    # arcs[i]: element i -> i+1

        legs = []
        resources = [res for (_tag, res) in arcs if res is not None]
        event_seq = [nd for nd, _s in nodes_states]
        state_seq = [s for _nd, s in nodes_states]
        open_board = None
        for i, (nd, _st) in enumerate(nodes_states):
            kind, ti, k = g.node_info[nd]
            if kind == "B" and i > 0 and \
                    g.node_info[nodes_states[i - 1][0]][0] == "W":
                open_board = (ti, k)
            elif kind == "X" and open_board is not None \
                    and open_board[0] == ti:
                legs.append((ti, open_board[1], k))
                open_board = None

        # projections derived from legs against the SAME trip objects
        routes, trips_seq, stops_b, stops_a = [], [], [], []
        board_times, alight_times = [], []
        for ti, bk, ak in legs:
            t = g.trips[ti]
            routes.append(t.route_id)
            trips_seq.append(t.trip_id)
            stops_b.append(t.stations[bk])
            stops_a.append(t.stations[ak])
            board_times.append(t.dep[bk])
            alight_times.append(t.arr[ak])
        return {"legs": tuple(legs), "resources": tuple(resources),
                "event_seq": tuple(event_seq),
                "state_seq": tuple(state_seq),
                "route_seq": tuple(routes), "trip_seq": tuple(trips_seq),
                "board_stops": tuple(stops_b),
                "alight_stops": tuple(stops_a),
                "board_times": tuple(board_times),
                "alight_times": tuple(alight_times)}
