# -*- coding:utf-8 -*-
##############################################################
# Created Date: Wednesday, November 16th 2022
# Contact Info: luoxiangyong01@gmail.com
# Author/Copyright: Mr. Xiangyong Luo
##############################################################

import os
import pandas as pd
from gtfs2gmns.func_lib.read_gtfs import read_gtfs_single
from gtfs2gmns.func_lib.gen_node_link import create_nodes, create_service_boarding_links, create_transferring_links
from gtfs2gmns.func_lib.generate_access_link import generate_access_link
from gtfs2gmns.utility_lib import (validate_time_period)
from pyufunc import path2linux, func_running_time, generate_unique_filename


class GTFS2GMNS:

    def __init__(self, gtfs_input_dir: str, time_period: str = '07:00:00_08:00:00',
                 date_period: list = [],
                 gtfs_output_dir: str = "", isSaveToCSV: bool = True):

        # TDD 1: check if the input folder exists
        if not os.path.isdir(gtfs_input_dir):
            raise ValueError('The input folder does not exist.')

        # TDD 2: if user specified output folder, check folder existence first,
        #        else, save results to same input folder
        if gtfs_output_dir:
            if not os.path.isdir(gtfs_output_dir):
                os.makedirs(gtfs_output_dir)
                print('Warning: The output folder does not exist. Create a new folder instead.')
            self.gtfs_output_dir = gtfs_output_dir
        else:
            self.gtfs_output_dir = gtfs_input_dir

        # TDD 3: check if the time period is valid
        self.time_period = time_period
        self.period_start_time, self.period_end_time = validate_time_period(time_period)

        self.gtfs_input_dir = gtfs_input_dir
        self.isSaveToCSV = isSaveToCSV

        # Default required files
        self.required_files = ['agency.txt', 'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt']

        # Initialize input folder list
        self.gtfs_folder_list = self.__get_gtfs_folder_list()

    @property
    def agency(self) -> pd.DataFrame:
        try:
            return self.__gfts_dict.get("agency")
        except Exception as e:
            print("Error: ", e)
            return "Need to load GTFS data first: gtfs2gmns.load_gtfs()"

    @property
    def calendar(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "calendar.txt")

    @property
    def calendar_dates(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "calendar_dates.txt")

    @property
    def fare_attributes(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "fare_attributes.txt")

    @property
    def fare_rules(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "fare_rules.txt")

    @property
    def feed_info(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "feed_info.txt")

    @property
    def frequencies(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "frequencies.txt")

    @property
    def routes(self) -> pd.DataFrame:
        try:
            return self.__gfts_dict.get("routes")
        except Exception:
            return "Need to load GTFS data first: gtfs2gmns.load_gtfs()"

    @property
    def route_ids(self) -> list:
        try:
            routes_df = self.__gfts_dict.get("routes")
            return routes_df.route_id.unique().tolist()
        except Exception:
            return "Need to load GTFS data first: gtfs2gmns.load_gtfs()"

    @property
    def shapes(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "shapes.txt")

    @property
    def stops(self) -> pd.DataFrame:
        try:
            return self.__gfts_dict.get("stops")
        except Exception:
            return "Need to load GTFS data first: gtfs2gmns.load_gtfs()"

    @property
    def stop_times(self) -> pd.DataFrame:
        try:
            return self.__gfts_dict.get("stop_times")
        except Exception:
            return "Need to load GTFS data first: gtfs2gmns.load_gtfs()"

    @property
    def trips(self) -> pd.DataFrame:
        try:
            return self.__gfts_dict.get("trips")
        except Exception:
            return "Need to load GTFS data first: gtfs2gmns.load_gtfs()"

    @property
    def transfers(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "transfers.txt")

    @property
    def timepoints(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "timepoints.txt")

    @property
    def timepoint_times(self) -> pd.DataFrame:
        return self.__get_text_data_from_folder_lst(self.gtfs_folder_list, "timepoint_times.txt")

    @property
    def trip_routes(self) -> pd.DataFrame:
        try:
            return self.__gfts_dict.get("trip_routes")
        except Exception:
            return "Need to load GTFS data first: gtfs2gmns.load_gtfs()"

    @property
    def stops_freq(self) -> pd.DataFrame:
        return None

    @property
    def route_freq(self) -> pd.DataFrame:
        return None

    @property
    def route_segments(self) -> pd.DataFrame:
        "can adopted from package gtfs_segments"
        return None

    @property
    def route_segment_speed(self) -> pd.DataFrame:
        return None

    @property
    def vis_stops_freq(self) -> None:
        "visualization of stops - 3D figure"
        "return and save the plot"
        return None

    @property
    def vis_routes_freq(self):
        "visualization of routes - 3D "
        return None

    def vis_route_segment(self, route_id: list = [], segment_id: list = []):
        "visualization of route segment - 3D figure"
        return None

    @property
    def vis_route_segment_freq(self):
        return None

    @property
    def vis_route_segment_speed(self):
        return None

    @property
    def vis_route_segment_runtime(self):
        return None

    @property
    def vis_route_stop_speed_heatmap(self):
        return None

    @property
    def vis_spacetime_trajectory(self):
        return None

    @property
    def equity_analysis(self):
        return None

    @property
    def accessibility_analysis(self):
        return None

    def __get_gtfs_folder_list(self) -> list:
        folders = os.listdir(self.gtfs_input_dir)
        gtfs_folder_list = []
        for sub_folder in folders:
            sub_folder_path = self.gtfs_input_dir + '/' + sub_folder
            # check whether the specified path is an existing directory or not.
            if os.path.isdir(sub_folder_path):
                gtfs_folder_list.append(sub_folder_path)
        if not gtfs_folder_list:
            gtfs_folder_list.append(self.gtfs_input_dir)
        return gtfs_folder_list

    def __get_agency_name_from_folder(self, folder: str) -> str:
        agency_df = pd.read_csv(folder + '/agency.txt', encoding='utf-8-sig')
        return agency_df.agency_name[0]

    def __get_text_data_from_folder_lst(self, folder_lst: list, file_name: str) -> pd.DataFrame:
        df_list = []
        for folder in folder_lst:
            path_fare_rules = folder + '/' + file_name
            if os.path.isfile(path_fare_rules):
                df_file_name = pd.read_csv(path_fare_rules, encoding='utf-8-sig')
                df_file_name["agency"] = self.__get_agency_name_from_folder(folder)
                df_list.append(df_file_name)
        if df_list:
            return pd.concat(df_list, axis=0)
        return f"No {file_name} file found in the input folder(s)."

    @func_running_time
    def load_gtfs(self) -> None:

        agency_list = []
        stop_list = []
        route_list = []
        trip_list = []
        trip_route_list = []
        stop_time_list = []
        directed_trip_route_stop_time_list = []

        for gtfsfolder in self.gtfs_folder_list:

            print(f"Info: Start reading GTFS data from: \n    :{gtfsfolder}...")

            # Step 2. Read GTFS data from a single folder
            gtfs_dict_single = read_gtfs_single(gtfsfolder, self.time_period, self.required_files)

            agency_list.append(gtfs_dict_single.get("agency"))
            stop_list.append(gtfs_dict_single.get("stops"))
            route_list.append(gtfs_dict_single.get("routes"))
            trip_list.append(gtfs_dict_single.get("trips"))
            trip_route_list.append(gtfs_dict_single.get("trip_routes"))
            stop_time_list.append(gtfs_dict_single.get("stop_times"))
            directed_trip_route_stop_time_list.append(gtfs_dict_single.get("directed_trip_route_stop_time"))

        self.__gfts_dict = {
            "agency": pd.concat(agency_list, axis=0) if len(agency_list) > 1 else agency_list[0],
            "stops": pd.concat(stop_list, axis=0) if len(stop_list) > 1 else stop_list[0],
            "routes": pd.concat(route_list, axis=0) if len(route_list) > 1 else route_list[0],
            "trips": pd.concat(trip_list, axis=0) if len(trip_list) > 1 else trip_list[0],
            "trip_routes": pd.concat(trip_route_list, axis=0) if len(trip_route_list) > 1 else trip_route_list[0],
            "stop_times": pd.concat(stop_time_list, axis=0) if len(stop_time_list) > 1 else stop_time_list[0],
            "directed_trip_route_stop_time": pd.concat(directed_trip_route_stop_time_list, axis=0) if len(directed_trip_route_stop_time_list) > 1 else directed_trip_route_stop_time_list[0]
        }
        return None

    @func_running_time
    def gen_gmns_nodes_links(self) -> list:

        # step 1. prepare gmns node and link
        try:
            directed_trip_route_stop_time_df = self.__gfts_dict.get("directed_trip_route_stop_time")
        except Exception:
            return "Need to load GTFS data first: gtfs2gmns.load_gtfs()"

        agency_lst = directed_trip_route_stop_time_df.agency_name.unique().tolist()

        all_node_lst = []
        all_link_lst = []

        for agency_index in range(len(agency_lst)):
            agency_name = agency_lst[agency_index]

            # prepare node data
            directed_trip_route_stop_time_df_agency = directed_trip_route_stop_time_df[directed_trip_route_stop_time_df.agency_name == agency_name].reset_index(drop=True)
            node_df = create_nodes(directed_trip_route_stop_time_df_agency, agency_index + 1)
            all_node_lst.append(node_df)

            # prepare link data
            all_link_lst = create_service_boarding_links(directed_trip_route_stop_time_df_agency,
                                                         node_df,
                                                         all_link_lst,
                                                         period_start_time=self.period_start_time,
                                                         period_end_time=self.period_end_time,
                                                         agency_num=agency_index + 1)

        all_node_df = pd.concat(all_node_lst)
        all_node_df.reset_index(inplace=True, drop=True)

        # transferring links
        all_link_lst = create_transferring_links(all_node_df, all_link_lst)
        all_link_df = pd.DataFrame(all_link_lst)

        all_link_df.rename(columns={0: 'link_id',
                                    1: 'from_node_id',
                                    2: 'to_node_id',
                                    3: 'facility_type',
                                    4: 'dir_flag',
                                    5: 'directed_route_id',
                                    6: 'link_type',
                                    7: 'link_type_name',
                                    8: 'length',
                                    9: 'lanes',
                                    10: 'capacity',
                                    11: 'free_speed',
                                    12: 'cost',
                                    13: 'VDF_fftt1',
                                    14: 'VDF_cap1',
                                    15: 'VDF_alpha1',
                                    16: 'VDF_beta1',
                                    17: 'VDF_penalty1',
                                    18: 'geometry',
                                    19: 'VDF_allowed_uses1',
                                    20: 'agency_name',
                                    21: 'stop_sequence',
                                    22: 'directed_service_id'}, inplace=True)

        all_link_df = all_link_df.drop_duplicates(
            subset=['from_node_id', 'to_node_id'], keep='last').reset_index(drop=True)

        # step 4. save node and link data
        # create node and link result path
        if self.isSaveToCSV:
            node_result_file = path2linux(os.path.join(self.gtfs_output_dir, "node.csv"))
            link_result_file = path2linux(os.path.join(self.gtfs_output_dir, "link.csv"))

            # validate result file path exist or not, if exist, create new file wit _1 suffix
            node_result_file = generate_unique_filename(node_result_file)
            link_result_file = generate_unique_filename(link_result_file)

            #  zone_df = pd.read_csv('zone.csv')
            #  source_node_df = pd.read_csv('source_node.csv')
            #  node_df = pd.concat([zone_df, all_node_df])
            all_node_df.to_csv(node_result_file, index=False)
            all_link_df.to_csv(link_result_file, index=False)
            print(f"Info: successfully converted gtfs data to node and link data:\n{node_result_file} \n{link_result_file}")
        else:
            print("Info: successfully converted gtfs data to node and link and return node and link dataframes")

        return [all_node_df, all_link_df]

    def download_gtfs(self, place: str = ""):
        "learn from package: gtfs_segments"
        return None

    def generate_access_link(self, zone_path: str, node_path: str, radius: float, k_closest: int = 0) -> pd.DataFrame:
        """Generate access links between zones and nodes based on the given radius and k_closest.

        Args:
            zone_path (str): _description_
            node_path (str): _description_
            radius (float): _description_
            k_closest (int, optional): _description_. Defaults to 0.

        Returns:
            pd.DataFrame: _description_
        """
        return generate_access_link(zone_path, node_path, radius, k_closest)