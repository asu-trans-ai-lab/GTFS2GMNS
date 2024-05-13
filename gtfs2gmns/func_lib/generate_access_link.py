# -*- coding:utf-8 -*-
##############################################################
# Created Date: Sunday, February 18th 2024
# Contact Info: luoxiangyong01@gmail.com
# Author/Copyright: Mr. Xiangyong Luo
##############################################################

# Date: Feb 25, 2024
# Fang Tang, tangfang@gmail.com

# This code is to fix some connectivity issues based on released gtfs2gmns 0.1.8


import pandas as pd
from shapely import Point, LineString, Polygon, geometry, MultiPoint
from pyufunc import gmns_geo, calc_distance_on_unit_sphere, func_time, find_k_nearest_points


@func_time
def generate_access_link(zone_path: str,
                         node_path: str,
                         radius: float,
                         k_closest: int = 0) -> pd.DataFrame:

    # read zone and node data
    df_zone = pd.read_csv(zone_path)
    df_node = pd.read_csv(node_path)

    # check required columns for zone data and node data
    zone_required_columns = ['zone_id', 'x_coord', 'y_coord']
    node_required_columns = ['node_id', 'x_coord', 'y_coord']
    if not set(zone_required_columns).issubset(df_zone.columns):
        raise ValueError(f"zone data should contain {zone_required_columns}")

    if not set(node_required_columns).issubset(df_node.columns):
        raise ValueError(f"node data should contain {node_required_columns}")

    # filter out the real nodes
    df_node_real = df_node[df_node['directed_service_id'].isnull()]

    # Create a dictionary for the zone
    zone_dict = {}
    for i in range(len(df_zone)):
        zone_id = df_zone.loc[i]['zone_id']
        x_coord = df_zone.loc[i]['x_coord']
        y_coord = df_zone.loc[i]['y_coord']
        zone_dict[zone_id] = {"geometry": geometry.Point(x_coord, y_coord),
                              "access_points": [],
                              "access_links": []}

    # Create a dictionary for the nodes
    node_dict = {}
    for i in range(len(df_node_real)):
        node_id = df_node_real.loc[i]['node_id']
        x_coord = df_node_real.loc[i]['x_coord']
        y_coord = df_node_real.loc[i]['y_coord']
        node_dict[node_id] = geometry.Point(x_coord, y_coord)

    # create multipoint for the nodes
    nodes_multipoints = MultiPoint([node_dict[node_id] for node_id in node_dict])

    # create zone multipoints
    zone_multipoints = MultiPoint([zone_dict[zone_id]["geometry"] for zone_id in zone_dict])

    # find the closest node to each zone
    zone_access_points = find_k_nearest_points(zone_multipoints, nodes_multipoints, radius, k_closest)

    # Create a mapping from Point to id
    zone_dict_reversed = {v['geometry']: k for k, v in zone_dict.items()}
    node_dict_reversed = {v: k for k, v in node_dict.items()}

    access_links = []
    # create access links
    for zone_center in zone_access_points:
        if zone_access_points[zone_center]:
            for node_id in zone_access_points[zone_center]:

                # create zone and node id from the mapping
                zone_id_i = zone_dict_reversed[zone_center]
                node_id_i = node_dict_reversed[node_id]

                access_links.append(
                    gmns_geo.Link(
                        id=f"{zone_id_i}_{node_id_i}",
                        from_node_id=zone_id_i,
                        to_node_id=node_id_i,
                        length=calc_distance_on_unit_sphere(zone_center, node_id, "meter"),
                        lanes=1,
                        free_speed=-1,
                        capacity=-1,
                        allowed_uses='auto',
                        geometry=LineString([zone_center, node_id])
                    )
                )

    return pd.DataFrame([link.as_dict() for link in access_links])
