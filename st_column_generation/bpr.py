"""BPR congestion functions, Beckmann potential, marginal costs.

Locked design (2026-07-17): C_r is a congestion SCALE parameter, never a
hard capacity.  The flow-dependent part of a resource's cost is the BPR
add-on only,

    t_ex_r(v) = omega_r * t0_r * alpha_r * (v / C_r)^beta_r ,

so the scheduled in-vehicle time stays in the column's fixed cost
g_fixed and is not double counted.  The Beckmann potential of the add-on,

    Phi(v) = sum_r omega_r * t0_r * alpha_r / (beta_r + 1)
                 * v^(beta_r+1) / C_r^beta_r ,

is smooth and convex; d Phi / d v_r = t_ex_r(v_r).
"""

import numpy as np


class BPRResources:
    """Vectorized BPR add-on over a set of resources r (e.g. scheduled
    trip segments)."""

    def __init__(self, t0, C, alpha=0.15, beta=4.0, omega=1.0):
        self.t0 = np.asarray(t0, dtype=float)
        self.C = np.asarray(C, dtype=float)
        self.alpha = alpha * np.ones_like(self.t0)
        self.beta = beta * np.ones_like(self.t0)
        self.omega = omega * np.ones_like(self.t0)
        self._k = self.omega * self.t0 * self.alpha / self.C ** self.beta

    def excess_time(self, v):
        """t_ex_r(v): marginal congestion cost per resource."""
        return self._k * np.maximum(v, 0.0) ** self.beta

    def potential(self, v):
        """Phi(v): Beckmann integral of the add-on."""
        vv = np.maximum(v, 0.0)
        return float(np.sum(self._k / (self.beta + 1.0)
                            * vv ** (self.beta + 1.0)))

    def potential_derivative_along(self, v, dv):
        """d/da Phi(v + a*dv) at given (v, dv): dot(t_ex(v), dv)."""
        return float(np.dot(self.excess_time(v), dv))
