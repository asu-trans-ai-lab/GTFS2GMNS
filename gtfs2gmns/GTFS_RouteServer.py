#-----------------------------------------------------------------------------------------------------------------------
# Name:        GTFS route server version 1.0 (server side script)
# Purpose:     Generates a search graph as edge list that may be used to perform large scale timetable based route searches
#              on GTFS data. Depends on NetworkX (http://networkx.github.io/documentation/networkx-1.9.1/index.html)
#              for shortest path searches in addition to other standard python modules, the search graph in generated
#              is generic so it can be used with any other graph search library if desired.
# Author:      Chetan Joshi, Portland OR
#
# Created:     6/12/2015
#
# Dependencies: networkx module for running graph search efficiently is required, xmlrpc is used for running the query  
#
# Copyright:   (c) Chetan Joshi 2015
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
#----------------------------------------------------------------------------------------------------------------------

import csv
import time, os
import ast
from math import *
import networkx as nx
start = time.time()
from SimpleXMLRPCServer import SimpleXMLRPCServer
server = SimpleXMLRPCServer(("localhost", 8000))

def computeGCD(lat1,lon1,lat2,lon2):
    #computes great circle distance from lat/lon
    '''lat1/lon1 = lat/lon of first pt
       lat2/lon2 = lat/lon of second pt
    '''
    degRad = pi/180
    lat1 = degRad*lat1
    lon1 = degRad*lon1
    lat2 = degRad*lat2
    lon2 = degRad*lon2
    dellambda = lon2-lon1
    Numerator = sqrt((cos(lat2)*sin(dellambda))**2 + (cos(lat1)*sin(lat2)- sin(lat1)*cos(lat2)*cos(dellambda))**2)
    Denominator = sin(lat1)*sin(lat2) + cos(lat1)*cos(lat2)*cos(dellambda)
    delSigma = atan2(Numerator,Denominator)

    return 3963.19059*delSigma

def getCandidateStops(oPoint, dPoint, stopdata, maxDist):
    '''oPoint = tuple/list of origin lat/lon
       dPoint = tuple/list of destination lat/lon
       stopdata = stopdata dictionary with -> key:stop_id, values[stop_name, stop_lat, stop_lon]
       maxDist = max cutoff distance for search
       returns a dict with list stopID -> walk time, stop(lat/lon)
    '''
    oStopIDs = {}
    dStopIDs = {}
    for stopid in stopdata.keys():
        dist = computeGCD(oPoint[0],oPoint[1],stopdata[stopid][1],stopdata[stopid][2])
        if  dist < maxDist:
            oStopIDs[stopid] = [dist*3600/3.0, (stopdata[stopid][1], stopdata[stopid][2])]
            
        dist = computeGCD(dPoint[0],dPoint[1],stopdata[stopid][1],stopdata[stopid][2])
        if  dist < maxDist:
            dStopIDs[stopid] = [dist*3600/3.0, (stopdata[stopid][1], stopdata[stopid][2])]
    return oStopIDs, dStopIDs


def createTransferFile(dir, maxDist, stopsfile=r'\stops.txt', transferfile=r'\transfers.txt'):
    #utility to create a stop to stop transfer file is it does not already exist with the GTFS file set
    #calculation method is not very clever so running time may get prohibitive if too many stops
    '''dir = directory path where files are stored
    maxDist = maximum walk distance in miles
    stopsfile = name of the file where stop data is stored - see GTFS stops.txt for format also default name
    transferfile = name of the file where transfer data is stopred - see GTFS transfers.txt for format also default name
    '''
    print 'Generating transfer file from user spec...'
    ts1 = time.time()
    fn = open(dir+stopsfile, 'rb')
    reader = csv.reader(fn, delimiter=',')
    atts = reader.next()
    attix = dict(zip(atts, range(len(atts))))
    #print attix
    stopdata = {}
    for row in reader:
        stopdata[row[attix['stop_id']]] = [row[attix['stop_name']], float(row[attix['stop_lat']]), float(row[attix['stop_lon']])]
    fn.close()

    calctransfer = [['from_stop_id','to_stop_id','transfer_type']]
    oStops = stopdata.keys()
    dStops = stopdata.keys()
    for oStop in oStops:
        oStopLat = stopdata[oStop][1]
        oStopLon = stopdata[oStop][2]
        for dStop in dStops:
            dStopLat = stopdata[dStop][1]
            dStopLon = stopdata[dStop][2]
            dist = computeGCD(oStopLat,oStopLon,dStopLat,dStopLon)
            if dist <= maxDist and oStop <> dStop:
                calctransfer.append([oStop, dStop, 0])

    fn = open(dir+transferfile, 'wb')
    writer = csv.writer(fn)
    writer.writerows(calctransfer)
    fn.close()
    del calctransfer, stopdata
    print 'Finised generating transfer file from user spec in ',time.time()-ts1, ' secs'


