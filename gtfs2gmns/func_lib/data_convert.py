# -*- coding:utf-8 -*-
##############################################################
# Created Date: Wednesday, November 16th 2022
# Contact Info: luoxiangyong01@gmail.com
# Author/Copyright: Mr. Xiangyong Luo
##############################################################

import math
import datetime
import numpy as np
import pandas as pd


def stop_sequence_label(trip_stop_time_df: pd.DataFrame) -> pd.DataFrame:
    trip_stop_time_df = trip_stop_time_df.sort_values(by=['stop_sequence'])
    trip_stop_time_df['stop_sequence_label'] = ';'.join(
        np.array(trip_stop_time_df.stop_sequence).astype(str))
    return trip_stop_time_df


def split_ignore_separators_in_quoted(s: str, separator: str = ',', quote_mark: str = '"') -> list:
    result = []
    quoted = False
    current = ''
    for i in range(len(s)):
        if quoted:
            current += s[i]
            if s[i] == quote_mark:
                quoted = False
            continue
        if s[i] == separator:
            result.append(current.strip())
            current = ''
        else:
            current += s[i]
            if s[i] == quote_mark:
                quoted = True
    result.append(current)
    return result


def determine_terminal_flag(trip_stop_time_df: pd.DataFrame) -> pd.DataFrame:
    trip_stop_time_df.stop_sequence = trip_stop_time_df.stop_sequence.astype(
        'int32')
    start_stop_seq = int(trip_stop_time_df.stop_sequence.min())
    end_stop_seq = int(trip_stop_time_df.stop_sequence.max())

    #  convert string to integer
    trip_stop_time_df['terminal_flag'] = \
        ((trip_stop_time_df.stop_sequence == start_stop_seq) |
         (trip_stop_time_df.stop_sequence == end_stop_seq)).astype('int32')
    return trip_stop_time_df


def allowed_use_function(route_type: str) -> str:
    #  convert route type to node type on service network: 0:tram, 1:metro, 2:rail, 3:bus
    allowed_use_dict = {0: "w_bus_only;w_bus_metro;d_bus_only;d_bus_metro",
                        1: "w_metro_only;w_bus_metro;d_metro_only;d_bus_metro",
                        2: "w_rail_only;d_rail_only",
                        3: "w_bus_only;w_bus_metro;d_bus_only;d_bus_metro"}
    return allowed_use_dict.get(int(route_type), "")


def allowed_use_transferring(node_type_1: str, node_type_2: str) -> str:
    if (node_type_1 == 'stop') & (node_type_2 == 'stop'):
        return "w_bus_only;d_bus_only"
    elif (node_type_1 == 'stop') & (node_type_2 == 'metro_station'):
        return "w_bus_metro;d_bus_metro"
    elif (node_type_1 == 'metro_station') & (node_type_2 == 'stop'):
        return "w_bus_metro;d_bus_metro"
    elif (node_type_1 == 'metro_station') & (node_type_2 == 'metro_station'):
        return "w_metro_only;d_metro_only"
    elif (node_type_1 == 'rail_station') & (node_type_2 == 'rail_station'):
        return "w_rail_only;d_rail_only"
    else:
        return "closed"


def transferring_penalty(node_type_1: str, node_type_2: str) -> int:
    if (node_type_1 == 'stop') & (node_type_2 == 'stop'):
        return 99
    elif (node_type_1 == 'stop') & (node_type_2 == 'metro_station'):
        return 0
    elif (node_type_1 == 'metro_station') & (node_type_2 == 'stop'):
        return 0
    elif (node_type_1 == 'metro_station') & (node_type_2 == 'metro_station'):
        return 99
    elif (node_type_1 == 'rail_station') & (node_type_2 == 'rail_station'):
        return 99
    else:
        return 1000


def convert_route_type_to_node_type_p(route_type: str) -> str:
    #  convert route type to node type on physical network: 0:tram, 1:metro, 2:rail, 3:bus
    node_type_dict = {0: 'stop', 1: 'metro_station', 2: 'rail_station', 3: 'stop'}
    return node_type_dict.get(int(route_type), "")


def convert_route_type_to_node_type_s(route_type: str) -> str:
    #  convert route type to node type on service network: 0:tram, 1:metro, 2:rail, 3:bus
    node_type_dict = {0: "tram_service_nide", 1: "metro_service_node", 2: "rail_service_node", 3: "bus_service_node"}
    return node_type_dict.get(int(route_type), "")


def convert_route_type_to_link_type(route_type: str) -> str:
    #  convert route type to node type on service network
    route_type_dict = {0: 'tram', 1: 'metro', 2: 'rail', 3: 'bus'}
    return route_type_dict.get(int(route_type), '')


# WGS84 transfer coordinate system to distance(mile) #xy
def calculate_distance_from_geometry(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6371
    d_latitude = (lat2 - lat1) * math.pi / 180.0
    d_longitude = (lon2 - lon1) * math.pi / 180.0

    a = math.sin(d_latitude / 2) * math.sin(d_latitude / 2) + math.cos(lat1 * math.pi / 180.0) * math.cos(
        lat2 * math.pi / 180.0) * math.sin(d_longitude / 2) * math.sin(d_longitude / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # distance = radius * c * 1000 / 1609.34  # mile
    distance = radius * c * 1000  # meter
    return distance


def hhmm_to_minutes(time_period_1: str) -> list:
    from_time_1 = datetime.time(int(time_period_1[:2]), int(time_period_1[2:4]))
    to_time_1 = datetime.time(int(time_period_1[-4:-2]), int(time_period_1[-2:]))

    from_time_min_1 = from_time_1.hour * 60 + from_time_1.minute
    to_time_min_1 = to_time_1.hour * 60 + to_time_1.minute

    return [from_time_min_1, to_time_min_1]
