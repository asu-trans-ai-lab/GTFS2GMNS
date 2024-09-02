#----------------------------------------------------------------------------------------------------------------------------------------------------------------------#
# Name:        gtfs_to_traj
# Purpose:     Takes a gtfs file and converts the trip runs into trajectories for animation in tools like CartoDB/Carto 
#               
# Author:      Chetan Joshi, Portland OR
# Dependencies:None
# Created:     01/20/2018
#              
# Copyright:   (c) Chetan Joshi 2018
# Licence:     Permission is hereby granted, free of charge, to any person obtaining a copy
#              of this software and associated documentation files (the "Software"), to deal
#              in the Software without restriction, including without limitation the rights
#              to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#              copies of the Software, and to permit persons to whom the Software is
#              furnished to do so, subject to the following conditions:
#
#              The above copyright notice and this permission notice shall be included in all
#              copies or substantial portions of the Software.
#
#              THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#              IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#              FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#              AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#              LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#              OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#              SOFTWARE.
#--------------------------------------------------------------------------------------------------------------------------------------------------------------------#
import csv
import sqlite3
import sys
import numpy

#--------------TO GET ACTIVE SERVICES-------------------------------------------------#
def GetActiveServicesDay(day, fname):
    f = open(fname, 'r+')
    reader = csv.DictReader(f, delimiter = ',')
    ActiveServices = []
    for row in reader:
        if row[day] == '1':
            ActiveServices.append(row['service_id'])
    f.close()
    print 'Got: ', len(ActiveServices), ' active services.'
    return ActiveServices

def GetActiveServicesDate(date, fname):
    f = open(fname, 'r+')
    reader = csv.DictReader(f, delimiter = ',')
    ActiveServices = []
    for row in reader:
        if row['date'] == date:
            ActiveServices.append(row['service_id'])
    f.close()
    print 'Got: ', len(ActiveServices), ' active services.'
    return ActiveServices 
#------------------------------------------------------------------------------------#

def GetActiveTrips(services, fname):
    f = open(fname, 'r+')
    reader = csv.DictReader(f, delimiter = ',')
    ActiveTrips = []
    for row in reader:
        if row['service_id'] in services:
            ActiveTrips.append(row['trip_id'])
    f.close()
    print 'Got: ', len(ActiveTrips), ' active trips.'
    return ActiveTrips

def GetStopXY(fname):
    f = open(fname, 'r+')
    reader = csv.DictReader(f, delimiter = ',')
    GetStopXY = {}
    for row in reader:
        GetStopXY[row['stop_id']] = [row['stop_name'], float(row['stop_lon']), float(row['stop_lat'])]
    f.close()
    return GetStopXY

##trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type
def GetActiveJourneys(activetrips, getstopxy, fname):
    f = open(fname, 'r+')
    reader = csv.DictReader(f, delimiter = ',')
    conn = sqlite3.connect(':memory:')
    ActiveJourneys = conn.cursor()
    ActiveJourneys.execute("CREATE TABLE Journeys(trip_id TEXT, stop_id TEXT, stop_sequence INT, arrival_time INT, departure_time INT, stop_x DOUBLE, stop_y DOUBLE)")
    for row in reader:
        tmp = map(int, row['arrival_time'].split(':'))
        arr_time = tmp[0]*3600 + tmp[1]*60 + tmp[2] #h, m, s
        
        tmp = map(int, row['departure_time'].split(':'))
        dep_time = tmp[0]*3600 + tmp[1]*60 + tmp[2] #h, m, s
        
        x = getstopxy[row['stop_id']][1]
        y = getstopxy[row['stop_id']][2]
        
        ActiveJourneys.execute("insert into Journeys values ((?),(?),(?),(?),(?),(?),(?))",(row['trip_id'], row['stop_id'], int(row['stop_sequence']), arr_time, dep_time, x, y))
        conn.commit()
        
    f.close()
    return conn, ActiveJourneys

def GetTripInfo(fname):
    trip_info = {}
    f = open(fname, 'r+')
    reader = csv.DictReader(f, delimiter = ',')
    print reader.fieldnames
    if 'trip_headsign' in reader.fieldnames:
        for row in reader:
            trip_info[row['trip_id']] = [row['route_id'],row['service_id'],row['trip_headsign']]
    else:
        for row in reader:
            trip_info[row['trip_id']] = [row['route_id'],row['service_id'],row['direction_id']]
    f.close()
    return trip_info

def GetDiscretePoints(arr, dep, tfac, x1, y1, x2, y2):
    s = ((y2 - y1)**2 + (x2 - x1)**2)**0.5
    dx = x2 - x1
    dy = y2 - y1
    t = (arr - dep)/tfac
    v = s/max(t,1)
    r = v * numpy.arange(t)
    xi = x1 + r * dx/s
    yi = y1 + r * dy/s
    return zip(xi, yi, numpy.arange(t))

#--------------------------USAGE EXAMPLE-------------------------------------------------------------------------------------------------------#
##day = 'monday'
##fname = r'C:\Projects\Generic\Mapping Experiments\Amtrak_transit_feed\calendar.txt'
##services = GetActiveServicesDay(day, fname)
print 'start processing data...' 
date = '20170519'
fname = r'C:\Projects\Generic\Mapping Experiments\gtfs\calendar_dates.txt'
services = GetActiveServicesDate(date, fname)

fname = r'C:\Projects\Generic\Mapping Experiments\gtfs\trips.txt'
activetrips = GetActiveTrips(services, fname)

trip_info = GetTripInfo(fname)

fname = r'C:\Projects\Generic\Mapping Experiments\gtfs\stops.txt'
getstopxy = GetStopXY(fname)

fname = r'C:\Projects\Generic\Mapping Experiments\gtfs\stop_times.txt'
conn, ActiveJourneys = GetActiveJourneys(activetrips, getstopxy, fname)

fout = r'C:\Projects\Generic\Mapping Experiments\gtfs\trimet_traj3.csv'
f = open(fout, 'wb')
writer = csv.writer(f, delimiter = ',')
writer.writerow(['trip_id','trip_headsign','route_id','lon','lat','timepoint'])

journey_filter = ['06:00:00', '07:00:00'] #start and end time to impose time bounds

print 'generating trajectories...'
start = map(int, journey_filter[0].split(':'))
start = start[0]*3600 + start[1]*60 + start[2]

end = map(int, journey_filter[1].split(':'))
end = end[0]*3600 + end[1]*60 + end[2]

uni_trips = ActiveJourneys.execute("select distinct trip_id from Journeys")
uni_trips = uni_trips.fetchall()

time_scale = 30

for trip_id, in uni_trips:
    jrny = ActiveJourneys.execute("select trip_id, stop_id, arrival_time, departure_time, stop_x, stop_y from Journeys where trip_id = "+str(trip_id)+" order by stop_sequence")
    jrny = jrny.fetchall()
    if jrny[0][3] >= start and jrny[-1][2] <= end: #only trip between the given time bounds are processed
        all_points = []
        for i in range(0, len(jrny)-1):
            points = GetDiscretePoints(jrny[i+1][2], jrny[i][3], time_scale, jrny[i][4], jrny[i][5], jrny[i+1][4], jrny[i+1][5])
            all_points.extend(points)
            
        start_time = jrny[0][3]/time_scale #start time offset in minutes
        trip_headsign = trip_info[trip_id][2]
        trip_route = trip_info[trip_id][0]
        for lon, lat, tp in all_points:
            writer.writerow([trip_id,trip_headsign,trip_route,lon,lat,start_time])
            start_time+=1
f.close()
conn.close()

print 'finished data processing!'