def BuildSearchGraph(dir, xferpen, calmethod, date='', day=''):
    '''dir = directory path of the GTFS file set
       xferpen = transfer penalty in seconds - needed for getting fewer transfer in paths
       calmethod = 1--> use calendar.txt
                 = 2--> use calendar_dates.txt
                 = 3--> use both calendar and calendar_dates 
       day = string input (if calmethod = 1) for day of trip -> 'monday', 'tuesday', 'wednesday' ,'thursday', 'friday', 'saturday', 'sunday'
       date = string input (if calmethod = 2) on date as per GTFS-> YYYYMMDD
       The function returns: 1) edges (list to build Graph in networkX),
                             2) validservices (dict to lookup valid service IDs),
                             3) validtrips (dict to get trips valid that day-> maps to RouteID),
                             4) stoptrips (dict of services serving a stop),
                             5) getstopid (dict of trip_id+stop_id -> arrival, departure info),
                             6) stopdata (dict of stop properties)
    '''
    t0 = time.time()
    filesindir = set(os.listdir(dir))
    print 'Files found in directory: ', filesindir
    reqdfiles = ['stops.txt', 'trips.txt', 'stop_times.txt']#, 'transfers.txt']
    if calmethod == 1:
        reqdfiles.append('calendar.txt')
    elif calmethod == 2:
        reqdfiles.append('calendar_dates.txt')
    elif calmethod == 3:
        reqdfiles.append('calendar.txt')
        reqdfiles.append('calendar_dates.txt')
        
    filesok = 0
    if filesindir.issuperset(reqdfiles):
        filesok=1
        print 'Starting to process feed data...'
        if calmethod == 1:
            #1.a) get calendar for service id and valid day
            fn = open(dir+r'\calendar.txt', 'rb')
            reader = csv.reader(fn, delimiter=',')
            atts = reader.next()
            serviceday = dict(zip(atts, range(len(atts))))
            #service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
            validservices = {}
            for row in reader:
                if row[serviceday[day]] == '1':
                    validservices[row[serviceday['service_id']]] = 1
            fn.close()

        elif calmethod == 2:
            #1.b) Valid services based on calendar_dates.txt
            fn = open(dir+r'\calendar_dates.txt', 'rb')
            reader = csv.reader(fn, delimiter=',')
            reader.next()
            #service_id,date,exception_type
            validservices = {}
            for row in reader:
                if row[1] == date and row[2] == '1':
                    validservices[row[0]] = 1
            fn.close()
            #print validservices
        elif calmethod == 3:
            #1.c) get calendar for service id and valid day
            fn = open(dir+r'\calendar.txt', 'rb')
            reader = csv.reader(fn, delimiter=',')
            atts = reader.next()
            serviceday = dict(zip(atts, range(len(atts))))
            #service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
            validservices = {}
            for row in reader:
                if row[serviceday[day]] == '1':
                    validservices[row[serviceday['service_id']]] = 1
            fn.close()

            fn = open(dir+r'\calendar_dates.txt', 'rb')
            reader = csv.reader(fn, delimiter=',')
            reader.next()
            #service_id,date,exception_type
            serviceexcept = {}
            for row in reader:
                if row[1] == date:
                    serviceexcept[row[0]] = row[2] #1 -> add, 2 --> remove
            fn.close()
            #valid services has all services without exception... now we filter out the ones not applicable to a date...
            for key in serviceexcept.keys():
                if serviceexcept[key] == '1':   #1 -> add, 2 --> remove
                    if not validservices.has_key(key):
                        validservices[key] = 1  # -> insert an added service if it does not already exist
                elif serviceexcept[key] == '2':
                    if validservices.has_key(key):
                        validservices.pop(key)  # --> pop out an invalid service for the day

        #2) get valid trip_id based on valid services
        fn = open(dir+r'\trips.txt', 'rb')
        reader = csv.reader(fn, delimiter=',')
        atts = reader.next()
        attix = dict(zip(atts, range(len(atts))))
        #print attix
        validtrips = {} #gives route id based on trip id
        for row in reader:
            if validservices.has_key(row[attix['service_id']]):
                validtrips[row[attix['trip_id']]]=row[attix['route_id']]
        fn.close()
        #print validtrips
        #3) now build veh journeys from valid trips
        fn = open(dir+r'\stop_times.txt', 'rb')
        reader = csv.reader(fn, delimiter=',')
        atts = reader.next()
        attix = dict(zip(atts, range(len(atts))))
        #print attix
        stoptrips = {}
        getstopid = {}
        edges = []
        stop_times = []
        cnt=0
        for row in reader:
            #this builds stop to stop times for valid trips...
            #trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled
            if validtrips.has_key(row[attix['trip_id']]):
                stop_times.append(row)
                getstopid[row[attix['trip_id']]+'^'+row[attix['stop_id']]]=[row[attix['stop_id']], row[attix['arrival_time']], row[attix['departure_time']]]
            #this builds wihin stop transfers...
                try:
                    if stoptrips.has_key(row[attix['stop_id']]):
                        arr = map(int, row[attix['arrival_time']].split(':'))
                        arrtm = arr[0]*3600 + arr[1]*60 + arr[2]
                        dep = map(int, row[attix['departure_time']].split(':'))
                        deptm = dep[0]*3600 + dep[1]*60 + dep[2]
                        stoptrips[row[attix['stop_id']]].append([row[attix['trip_id']], arrtm, deptm])
                    else:
                        arr = map(int, row[attix['arrival_time']].split(':'))
                        arrtm = arr[0]*3600 + arr[1]*60 + arr[2]
                        dep = map(int, row[attix['departure_time']].split(':'))
                        deptm = dep[0]*3600 + dep[1]*60 + dep[2]
                        stoptrips[row[attix['stop_id']]]=[[row[attix['trip_id']], arrtm, deptm]]
                except:
                    if cnt < 10:
                        print 'Failed to convert data for row: ', row
                        cnt+=1
                    else:
                        pass

        fn.close()
        print 'Finished building basic lookups and filtering data: ', time.time() - start, ' secs'
        start1 = time.time()
        cnt = 0
        for i in xrange(0, len(stop_times)-1):
            if stop_times[i][attix['trip_id']] == stop_times[i+1][attix['trip_id']]:
                try:
                    arr = map(int, stop_times[i+1][attix['arrival_time']].split(':'))
                    arrtm = arr[0]*3600 + arr[1]*60 + arr[2]
                    dep = map(int, stop_times[i][attix['departure_time']].split(':'))
                    deptm = dep[0]*3600 + dep[1]*60 + dep[2]
                    edges.append([stop_times[i][attix['trip_id']]+'^'+stop_times[i][attix['stop_id']],
                                  stop_times[i+1][attix['trip_id']]+'^'+stop_times[i+1][attix['stop_id']],
                                  arrtm-deptm])
                except:
                    if cnt < 10:
                        print 'Failed to convert data for row: ', row
                        cnt+=1
                    else:
                        pass

        print 'Finished building line graph: ', time.time() - start1, ' secs ', len(edges), ' edges so far...'
        del stop_times
        start2 = time.time()

        for key in stoptrips.keys():
            strps = stoptrips[key]
