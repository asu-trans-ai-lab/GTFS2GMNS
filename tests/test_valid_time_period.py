# -*- coding:utf-8 -*-
##############################################################
# Created Date: Friday, March 1st 2024
# Contact Info: luoxiangyong01@gmail.com
# Author/Copyright: Mr. Xiangyong Luo
##############################################################

import pytest
import datetime
from gtfs2gmns.utility_lib import validate_time_period


def test_validate_time_period():
    # Test valid time period
    time_period = "07:00:00_09:00:00"
    expected_result = [datetime.datetime(1900, 1, 1, 7, 0), datetime.datetime(1900, 1, 1, 9, 0)]
    assert validate_time_period(time_period) == expected_result

    # Test invalid time period format
    time_period = "07:00:00-09:00:00"
    with pytest.raises(Exception, match="Error: time period should be in the format of 'startTime_endTime'"):
        validate_time_period(time_period)

    # Test invalid time period values
    time_period = "07:00:0s_09:60:00"
    with pytest.raises(Exception, match="Error: hour, minute, and second should be integers"):
        validate_time_period(time_period)

    time_period = "07:00:00_09:00:6s"
    with pytest.raises(Exception, match="Error: hour, minute, and second should be integers"):
        validate_time_period(time_period)