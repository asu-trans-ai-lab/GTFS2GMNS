"""Configuration for the controlled single-OD schedule-based prototype.

Design-doc Step 13: one OD, three physical alternatives (direct express,
direct local, one-transfer route), two-hour peak, peaked Gaussian demand.
All times are minutes after midnight unless noted.
"""

BASE_CONFIG = {
    # passenger departure (cohort) window: 07:00 - 09:00
    "t_start": 420,
    "t_end": 540,
    # timetable horizon: trips may depart 06:40 - 10:00
    "service_start": 400,
    "service_end": 600,
    "bin_size": 1,            # minutes per link-time occupancy bin

    "departure_interval": 5,  # cohort spacing Delta in minutes (swept in Exp 1)
    "headway_scale": 1.0,     # multiplies all base headways (swept in Exp 1)
    "max_transfers": 1,       # 0 or 1 (swept in Exp 1)

    # itinerary feasibility limits (minutes)
    "max_origin_wait": 20.0,
    "max_transfer_wait": 20.0,
    "max_total_time": 90.0,

    # walking times (minutes)
    "access_walk": 2.0,
    "egress_walk": 2.0,
    "transfer_walk": 3.0,

    # generalized-cost coefficients (minute-equivalents)
    "beta_iv": 1.0,
    "beta_wait": 2.0,
    "beta_walk": 2.0,
    "beta_transfer": 5.0,
    "beta_early": 0.5,        # per minute of early arrival
    "beta_late": 2.0,         # per minute of late arrival
    "arrival_target_offset": 40.0,  # desired arrival = cohort departure + offset

    # demand profile d_tau = peak_rate * Delta * exp(-(tau - tau_p)^2 / (2 sigma^2))
    "demand_peak_rate": 2.0,  # passengers per minute at the peak
    "demand_peak_time": 465,  # 07:45
    "demand_sigma": 25.0,

    # effective-rank tolerances (relative Frobenius residual)
    "rank_eps": [0.01, 0.05],
}

# Physical lines.  seg_times are per-segment run times in minutes; a trip's
# stop-departure profile is the cumulative sum.  offset shifts the first
# departure relative to service_start.
LINES = {
    # direct express: O -> M1 -> D, 25 min in-vehicle, 15-min headway
    "E": {"desc": "direct express", "stops": ["O", "M1", "D"],
          "seg_times": [12.0, 13.0], "headway": 15.0, "offset": 0.0},
    # direct local: O -> S1..S6 -> D, 40 min in-vehicle, 5-min headway
    "L": {"desc": "direct local", "stops": ["O", "S1", "S2", "S3", "S4", "S5", "S6", "D"],
          "seg_times": [6.0, 6.0, 6.0, 5.0, 6.0, 5.0, 6.0], "headway": 5.0, "offset": 2.0},
    # feeder to transfer station X, 15 min in-vehicle, 7-min headway
    "B": {"desc": "feeder to X", "stops": ["O", "B1", "B2", "X"],
          "seg_times": [5.0, 5.0, 5.0], "headway": 7.0, "offset": 3.0},
    # connector from X to D, 12 min in-vehicle, 10-min headway
    "C": {"desc": "connector from X", "stops": ["X", "C1", "C2", "D"],
          "seg_times": [4.0, 4.0, 4.0], "headway": 10.0, "offset": 5.0},
}

# The three physical alternatives (route skeletons / itinerary families).
# Each entry: tuple of line legs in travel order.
ALTERNATIVES = [
    ("E",),
    ("L",),
    ("B", "C"),   # transfer at X
]


def family_key(legs):
    """Family = physical route skeleton, e.g. 'E', 'L', 'B>X>C'."""
    lines = [line for line, _trip in legs]
    if lines == ["B", "C"]:
        return "B>X>C"
    return ">".join(lines)