##            avghw = 24*60/len(strps)
##            if avghw < 15:
##                lim = 2400
##            else:
##                lim = 3600
            lim = 4800
            for ostp, oarr, odep in strps:
                for dstp, darr, ddep in strps:
                    if oarr < ddep and validtrips[ostp] <> validtrips[dstp]: #--> no need to create transfer on same route id
                        conntime = max(60, ddep - oarr)
                        if conntime < lim:
                            edges.append([ostp+'^'+key, dstp+'^'+key, conntime+xferpen])

        print 'Finished building valid transfers within stops: ', time.time() - start2, ' secs', len(edges), ' edges so far...'

        fn = open(dir+r'\stops.txt', 'rb')
        reader = csv.reader(fn, delimiter=',')
        atts = reader.next()
        attix = dict(zip(atts, range(len(atts))))
        #print attix
        stopdata = {}
        for row in reader:
            stopdata[row[attix['stop_id']]] = [row[attix['stop_name']], float(row[attix['stop_lat']]), float(row[attix['stop_lon']])]
        fn.close()
        
        if filesindir.intersection(['transfers.txt']):            
            #4) load transfer file between stops...
            fn = open(dir+r'\transfers.txt', 'rb')
            reader = csv.reader(fn, delimiter=',')
            atts = reader.next()
            attix = dict(zip(atts, range(len(atts))))
            #print attix
            #walkedges = []
            #from_stop_id,to_stop_id,transfer_type
            for row in reader:
                if stoptrips.has_key(row[attix['from_stop_id']]) and stoptrips.has_key(row[attix['to_stop_id']]):
                    ostoptrips = stoptrips[row[attix['from_stop_id']]]
                    dstoptrips = stoptrips[row[attix['to_stop_id']]]
    ##                avghw = 24*60/len(dstoptrips)
    ##                if avghw < 15:
    ##                    lim = 2400
    ##                else:
    ##                    lim = 3600
                    lim = 4800
                    wlktim = computeGCD(stopdata[row[attix['from_stop_id']]][1],stopdata[row[attix['from_stop_id']]][2],stopdata[row[attix['to_stop_id']]][1],stopdata[row[attix['to_stop_id']]][2])*1200*1.25
        ##            wlkdis = wlktim/1200
                    for ostp, oarr, odep in ostoptrips:
                        for dstp, darr, ddep in dstoptrips:
                            #trip_id, arr, dep
                            if oarr+wlktim < ddep and validtrips[ostp] <> validtrips[dstp]:
                                conntime = max(60, ddep - oarr)
                                if conntime < lim:
                                    #validxfers[ostp+key, dstp+key] = conntime
                                    edges.append([ostp+'^'+row[attix['from_stop_id']], dstp+'^'+row[attix['to_stop_id']], conntime+xferpen])
                                    #walkedges.append([ostp+'^'+row[attix['from_stop_id']], dstp+'^'+row[attix['to_stop_id']], wlktim])
        print 'Finished generating complete search graph in ', time.time()-t0, ' secs'
        G = nx.DiGraph()
        G.add_weighted_edges_from(edges, 'time')
        del edges
        return G, validservices, validtrips, stoptrips, getstopid, stopdata
    else:
        print 'The set of required files for generating the search graph is not complete. Processing aborted!'   #--->if this happens abort..
        return 0

