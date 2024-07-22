## GTFS2GMNS

The open-source Python codes (GTFS2GMNS) is released to facilitate researchers and planners to construct the multi-modal transit networks easily from generic [General Transit Feed Specification (GTFS)](https://gtfs.org/) to the network modeling format in [General Modeling Network Specification (GMNS)](https://github.com/zephyr-data-specs/GMNS). The converted physical and service networks in GMNS format are more convenient for network modeling tasks such as transit network routing, traffic flow assignment, simulation and service network optimization.

Your comments will be valuable for code review and improvement. Please feel free to add your comments to our Google document of [GTFS2GMNS Users&#39; Guide](https://docs.google.com/document/d/1-A2g4ZjJu-gzusEKcSoOXzr95S3tv7sj/edit?usp=sharing&ouid=112385243549486266715&rtpof=true&sd=true).

## Getting Started

### *Download GTFS Data*

On TransitFeed [homepage](https://transitfeeds.com/), users can browse and download official GTFS  feeds from around the world. Make sure that the following files are present, so that we can proceed.

* stop.txt
* route.txt
* trip.txt
* stop_times.txt
* agency.txt

GTFS2GMNS can handle the transit data from several agencies. Users need to configure different sub-files in the same directory. Under the `test/GTFS` folder, a subfolder `Pheonix` with its owm GTFS data is set up.

### *Convert GTFS Data into GMNS Format*

```python
if __name__ == '__main__':
    global period_start_time
    global period_end_time
    input_gtfs_path = 'GTFS'
    output_gmns_path = '.'
    time_period_id = 1
    time_period = '1200_1300'
    period_start_time, period_end_time = _hhmm_to_minutes(time_period)

    gtfs2gmns(input_gtfs_path, output_gmns_path)
```

The input parameter  `input_gtfs_path` is the path of GTFS data, and the parameter  `output_gmns_path` is the path of output GMNS files. Users can customize the parameter  `time_period`, such as 12:00 to 13:00.

The output files include node.csv and link.csv.

## Main Steps

### *Read GTFS data*

**Step 1.1: Read routes.txt**

- route_id, route_long_name, route_short_name, route_url, route_type

**Step 1.2: Read stop.txt**

- stop_id, stop_lat, stop_lon, direction, location_type, position, stop_code, stop_name, zone_id

**Step 1.3: Read trips.txt**

- trip_id, route_id, service_id, block_id, direction_id, shape_id, trip_type
- and create the directed_route_id by combining route_id and direction_id

**Step 1.4: Read stop_times.txt**

- trip_id, stop_id, arrival_time, deaprture_time, stop_sequence
- create directed_route_stop_id by combining directed_route_id and stop_id through the trip_id

  > Note: the function needs to skip this record if trip_id is not defined, and link the virtual stop id with corresponding physical stop id.
  >
- fetch the geometry of the direction_route_stop_id
- return the arrival_time for every stop

### *Building service network*

**Step 2.1 Create physical nodes**

- physical node is the original stop in standard GTFS

**Step 2.2 Create directed route stop vertexes**

- add route stop vertexes. the node_id of route stop nodes starts from 100001

  > Note: the route stop vertex the programing create nearby the corresponding physical node, to make some offset.
  >
- add entrance link from physical node to route stop node
- add exit link from route stop node to physical node. As they both connect to the physical nodes, the in-station transfer process can be also implemented

**Step 2.3 Create physical arcs**

- add physical links between each physical node pair of each trip

**Step 2.4 Create service arcs**

- add service links between each route stop pair of each trip

## Visualization

You can visualize generated networks using [NeXTA](https://github.com/xzhou99/NeXTA-GMNS) or [QGIS](https://qgis.org/).

## Quick Tutorial

### Introducing Functional Tools within GTFS2GMNS

GTFS2GMNS is a Python package that serves as a class-based instance, specifically designed for reading, converting, analyzing, and visualizing GTFS data. The converted physical and service networks in GMNS format offer enhanced convenience for a variety of networkAg modeling tasks, including transit network routing, traffic flow assignment, simulation, and service network optimization.

### Input for class GTFS2GMNS

- **gtfs_input_dir** :  str, the dir store GTFS data. **GTFS2GMNS is capable of reading multiple GTFS data sets.**
- **time_period**: str, the time period sprcified (for data selection), default is "07:00:00_08:00:00"
- **date_period**: list, user can specified exact data or dates for selection
- **gtfs_output_dir**: str, the output folder to save data. defalut is ""
- **isSaveToCSV**: bool, whether to save gmns node and link to local machine, default is True

### *Code Example*

#### Loading gtfs data

```python
from gtfs2gmns import GTFS2GMNS

if __name__ == "__main__":
    gtfs_input_dir = r"Your-Path-Folder-To-GTFS-Data"

    # Explain: GMNS2GMNS is capable of reading multiple GTFS data sets
    """
	--root folder
	    -- subfolder (GTFS data of agency 1)
	    -- subfolder (GTFS data of agency 2)
	    -- subfolder (GTFS data of agency 3)
	    -- ...
	then, assign gtfs_input_foler = root folder
    """

    time_period = "00:00:00_23:59:59"
    date_period = []

    gg = GTFS2GMNS(gtfs_input_dir, time_period, date_period, gtfs_output_dir="", isSaveToCSV=False)

```

#### Generate access line between zones to nodes

```python

import gtfs2gmns as gg

path_zone = "Path to zone.csv"    # please make sure you have zone_id, x_coord, y_coord in columns
path_node = "Path to node.csv"    # please make sure you have node_id, x_coord, y_coord in columns

radius = 100 # unit in meters
k_closest = 0 # if 0, generate all accessible links within radius. if 1, closest link within the radius...

access_links = gg.generate_access_links(path_zone, path_node, radius, k_closest)

access_links.to_csv("access_link.csv", index=False)

```

### Functions and Attributes


| func_type     | func_name                    | Python example | Input | Output    | Remark                                                        |
| :------------ | :--------------------------- | :------------- | ----- | --------- | ------------------------------------------------------------- |
| read-show     | agency                       | `gg.agency`    | NA    | DataFrame | This attribute load and return agency data from source folder |
|               | calendar                     | `gg.calendar`  |       |           |                                                               |
|               | calendar_dates               |                |       |           |                                                               |
|               | fare_attributes              |                |       |           |                                                               |
|               | fare_rules                   |                |       |           |                                                               |
|               | feed_info                    |                |       |           |                                                               |
|               | frequencies                  |                |       |           |                                                               |
|               | routes                       |                |       |           |                                                               |
|               | shapes                       |                |       |           |                                                               |
|               | stops                        |                |       |           |                                                               |
|               | stop_times                   |                |       |           |                                                               |
|               | trips                        |                |       |           |                                                               |
|               | transfers                    |                |       |           |                                                               |
|               | timepoints                   |                |       |           |                                                               |
|               | timepoint_times              |                |       |           |                                                               |
|               | trip_routes                  |                |       |           |                                                               |
|               | stops_freq                   |                |       |           |                                                               |
|               | routes_freq                  |                |       |           |                                                               |
|               | rute_segments                |                |       |           |                                                               |
|               | route_segment_speed          |                |       |           |                                                               |
|               | vis_stops_freq               |                |       |           |                                                               |
| analysis      | vis_routes_fres              |                |       |           |                                                               |
|               | vis_route_segment_speed      |                |       |           |                                                               |
|               | vis_route_segment_runtime    |                |       |           |                                                               |
|               | vis_route_stop_speed_heatmap |                |       |           |                                                               |
|               | vis_spacetime_trajectory     |                |       |           |                                                               |
|               | equity_alanysis              |                |       |           |                                                               |
|               | accessibility_analysis       |                |       |           |                                                               |
|               | load_gtfs                    |                |       |           |                                                               |
|               | gen_gmns_node_link           |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |
| visualization |                              |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |
|               |                              |                |       |           |                                                               |




## Upcoming Features

- [ ] Output service and trace files.
- [ ] Set the time period and add vdf_fftt and vdf_freq fields in link files.
- [ ] Add Visualization functions
  - [ ] Stops
  - [ ] Routes
  - [ ] ...

## Citing gtfs2gmns

If you use gtfs2gmns in your research please use the following BibTeX entry:

```
@misc{gtfs2gmns,
  author =       {Fang Tang, Xiangyong Luo, Han Wang, Xuesong Zhou},
  title =        {Connecting Oasis for Transit Deserts: Mathematical Model and Reformulation for Equity-oriented Network Design},
  howpublished = {Github},
  year =         {2023},
  url =          {https://github.com/xyluo25/gtfs2gmns}
}
```


```bibtex
@misc{gtfs2gmns,
  author =       {Xiangyong Luo, Fang Tang, Han Wang, Xuesong Zhou},
  title =        {gtfs2gmns - A class-based instance designed for reading, converting, analyzing, and visualizing GTFS data.},
  howpublished = {Github},
  year =         {2023},
  url =          {https://github.com/xyluo25/gtfs2gmns}
}
```



```
Luo, X., Tang, F, Wang, H and Zhou, X. (2021, April 4). GTFS2GMNS. Retrieved from https://github.com/xyluo25/gtfs2gmns
```

