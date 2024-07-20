# -*- coding:utf-8 -*-
##############################################################
# Created Date: Tuesday, September 19th 2023
# Contact Info: luoxiangyong01@gmail.com
# Author/Copyright: Mr. Xiangyong Luo
##############################################################

import datetime
import os

import pandas as pd

from gtfs2gmns.func_lib.data_convert import (determine_terminal_flag,
                                             stop_sequence_label)
from gtfs2gmns.utility_lib import validate_time_period
from pyufunc import func_running_time, path2linux, check_files_in_dir


@func_running_time
def read_gtfs_single(gtfs_dir_single: str,
                     time_period: str,
                     required_files: list = ['agency.txt', 'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt']) -> dict:
    """read gtfs data from a single folder

    Args:
        gtfs_dir_single (str): the path of a single gtfs folder

    Raises:
        Exception: "Error: Required files not exist in the folder!"
        Exception: "Error: no trips are within the provided time window, please check/change the time window from input."

    Returns:
        dict: {"agency": agency_df,
               "stop": stop_df,
               "route": route_df,
               "trip": trip_df,
               "trip_route": trip_route_df,
               "stop_time": stop_time_df,
               "directed_trip_route_stop_time": directed_trip_route_stop_time_df}
    """

    # Step 1: check if required files exist in the folder
    # required_files = ['agency.txt', 'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt']
    required_files_dict = {file: path2linux(os.path.join(gtfs_dir_single, file)) for file in required_files}

    print(f"Info: Checking if required files exist in the folder: \n    :{gtfs_dir_single}")

    # txt_files_from_folder_abspath = get_filenames_by_ext(gtfs_dir_single, file_ext=".txt")
    # if not check_files_existence(list(required_files_dict.values()), txt_files_from_folder_abspath):
    #     raise Exception("Error: Required files not exist in the folder!")

    if not check_files_in_dir(list(required_files_dict.values()), gtfs_dir_single):
        raise Exception("Error: Required files not exist in the folder!")

    # Step 2: Check and Format time period
    period_start_time, period_end_time = validate_time_period(time_period)

    # Step 3: read GTFS data
    # Step 3.1 read agency.txt
    print("     : Reading agency.txt...")
    agency_df = pd.read_csv(required_files_dict.get("agency.txt"), encoding='utf-8-sig')
    agency_name = agency_df['agency_name'][0]

    # Step 3.2 read stops.txt
    print("     : Reading stops.txt...")
    stop_df = pd.read_csv(required_files_dict.get("stops.txt"), encoding='utf-8-sig')
    stop_df["agency"] = agency_name
    # stop_df = stop_df[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]

    # Step 3.3 read routes.txt
    print("     : Reading routes.txt...")
    route_df = pd.read_csv(required_files_dict.get("routes.txt"), encoding='utf-8-sig')
    route_df["agency"] = agency_name
    # route_df = route_df[['route_id', 'route_short_name', 'route_long_name', 'route_type']]

    # Step 3.4 read trips.txt
    print("     : Reading trips.txt...")
    trip_df = pd.read_csv(required_files_dict.get("trips.txt"), encoding='utf-8-sig')
    trip_df["trip_id"] = trip_df["trip_id"].astype(str)
    trip_df["agency"] = agency_name

    # direction_id is mandatory field name here
    if 'direction_id' not in trip_df.columns.tolist():
        trip_df['direction_id'] = "0"

    # Deal with special issues of direction_id exists but all values are NaN
    try:
        trip_df['direction_id'] = trip_df.apply(lambda x: str(2 - int(x['direction_id'])), axis=1)
    except Exception:
        trip_df['direction_id'] = "0"

    # add a new column "directed_route_id"
    #  If trips on a route service opposite directions,distinguish directions using values 0 and 1.
    # revise the direction_id from 0,1 to 2,1
    # add a new field directed_route_id
    # deal with special issues of Agency 12 Fairfax CUE # Alicia, Nov 10:
    # route file has route id with quotes, e.g., '"green2"' while trip file does not have it, e.g.,'green2'
    directed_route_id = trip_df['route_id'].astype(str).str.cat(
        trip_df['direction_id'].astype(str), sep='.')
    trip_df['directed_route_id'] = directed_route_id

    # deal with special issues with route_id in two dataframes have different formats
    route_df["route_id"] = route_df["route_id"].astype(str)
    trip_df["route_id"] = trip_df["route_id"].astype(str)

    # make route_id in two dataframes have the same format
    if (route_df['route_id'][0][0] == '"') != (trip_df['route_id'][0][0] == '"'):
        if route_df['route_id'][0][0] == '"':
            route_df['route_id'] = route_df.apply(lambda x: x['route_id'].strip('"'), axis=1)
        else:
            trip_df['route_id'] = trip_df.apply(lambda x: x['route_id'].strip('"'), axis=1)

    # Left merge, as route is higher level planning than trips, len(trip_route_df)=len(trip_df)
    trip_route_df = pd.merge(trip_df, route_df, on='route_id')
    trip_route_df["trip_id"] = trip_route_df["trip_id"].astype(str)

    # Step 3.5 read stop_times.txt
    print("     : Reading stop_times.txt...\n")
    stop_time_df = pd.read_csv(required_files_dict.get("stop_times.txt"), encoding='utf-8-sig')
    stop_time_df["agency"] = agency_name

    # drop the stations without accurate arrival and departure time.
    # drop nan
    stop_time_df = stop_time_df.dropna(subset=['arrival_time'], how='any')

    # drop '' and ' '
    stop_time_df = stop_time_df[~stop_time_df.arrival_time.isin(['', ' '])]
    stop_time_df = stop_time_df[~stop_time_df.departure_time.isin(['', ' '])]

    def convert_time_str_to_HMS(time_str: str) -> datetime.datetime:

        # initialize flag for adding one day
        add_one_day = False

        # the string format of time is HH:MM:SS
        # Check whether the time correct format
        if len(time_str) not in {7, 8}:
            raise Exception(f"Error: input time {time_str}, standard time format: 04:20:22.")

        # check whether to add one day for the time 24:00:00
        if time_str >= '24:00:00':
            add_one_day = True

            # update the time string to 00 for a new day
            if len(time_str) == 7:
                time_str = "0" + time_str[1:]
            elif len(time_str) == 8:
                time_str = "00" + time_str[2:]
            else:
                raise Exception(f"Error: input time {time_str}, standard time format: 04:20:22.")

        # convert the time string to datetime format
        time_dt = datetime.datetime.strptime(time_str.strip(), '%H:%M:%S')

        # add one day if necessary
        if add_one_day:
            time_dt += datetime.timedelta(days=1)

        return time_dt

    stop_time_df['arrival_time'] = stop_time_df['arrival_time'].apply(
        lambda x: convert_time_str_to_HMS(x))
    stop_time_df['departure_time'] = stop_time_df['departure_time'].apply(
        lambda x: convert_time_str_to_HMS(x))

    iteration_group = stop_time_df.groupby(['trip_id'])
    # mark terminal flag for each stop. The terminals can only be determined at the level of trips

    input_list = []
    for trip_id, trip_stop_time_df in iteration_group:
        trip_stop_time_df = trip_stop_time_df.sort_values(
            by=['stop_sequence'])
        trip_stop_time_df = trip_stop_time_df.reset_index()

        # select only the trips within the provided time window
        mask1 = trip_stop_time_df.arrival_time.max() <= period_start_time
        mask2 = trip_stop_time_df.arrival_time.min() >= period_end_time
        if not mask1 and not mask2:
            input_list.append(trip_stop_time_df)

    # check if there is any trip within the provided time window
    # if not, raise an error
    if not input_list:
        raise Exception("Error: no trips are within the provided time window, please check/change the time window from input.")

    intermediate_output_list = list(map(determine_terminal_flag, input_list))
    output_list = list(map(stop_sequence_label, intermediate_output_list))

    stop_time_df_with_terminal = pd.concat(output_list, axis=0)
    stop_time_df_with_terminal["trip_id"] = stop_time_df_with_terminal["trip_id"].astype(str)

    # print("Info: merge the route information with trip information...")
    directed_trip_route_stop_time_df = pd.merge(
        trip_route_df, stop_time_df_with_terminal, on='trip_id')

    # print("Info: Data reading done.. \n")

    #  as trip is higher level planning than stop time scheduling, len(stop_time_df)>=len(trip_df)
    #  Each record of directed_trip_route_stop_time_df represents a space-time state of a vehicle
    # trip_id (different vehicles, e.g., train lines)
    # stop_id (spatial location of the vehicle)
    # arrival_time,departure_time (time index of the vehicle)

    directed_route_stop_id = directed_trip_route_stop_time_df['directed_route_id'].astype(
        str).str.cat(directed_trip_route_stop_time_df['stop_id'].astype(str), sep='.')

    # directed_route_stop_id is a unique id to identify the route, direction, and stop of a vehicle at a time point
    directed_trip_route_stop_time_df['directed_route_stop_id'] = directed_route_stop_id

    directed_trip_route_stop_time_df['stop_sequence'] = directed_trip_route_stop_time_df['stop_sequence'].astype(
        'int32')

    # two important concepts :
    # 1 directed_service_stop_id (directed_route_stop_id + stop sequence)
    directed_trip_route_stop_time_df['directed_service_stop_id'] = \
        directed_trip_route_stop_time_df.directed_route_stop_id.astype(str) + ':' + \
        directed_trip_route_stop_time_df.stop_sequence_label

    # 2. directed service id (directed_route_id + stop sequence) same directed route id might have different sequences
    directed_trip_route_stop_time_df['directed_service_id'] = \
        directed_trip_route_stop_time_df.directed_route_id.astype(str) + ':' + \
        directed_trip_route_stop_time_df.stop_sequence_label

    # attach stop name and geometry for stops
    directed_trip_route_stop_time_df = pd.merge(
        directed_trip_route_stop_time_df, stop_df, on='stop_id', suffixes=('_x1', '_y1'))
    directed_trip_route_stop_time_df['agency_name'] = agency_name

    return {"agency": agency_df, "stops": stop_df, "routes": route_df,
            "trips": trip_df, "trip_routes": trip_route_df,
            "stop_times": stop_time_df,
            "directed_trip_route_stop_time": directed_trip_route_stop_time_df}