#dirloc = r"C:\DevResearch\GTFS Builder\gtfs_trimet"
dirloc = r"C:\DevResearch\GTFS Builder\gtfs_puget_sound_consolidated"
xferpen = 650
calmethod = 3
date = '20151113' #'20150611'
day = 'friday'

beg = time.time()
print 'Building search graph...'
global G, validservices, validtrips, stoptrips, getstopid, stopdata #= BuildSearchGraph(dirloc, xferpen, calmethod, date, day)
G, validservices, validtrips, stoptrips, getstopid, stopdata = BuildSearchGraph(dirloc, xferpen, calmethod, date, day)
print 'Finished building search graph in: ', time.time()-beg, ' secs'

def GetRouteDetail(o, d): #, validtrips, getstopid):
    path = nx.dijkstra_path(G,o,d, weight='time')
    #print path
    tmp = path[0].split('^')
    print 'Start by taking route: ', validtrips[tmp[0]], ' from: ', getstopid[path[0]][0] ,' at: ', getstopid[path[0]][2]
    #resultstr = str(['Start by taking route: ', validtrips[tmp[0]], ' from: ', getstopid[path[0]][0] ,' at: ', getstopid[path[0]][2]])
    deptimeinput = map(int, getstopid[path[0]][2].split(':'))
    start = deptimeinput[0]*3600 + deptimeinput[1]*60 + deptimeinput[2]
    currentRoute = validtrips[tmp[0]]
    for i in xrange(1, len(path)-1):
        tmp = path[i].split('^')
        if validtrips[tmp[0]] <> currentRoute:
            print 'Transfer at: ', getstopid[path[i]][0], ' to route: ', validtrips[tmp[0]],' at: ', getstopid[path[i]][2]
            #'Transfer at: ', getstopid[path[i]][0], ' to route: ', validtrips[tmp[0]],' at: ', getstopid[path[i]][2]
            currentRoute = validtrips[tmp[0]]
            
    tmp = path[-1].split('^')
    print 'End at destination: ', getstopid[path[-1]][0], ' on route: ', validtrips[tmp[0]] ,'at: ', getstopid[path[-1]][1]
    #resultstr+= str('End at destination: ', getstopid[path[-1]][0], ' on route: ', validtrips[tmp[0]] ,'at: ', getstopid[path[-1]][1])
    deptimeinput = map(int, getstopid[path[-1]][1].split(':'))
    end = deptimeinput[0]*3600 + deptimeinput[1]*60 + deptimeinput[2]
    
    print 'Travel time: ', (end - start)/60.0, ' mins'
    #resultstr+=str('Travel time: ', (end - start)/60.0, ' mins')
    #return resultstr


def GetRouteTime(o, d, validtrips, getstopid):
    path = nx.dijkstra_path(G,o,d, weight='time')
    #print path
    tmp = path[0].split('^')
    deptimeinput = map(int, getstopid[path[0]][2].split(':'))
    start = deptimeinput[0]*3600 + deptimeinput[1]*60 + deptimeinput[2]

    deptimeinput = map(int, getstopid[path[-1]][1].split(':'))
    end = deptimeinput[0]*3600 + deptimeinput[1]*60 + deptimeinput[2]
    ttime = end - start
    #print 'Travel time: ', ttime, ' secs'
    return ttime

def Quit():
    global flag
    flag = 1
    return flag

#server.register_function(BuildSearchGraph, 'BuildSearchGraph')
server.register_function(GetRouteDetail, 'GetRouteDetail')
server.register_function(GetRouteTime, 'GetRouteTime')
server.register_function(Quit, 'Quit')

flag = 0
while flag <> 1:
    server.handle_request()


