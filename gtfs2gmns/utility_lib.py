# -*- coding:utf-8 -*-
##############################################################
# Created Date: Wednesday, November 16th 2022
# Contact Info: luoxiangyong01@gmail.com
# Author/Copyright: Mr. Xiangyong Luo
##############################################################

import datetime


def validate_time_period(time_period: str) -> list:
    # Step 2: Check and Format time period
    if "_" not in time_period:
        raise Exception("Error: time period should be in the format of 'startTime_endTime', e.g., '07:00:00_09:00:00'")

    period_start_str, period_end_str = time_period.split("_")
    if not all([period_start_str[:2].isdigit(),
                period_start_str[3:5].isdigit(),
                period_start_str[6:8].isdigit()]):
        raise Exception(
            "Error: hour, minute, and second should be integers, e.g., '07:00:00'")

    if not all([period_end_str[:2].isdigit(),
                period_end_str[3:5].isdigit(),
                period_end_str[6:8].isdigit()]):
        raise Exception(
            "Error: hour, minute, and second should be integers, e.g., '07:00:00'")

    period_start_time = datetime.datetime.strptime(period_start_str, '%H:%M:%S')
    period_end_time = datetime.datetime.strptime(period_end_str, '%H:%M:%S')
    return [period_start_time, period_end_time]

