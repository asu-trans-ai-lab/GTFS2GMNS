"""Multi-agency integrated event graph (Releases 0.2 / 0.3).

Pass 1  per-feed scheduled trips (namespaced), service day selected per
        feed: calendar.txt weekday flags if present, else the dominant
        weekday service_id set in calendar_dates.txt.
Pass 2  interagency transfer stations by SPATIAL CLUSTERING: stops
        within ~80 m union into one station cluster; the cluster name
        becomes the EventGraph station key, so the certified same-name
        transfer logic works unchanged across agencies.

Route types included: 0 tram, 1 metro, 2 rail, 3 bus.
"""

import math
import os
from collections import defaultdict

import pandas as pd

from event_graph import EventGraph, TripSched

CLUSTER_M = 80.0


def _hms(t):
    try:
        h, m, s = str(t).split(":")
        return int(h) * 60 + int(m) + int(s) / 60.0
    except Exception:
        return None


def pick_services(feed_dir, weekday_col="wednesday"):
    cal_p = os.path.join(feed_dir, "calendar.txt")
    if os.path.exists(cal_p):
        cal = pd.read_csv(cal_p, dtype=str)
        if weekday_col in cal.columns:
            svc = set(cal[cal[weekday_col] == "1"]["service_id"])
            if svc:
                return svc
    cd_p = os.path.join(feed_dir, "calendar_dates.txt")
    if os.path.exists(cd_p):
        cd = pd.read_csv(cd_p, dtype=str)
        cd = cd[cd["exception_type"] == "1"]
        cd["dow"] = pd.to_datetime(cd["date"]).dt.dayofweek
        wk = cd[cd["dow"] < 5]
        if len(wk):
            top_date = wk.groupby("date")["service_id"].count() \
                         .idxmax()
            return set(wk[wk["date"] == top_date]["service_id"])
    return None


def load_feed_trips(feed_dir, feed_ns, w0, w1, route_types):
    routes = pd.read_csv(os.path.join(feed_dir, "routes.txt"),
                         dtype=str)
    rt = dict(zip(routes["route_id"], routes["route_type"]))
    trips = pd.read_csv(os.path.join(feed_dir, "trips.txt"),
                        dtype=str)
    svc = pick_services(feed_dir)
    if svc is not None:
        trips = trips[trips["service_id"].isin(svc)]
    trips = trips[trips["route_id"].map(rt).isin(route_types)]
    if "direction_id" not in trips.columns:
        trips = trips.copy()
        trips["direction_id"] = "0"
    stops = pd.read_csv(os.path.join(feed_dir, "stops.txt"),
                        dtype=str)
    st = pd.read_csv(os.path.join(feed_dir, "stop_times.txt"),
                     dtype=str, usecols=["trip_id", "arrival_time",
                                         "departure_time", "stop_id",
                                         "stop_sequence"])
    st = st.merge(trips[["trip_id", "route_id", "direction_id"]],
                  on="trip_id")
    st["dep"] = st["departure_time"].map(_hms)
    st["arr"] = st["arrival_time"].map(_hms)
    st = st.dropna(subset=["dep", "arr"])
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    coords = {r["stop_id"]: (float(r["stop_lat"]),
                             float(r["stop_lon"]))
              for _i, r in stops.iterrows()
              if r["stop_lat"] and r["stop_lon"]}
    out = []
    for trip_id, gdf in st.groupby("trip_id"):
        gdf = gdf.sort_values("stop_sequence")
        d = gdf["dep"].to_numpy()
        if d.min() > w1 or d.max() < w0:
            continue
        if (pd.Series(d).diff().dropna() < 0).any():
            continue
        out.append((feed_ns, trip_id, gdf["route_id"].iloc[0],
                    gdf["direction_id"].iloc[0],
                    list(gdf["stop_id"]), list(gdf["arr"]),
                    list(gdf["dep"])))
    return out, coords


def cluster_stations(all_coords):
    """Grid-hash union of stops within CLUSTER_M meters.
    Returns {(feed, stop_id): cluster_name}."""
    cell = CLUSTER_M / 111000.0
    grid = defaultdict(list)
    keys = list(all_coords)
    for key in keys:
        lat, lon = all_coords[key]
        grid[(int(lat / cell), int(lon / cell))].append(key)
    parent = {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for (gi, gj), members in grid.items():
        cands = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                cands.extend(grid.get((gi + di, gj + dj), []))
        for a in members:
            la, lo = all_coords[a]
            for b in cands:
                if a >= b:
                    continue
                lb, lob = all_coords[b]
                dx = (lo - lob) * 87000.0
                dy = (la - lb) * 111000.0
                if dx * dx + dy * dy <= CLUSTER_M ** 2:
                    union(a, b)
    return {k: "C_" + str(find(k)) for k in keys}


def build_multi_graph(gtfs_root, feeds, w0, w1, cfg,
                      route_types=("0", "1", "2", "3")):
    all_trips_raw = []
    all_coords = {}
    for feed in feeds:
        p = os.path.join(gtfs_root, feed)
        tr, coords = load_feed_trips(p, feed.split("_")[0], w0, w1,
                                     set(route_types))
        all_trips_raw.extend(tr)
        for sid, c in coords.items():
            all_coords[(feed, sid)] = c
        print("  feed %-28s trips-in-window %6d" % (feed[:28],
                                                    len(tr)))
    def f_ns_feed(ns, feeds_):
        for f in feeds_:
            if f.split("_")[0] == ns:
                return f
        return ns

    # cluster stop ids used by trips only
    used = {(f_ns_feed(feed_ns, feeds), sid)
            for feed_ns, _t, _r, _d, sids, _a, _dd in all_trips_raw
            for sid in sids}
    used = {k for k in all_coords if k in used} or set(all_coords)
    cluster = cluster_stations({k: all_coords[k] for k in used})
    trip_objs = []
    for feed_ns, trip_id, route, dd, sids, arr, dep in all_trips_raw:
        feed_full = f_ns_feed(feed_ns, feeds)
        stations = tuple(cluster.get((feed_full, s),
                                     feed_ns + ":" + s)
                         for s in sids)
        trip_objs.append(TripSched(
            "%s:%s" % (feed_ns, trip_id),
            "%s:%s" % (feed_ns, route), dd, stations,
            tuple(arr), tuple(dep)))
    print("total trips %d | building event graph..."
          % len(trip_objs))
    g = EventGraph(trip_objs, cfg)
    return g, trip_objs, cluster
