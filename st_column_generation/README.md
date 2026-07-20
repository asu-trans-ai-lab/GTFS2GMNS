# st_column_generation — schedule-based space-time column generation

This folder extends GTFS2GMNS beyond the frequency-based network
collapse of `gtfs2gmns.py` (representative trip, `lanes = n_trips`,
`wait = h/2`): it keeps **every scheduled trip** and generates
**space-time (ST) itinerary columns** — departure-time-resolved,
trip-specific paths with boardings, transfers, and waiting — by
dynamic-programming pricing over an event graph, inside a
column-generation / convex-master loop.

```
GTFS feeds ──► event graph (trip stop-visits as timed nodes)
           ──► SST-DP pricing oracle (per class, origin, departure)
           ──► restricted convex master (BPR congestion, Frank–Wolfe)
           ──► column pool  (mode, o, d, tau, trip legs, cost)
                └── repeated: master marginals re-price the graph
```

## Modules (Python reference implementation)

| file | role |
|---|---|
| `config.py` | base coefficients (walk/wait/in-vehicle/transfer) |
| `event_graph.py` | `TripSched` + `EventGraph`: timed board/ride/alight/wait arcs from stop_times |
| `multi_agency_graph.py` | multi-feed builder: per-feed service-day pick, 80 m spatial station clustering, namespaced ids |
| `state_transition.py` | space-time-**state** machine (transfer count, status, previous service) |
| `sst_pricing.py` | the SST-DP pricing oracle (label-correcting over `(event, state)`) |
| `bpr.py` | BPR congestion on trip-segment resources |
| `restricted_bpr_master.py` | Frank–Wolfe restricted master with exact line search |
| `column_generation.py` | the CG loop for small/controlled instances |
| `cpp_kernel/pricer_multi.cpp` | optional C++ accelerator (layered Dijkstra; see policy below) |

## Quick start (no GTFS data required)

```
cd st_column_generation
python -m examples.manhattan_schedule.self_demo
```

`examples/manhattan_schedule/` is a hand-checkable synthetic fixture
(4x4 grid, three routes, one timed transfer). The demo asserts hard-coded
golden values — exact feasible trip pairs, the 4-column pool with costs
{15, 19, 24, 24}, DP == exhaustive enumeration, zero duplicate or
infeasible columns — and is the permanent regression gate for every
change in this folder. `fixture_growth.py` and `fixture_assignment.py`
extend the same fixture to service-richness growth and a congested
two-column equilibrium with a pricing certificate.

## Python vs. C++ policy

The Python modules are the **reference implementation and the
certification oracle**; the C++ kernel is an **accelerator, ported
selectively and gated by exact agreement**:

1. *Compatibility first*: a C++ port must reproduce the Python oracle
   exactly on the fixtures before it is used
   (`pricer_multi` was certified at max |cpp − python| = 0.0 on the
   rail network, and its path-recovery variant at 0 mismatches over
   cost + trip sequences).
2. *Speed second*: only profiled hot spots are ported — the pricing
   oracle is C++ (one layered Dijkstra per class/origin/departure,
   ~10 ms per query on an 864k-node, 1.26M-arc, 20-feed event graph);
   masters, graph construction, audits, and everything experimental
   stay in Python.

Not everything should be ported: the Python reference is what makes
results checkable, and most modules are not on the critical path.

## Scale record (NVTA, 20 feeds)

The pipeline in this folder has been run at full regional scale
(Northern Virginia / DC, 20 GTFS feeds, 6,684 trips in a 06:30–09:00
window, 8 demand classes): 13.7M ST columns over 8.35M
(class, origin, destination, departure) cohorts in three CG rounds,
with a per-OD unserved-reason ledger (no-access / no-egress /
no-feasible-itinerary / partial-window) as the network audit
instrument. Those artifacts live with the research project, not in
this repository; this folder carries the reusable machinery and the
synthetic regression fixture.

## Requirements

numpy, scipy, pandas (see `requirements.txt`). The C++ kernel builds
with any C++11 compiler: `g++ -O3 -std=c++11 -static -o pricer_multi
cpp_kernel/pricer_multi.cpp`.
