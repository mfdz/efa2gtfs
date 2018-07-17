#
#    efa2gtfs
#    Copyright (C) 2018  Holger Bruch <hb@mfdz.de>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import json, glob
import traceback
import itertools
import os
from efa2gtfs import util
from efa2gtfs.store import GtfsStore
from efa2gtfs import efa

class Converter():
    agencies = {}
    current_file = ''
    agency_counter = 0
    agencies_to_ignore = []
    gtfs_store = GtfsStore()
    
    pointGids_ok = {}
    pointGids_not_ok = {}
    fixed_coords = {}
    fix_stop_id_in_trip = {}
    # Workaround for corrupted data. For one route, we want to ignore some out of sequence stops
    stops_to_ignore= {}
    route_to_fix_stop_times = {}
    
    def export_gtfs(self, gtfs_filename, out_dir_name):
        if not os.path.exists(out_dir_name): os.makedirs(out_dir_name)
        self.gtfs_store.export(gtfs_filename, out_dir_name)
    
    def import_from_dir(self, dir_name, agencies_to_ignore = None):
        '''Iterates over all *.json files in DIR_NAME. The json file is assumed to be
        in DM-Request response format and to contain service lines.'''
        
        self.gtfs_store.init_static_content()
        
        if agencies_to_ignore:
            self.agencies_to_ignore += agencies_to_ignore
        
        pattern = dir_name+'/*.json'
        cnt = 0
        for fname in glob.iglob(pattern):
            try:
                cnt += 1
                print('Load ', fname, '(', cnt,'/?)')
                self.extract_gtfs_info_from_dm_response_file(fname)
            except Exception as err:
                traceback.print_exc()
        self.gtfs_store.filter_unused_stops()
                
    def extract_gtfs_info_from_dm_response_file(self, fname):
        with open(fname, "r", encoding="utf-8") as f:
            self.current_file = fname
            content = f.read()
            dm_response = json.loads(content)
            efa_dm_response = efa.DmResponse(dm_response) 
            try:
                self.extract_gtfs_info_from_dm_response(efa_dm_response)
            except (TypeError, ValueError, KeyError) as err:
                print("Uncaught exception parsing file ", fname)
                raise
                
    def extract_gtfs_info_from_dm_response(self, dm_response):
        '''Extracts stop, route, trip and stop_time information from DM_RESPONSE
        and caches it.'''
        self.gtfs_store.cache(self.process_stop_via_points(dm_response), self.gtfs_store.stops)
        self.gtfs_store.cache(self.process_stops_via_stop_sequences(dm_response).values(), self.gtfs_store.stops)
        self.gtfs_store.cache(self.process_routes(dm_response), self.gtfs_store.routes)
        self.gtfs_store.cache(self.process_trips(dm_response), self.gtfs_store.trips)
        self.gtfs_store.cache(self.process_stop_times(dm_response), self.gtfs_store.stop_times, 2)
   
    # ---- 1 --------------------------------------------------
    def process_stop_via_points(self, efa_dm_response):
        '''Extracts stops from dm/points/(point) information. Note: At least for efa-bw,
        usually only a single point is returned, which seems to be a kind of parent stop. 
        TODO: Probably other efa instances return points for each plattforms.'''
        
        points = []
        
        for point in efa_dm_response.points:
            stop_id = point.id
            rec_coords = self.retrieve_coords(point.coords, stop_id)
     
            # stop_id,stop_name,stop_lat,stop_lon,source
            points.append([
                stop_id,
                point.name,
                '', # no platform_code for "parent" station
                *rec_coords,
                self.current_file[-20:],
            ])
        return points

    # ---- 2 --------------------------------------------------
    def process_stops_via_stop_sequences(self, efa_dm_response):
        '''Extracts stops from every departure's stop sequences. Note: the current stop is
        not extracted, as this is done via the dm/points/point.'''
        out_stops = {}

        for trip in efa_dm_response.trips:      
            self.process_stops_from_seq(trip.prev_stops, out_stops)
            self.process_stops_from_seq(trip.onward_stops, out_stops)

        return out_stops
        
    def retrieve_stop_id(self, stop):
        return self.fix_stop_id(stop.stop_id, stop)
        
    def fix_stop_id(self, candidate_id, stop):
        
        if not stop.is_point_gid_consistent_wih_gid:
            (point_gid_prefix, point_gid_area, point_gid_platform) = stop.point_gid.rsplit(':',2)
            if point_gid_prefix in self.pointGids_not_ok and stop.gid==self.pointGids_not_ok[point_gid_prefix]:
                return "{}:{}:{}".format(self.pointGids_not_ok[point_gid_prefix], point_gid_area, point_gid_platform)
            elif candidate_id in self.pointGids_ok:
                # error is assumed to be in gid, not pointGid
                return candidate_id
            else:
                print("WARN: pointGid {} does not start with gid {} in file {}", stop.point_gid, stop.gid, self.current_file)
            
        return candidate_id
        
    def retrieve_coords(self, coords, stop_id):
        if stop_id in self.fixed_coords:
            return self.fixed_coords[stop_id]                
        if coords == '':
            return ['', '']
        rec_coords = coords.split(',')
        lon =     float(rec_coords[0]) / 1000000.0
        lat =     float(rec_coords[1]) / 1000000.0
        # FIXME fixing coord order currently only works for coords in germany's bounds()
        if lon > lat:
            print("WARN: swapped lat/lon as order seemed to be broken for stop {} (coords: {}, {}). Might be wrong for non-German efa instances!", stop_id, lat, lon) 
            return [lon,lat]
        else: 
            return [lat,lon]
        
    def process_stops_from_seq(self, stop_sequence, stops):            
        ''' Extracts stops from supplied stop_sequence.'''
        for stop in stop_sequence:
            try:
                id = self.retrieve_stop_id(stop)
                    
                if id in stops:
                    continue
                # only if stop not already existant extract stops 
                
                platform_code = stop.platform 
                rec_coords = self.retrieve_coords(stop.coords, id)
                stop_name = stop.name
                
                # stop_id,stop_name,platform_code,stop_lat,stop_lon,source
                row = [
                    id,
                    stop_name,
                    platform_code,
                    *rec_coords,
                    self.current_file[-20:],                    
                ]
                stops[id] = row
            except ValueError as err:
                print("ERROR processing stop: ", err)
                print(stop)
            except KeyError as err:
                print("ERROR processing stop: ", err)
                print(stop)
                raise
                
    def _should_ignore(self, network, route_type):
        '''Ignore routes/trips/stoptimes for routes from agencies
        which should be ignored AND are not ON DEMAND 
        (type 715), as this seems not to be published in GTFS 
        currently, but we are interested in...'''     
        return network in self.agencies_to_ignore and route_type != 715

    # ---- 3 --------------------------------------------------
    def process_routes(self, efa_dm_response):
        #out_routes = self.process_routes_from_servingLines(efa_dm_response)

        out_routes = self.process_routes_from_departures(efa_dm_response)  
        
        return out_routes
    
    def process_routes_from_servingLines(self, efa_dm_response):
        out_routes = []
        #route_id,agency_id,route_short_name,route_long_name,route_type,route_url,route_color,route_text_color
        for line in efa_dm_response.lines:
            network = line.network
            if self._should_ignore(network, line.route_type):
                continue
            
            agency_id = self.retrieve_agency_id(network)    
            route_desc = '' # servingLines has no itdNoTrain
            route_type_and_colors = line.route_type_and_colors

            row = [
              line.route_id,
              agency_id,
              self.route_short_name,
              self.route_long_name,
              route_desc,
              *route_type_and_colors
            ]
            out_routes.append(row)
        return out_routes
    
    def process_routes_from_departures(self, efa_dm_response):
        out_routes = []
        
        for trip, network, route_type_and_colors in self.trips_network_type(efa_dm_response):
            line = trip.serving_line
            agency_id = self.retrieve_agency_id(network)
            route_id = trip.route_id
            route_short_name = line['number']
            
            if 'directionFrom' in line:
                route_long_name = line['directionFrom'] + ' - ' + line['direction']
            else: 
                route_long_name = line['direction']
            
            if len(route_short_name) > 6:
                #print("WARN: route_short_name '{}' > 6 chars, trying to shorten it, file: {}".format(route_short_name, self.current_file))
                route_short_name = route_short_name.split(' ')[0]
                if len(route_short_name) > 6 and not any(char.isdigit() for char in route_short_name):
                    route_short_name = ''
            
            route_desc = '' if not 'itdNoTrain' in line else line['itdNoTrain']
               
            row = [
              route_id,
              agency_id,
              route_short_name,
              route_long_name,
              route_desc,
              *route_type_and_colors
            ]
            out_routes.append(row)
        
        return out_routes
        
    # ---- 4 --------------------------------------------------
    def process_trips(self, efa_dm_response):
        out_trips = []

        #trip_id,route_id,service_id,trip_headsign
        for trip in self.filtered_trips(efa_dm_response):        
            row = [
              trip.trip_id,
              trip.route_id,
              trip.service_id, 
              trip.direction
            ]
            out_trips.append(row)
        
        return out_trips

    # ---- 5 --------------------------------------------------
    def process_stop_times(self, efa_dm_response):
        out_stop_times = []
        for trip in self.filtered_trips(efa_dm_response):    
            out_stop_times.extend(self.process_stop_times_for_trip(trip))
        
        return out_stop_times

    def filtered_trips(self, efa_dm_response):
        for trip, network, route_type_and_colors in self.trips_network_type(efa_dm_response):
            yield trip
    
    def trips_network_type(self, efa_dm_response):
        for trip in efa_dm_response.trips:
            network = trip.network
            route_type_and_colors = trip.route_type_and_colors
            
            if not self._should_ignore(network, trip.route_type):            
                yield trip, network, route_type_and_colors
    
    def update_point_gid_for_stop(self, stop, prevStops, onwardStops):
        for trip_stop in itertools.chain(prevStops, onwardStops):
            # we replace to stop id with the stateless id of the first prev/onward stop with the same id
            if trip_stop.id == stop[4] and trip_stop.point_gid:
                self.gtfs_store.update_stop_id(stop, self.retrieve_stop_id(trip_stop))
                return 
    
    def update_point_gid(self, trip_id, trip):
        stops_without_point_gid = self.gtfs_store.stops_without_point_gid(trip_id)
        for stop in stops_without_point_gid:
            self.update_point_gid_for_stop(stop, trip.prev_stops, trip.onward_stops)
    
    def process_stop_times_for_trip(self, trip):
        trip_id = trip.trip_id
        
        # we process trip only if was not processed yet, to avoid gtfs issues due to efa inconsistencies
        if self.gtfs_store.is_stop_times_extracted(trip_id):
            # but we need to reprocess a trip, since a stop_time might not yet have a stop_id derived from pointGid
            self.update_point_gid(trip_id, trip)
            return []
        
        start_hour_int = trip.start_hour
        is_on_demand_trip = trip.is_on_demand_trip
        
        prev_stops = trip.prev_stops
        onward_stops = trip.onward_stops
        prev_stop_times = self.process_stop_seq_times(prev_stops, trip_id, 0, start_hour_int,is_on_demand_trip)
        
        # sometimes current stop is already contained in prevStops or is the first of the onwardStops. Probably if multiple platforms are served. TODO: there is no pointGid for current stop, but probably area/platform? 
        if not (prev_stops and trip.stop_id == prev_stops[-1].id) and not (onward_stops and trip.stop_id == onward_stops[0].id):
            current_stop_time = self.process_current_stop_time(trip, trip_id, len(prev_stop_times), start_hour_int, is_on_demand_trip)
            prev_stop_times.append(current_stop_time)
        
        onward_stop_times = self.process_stop_seq_times(onward_stops, trip_id, len(prev_stop_times), start_hour_int, is_on_demand_trip)
        
        stop_times = prev_stop_times + onward_stop_times
        route_id = trip.route_id
        if route_id in self.route_to_fix_stop_times:
            stop_times = self.fix_stop_times_order(stop_times)
        return stop_times

    def fix_stop_times_order(self, stop_times):
        sorted_stop_times = TripSorter().sort(stop_times)
        new_idx = 0
        for stop_time in sorted_stop_times:
            new_idx += 1
            if new_idx != int(stop_time[self.SEQ_IDX]):
                stop_time[self.SEQ_IDX] = new_idx
        return sorted_stop_times

    
    def process_current_stop_time(self, trip, trip_id, previous_stop_sequence,start_hour_int, is_on_demand_trip):
        route_id = trip.route_id
        stop_id = trip.stop_id
        if route_id in self.fix_stop_id_in_trip and stop_id in self.fix_stop_id_in_trip[route_id]:
            stop_id = self.fix_stop_id_in_trip[route_id][stop_id]
        if self._should_ignore_stop(trip_id, stop_id):
            return []
        
        current_stop_time = trip.stop_time
        
        return [
            trip_id,
            previous_stop_sequence + 1,
            current_stop_time,
            current_stop_time,
            stop_id,
            #'', # no headsign
            self.current_file[-20:], # insert filename as headsign for debugging purposes
            2 if is_on_demand_trip else 0, 
            2 if is_on_demand_trip else 0            
        ]
    
    def route_id_from_trip_id(self, trip_id):
        return trip_id.split('-')[0]
        
    def _should_ignore_stop(self, trip_id, stop_id):
        route_id = self.route_id_from_trip_id(trip_id)
        if route_id in self.stops_to_ignore and (stop_id in self.stops_to_ignore[route_id]):
            print("WARN: Ignore stop {} in trip {}, file {}".format(stop_id, trip_id, self.current_file))
            return True
        return False
        
    def process_stop_seq_times(self, stop_seq, trip_id, stop_sequence, start_hour_int, is_on_demand_trip):
        out_stop_times = []
        
        prevStopId = None
        for stop in stop_seq:
            # If same stop has multiple halts in sequence, we skip them, as efa seems to report them inconsistently. This different stop counts for the same trip otherwise would result in time travels.
            
            stop_id = stop.id
            if stop_id == prevStopId:
                continue
            if self._should_ignore_stop(trip_id, stop_id):
                continue
            
            stop_stateless_id = self.retrieve_stop_id(stop)
            route_id = self.route_id_from_trip_id(trip_id)
            
            if route_id in self.fix_stop_id_in_trip and stop_stateless_id in self.fix_stop_id_in_trip[route_id]:
                stop_stateless_id = self.fix_stop_id_in_trip[route_id][stop_stateless_id]
                 
            prevStopId = stop_id    
            stop_sequence += 1
            
            arrDateTime = stop.arrival_date_time
            depDateTime = stop.departure_date_time
            #trip_id,stop_sequence,arrival_time,departure_time,stop_id,stop_headsign,pickup_type,drop_off_type
            row = [
                trip_id,
                stop_sequence,
                util.convert_to_gtfs_time(*(arrDateTime.split(' ')[1].split(':')), start_hour_int)+ ':00',
                util.convert_to_gtfs_time(*(depDateTime.split(' ')[1].split(':')), start_hour_int)+ ':00',
                stop_stateless_id,
                #'', # no headsign
                self.current_file[-20:], # insert filename as headsign for debugging purposes
                2 if is_on_demand_trip else 0,
                2 if is_on_demand_trip else 0
                ]
            out_stop_times.append(row)
            
        return out_stop_times

    def retrieve_agency_id(self, network):
        '''Maps the network name to an already asigned agency_id
        or assigns a new one and stores this assignment.'''
        if network in self.agencies:
            return self.agencies[network]
        else:
            self.agency_counter += 1
            new_id = self.agency_counter
            self.agencies[network] = new_id
            agency = [
                new_id,
                network,
                'http://unknown/',
                'Europe/Berlin'
            ]
            self.gtfs_store.cache([agency], self.gtfs_store.agencies)
            return new_id
    