"""Nonlinear generalized column generation for BPR-based assignment.

Loop:  restricted Beckmann master (Frank-Wolfe)
    -> marginal resource costs t_ex(v)
    -> pricing oracle per cohort (exact argmin over the full column space)
    -> insert negative-reduced-cost columns
    -> repeat until min_c min_q [C_q(v) - pi_c] >= -eps.

The pricing oracle is supplied by the caller: for Experiment 0 it is an
exact argmin over the enumerable universe; for the regional model it is
the time-dependent shortest path / SST forward DP on the event graph.
"""

import numpy as np

import restricted_bpr_master as master


def run(universe_B, universe_g, universe_cohort, demands, bpr,
        init_mask, pricing_eps=1e-6, master_tol=1e-9,
        max_rounds=50, master_max_iter=4000, log=print):
    """CG where the full space is enumerable (Experiment 0 setting).

    universe_*  full column space (B sparse, g fixed costs, cohort ids
                sorted ascending); init_mask selects the starting pool.
    Returns (result dict of final master, pool_mask, history).
    """
    n = universe_B.shape[1]
    pool = init_mask.copy()
    u_starts = master._group_pointers(universe_cohort)
    history = []
    res = None
    x_warm = None
    for rnd in range(1, max_rounds + 1):
        cols = np.flatnonzero(pool)
        B = universe_B[:, cols]
        g = universe_g[cols]
        cid = universe_cohort[cols]
        x0 = None
        if x_warm is not None:
            x0 = np.zeros(len(cols))
            common = np.isin(cols, x_warm[0])
            lookup = {c: xv for c, xv in zip(x_warm[0], x_warm[1])}
            x0[common] = [lookup[c] for c in cols[common]]
            # repair conservation per cohort (new columns start at 0)
            starts = master._group_pointers(cid)
            sums = np.add.reduceat(x0, starts)
            bad = np.abs(sums - demands) > 1e-12 * np.maximum(1, demands)
            if bad.any():
                x0 = None
        res = master.solve(B, g, cid, demands, bpr, x0=x0, tol=master_tol,
                           max_iter=master_max_iter)

        # exact pricing over the universe at current v
        u_costs = master.marginal_costs(universe_B, universe_g, bpr,
                                        res["v"])
        u_min = np.minimum.reduceat(u_costs, u_starts)
        rc = u_min - res["pi"]                  # per-cohort reduced cost
        worst = float(rc.min())
        # columns achieving the universe minimum, not yet pooled
        idx_min = np.minimum.reduceat(
            np.where(u_costs <= np.repeat(
                u_min, np.diff(np.r_[u_starts, n])) + 1e-15,
                np.arange(n), n), u_starts)
        new_cols = idx_min[(rc < -pricing_eps) & (~pool[idx_min])]
        history.append({"round": rnd, "pool_size": int(pool.sum()),
                        "master_obj": res["obj"], "master_gap": res["gap"],
                        "min_reduced_cost": worst,
                        "n_new_columns": len(new_cols)})
        log("CG round %2d | pool %5d | obj %.6f | gap %.2e | "
            "min rc %+.3e | +%d cols"
            % (rnd, pool.sum(), res["obj"], res["gap"], worst,
               len(new_cols)))
        if len(new_cols) == 0 and worst >= -pricing_eps:
            break
        pool[new_cols] = True
        x_warm = (cols, res["x"])
    return res, pool, history
