"""Restricted BPR master: smooth convex Beckmann problem on a column pool.

    min_{x >= 0}  F(x) = g_fixed . x + Phi(B x)
    s.t.          sum_{q in pool_c} x_q = d_c        for every cohort c

Solved by Frank-Wolfe with exact (bisection) line search: the per-cohort
linearized subproblem is an argmin over the cohort's pooled columns, the
combined direction is the all-or-nothing shift, and the relative gap

    gap = [ C(v).x - sum_c d_c * min_q C_q(v) ] / F(x)

is the in-pool KKT residual.  Columns must be grouped: cohort_ids sorted
ascending so np.minimum.reduceat works per group.
"""

import numpy as np


def _group_pointers(cohort_ids):
    """cohort_ids sorted ascending -> (group_starts, group_index_of_col)."""
    starts = np.flatnonzero(np.r_[True, cohort_ids[1:] != cohort_ids[:-1]])
    return starts


def marginal_costs(B, g_fixed, bpr, v):
    """C_q(v) = g_fixed_q + sum_r delta_rq * t_ex_r(v_r)."""
    return g_fixed + B.T @ bpr.excess_time(v)


def solve(B, g_fixed, cohort_ids, demands, bpr, x0=None,
          tol=1e-8, max_iter=500):
    """Frank-Wolfe on the pooled columns.

    B          sparse resources x columns
    cohort_ids per-column cohort index, sorted ascending
    demands    per-cohort demand, aligned with the sorted unique cohorts
    Returns dict with x, v, obj, gap, iters, pi (per-cohort min cost).
    """
    n_cols = B.shape[1]
    starts = _group_pointers(cohort_ids)
    n_groups = len(starts)
    assert len(demands) == n_groups

    if x0 is None:
        # all demand on the first column of each cohort
        x = np.zeros(n_cols)
        x[starts] = demands
    else:
        x = x0.astype(float).copy()

    v = B @ x
    gap = np.inf
    it = 0
    for it in range(1, max_iter + 1):
        costs = marginal_costs(B, g_fixed, bpr, v)
        grp_min = np.minimum.reduceat(costs, starts)
        # AON target: per group, put demand on the argmin column
        # (argmin via where cost equals group min, first occurrence)
        is_min = costs <= np.repeat(grp_min, np.diff(
            np.r_[starts, n_cols])) + 1e-15
        first_min = np.zeros(n_cols, dtype=bool)
        # first minimal column of each group
        idx_min = np.minimum.reduceat(
            np.where(is_min, np.arange(n_cols), n_cols), starts)
        first_min[idx_min] = True
        y = np.zeros(n_cols)
        y[idx_min] = demands

        obj = float(np.dot(g_fixed, x)) + bpr.potential(v)
        gap_abs = float(np.dot(costs, x) - np.dot(grp_min, demands))
        gap = gap_abs / max(1.0, abs(obj))
        if gap <= tol:
            break

        d = y - x
        dv = B @ d
        # exact line search: phi'(a) = g.d + t_ex(v+a dv).dv, convex in a
        gd = float(np.dot(g_fixed, d))
        lo, hi = 0.0, 1.0
        if gd + bpr.potential_derivative_along(v + dv, dv) <= 0.0:
            a = 1.0
        else:
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if gd + bpr.potential_derivative_along(v + mid * dv, dv) > 0:
                    hi = mid
                else:
                    lo = mid
            a = 0.5 * (lo + hi)
        if a <= 0.0:
            break
        x = x + a * d
        v = v + a * dv

    costs = marginal_costs(B, g_fixed, bpr, v)
    pi = np.minimum.reduceat(costs, starts)
    obj = float(np.dot(g_fixed, x)) + bpr.potential(v)
    return {"x": x, "v": v, "obj": obj, "gap": gap, "iters": it, "pi": pi,
            "costs": costs, "starts": starts}
