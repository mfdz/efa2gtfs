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

from . import util

# See https://developers.google.com/transit/gtfs/reference/extended-route-types
route_type_and_colors = {
    0: ['100', '8f908f', 'FFFFFF'], # Zug => Railway
    1: ['109', '83b23b', 'FFFFFF'], # S-Bahn => Suburban Railway
    2: ['402', '004DFF', 'FFFFFF'], # U-Bahn => Underground Service
    3: ['403', '004DFF', 'FFFFFF'], # Stadtbahn => Urban Railway Service (Note: VVS classifies as 402, but as it runs under/above ground, we classify as urban railway...)
    4: ['900', '004DFF', 'FFFFFF'],   # Straßen/Trambahn => Tram Service TODO Farbe ok?
    5: ['704', 'FF0000', 'FFFFFF'],   # Stadtbus => Local Bus Service
    6: ['701', 'FF0000', 'FFFFFF'],   # Regionalbus => Regional Bus Service
    7: ['702', '19ffff', '000000'], # Schnellbus => Express Bus Service
    8: ['116', '83b23b', 'FFFFFF'], # Seil-/Zahnradbahn => TODO Zahnrad would be 116 Rack and Pinion Railway, Seilbahn would be 1400 Funicular...
    9: ['1000', '0000FF', 'FFFFFF'],# Schiff => Water Transport Service
    10:['715', 'FF0000', 'FFFFFF'], # AST/Rufbus => Demand and Response Bus Service
    11:['715', 'FF0000', 'FFFFFF'], # TODO: Need to verify that product is emma to map to 715
    12: ['1100', '8f908f', 'FFFFFF'], # Flugzeug => Air Service
    13: ['106', '8f908f', 'FFFFFF'], # Zug (Nahverkehr) => Rail
    14: ['102', '8f908f', 'FFFFFF'], # Zug (Fernverkehr) => Rail
    15: ['102', '8f908f', 'FFFFFF'], # Zug (Fernverkehr mit ?) => Rail
    16: ['102', '8f908f', 'FFFFFF'], # Zug (Fernverkehr mit ?) => Rail
    17: ['714', '8f908f', 'FFFFFF'], # Schienenersatzverkehr => Rail Replacement Bus Service
    18: ['108', '8f908f', 'FFFFFF'], # Zug Shuttle => Rail Shuttle (Whitin Complex) (?)
    19: ['707', '8f908f', 'FFFFFF'], # Bürgerbus => Special Needs (No good match available(?))
    }    


class DmResponse(object):
    def __init__(self, data):
        self._data = data

    @property
    def points(self):
        return (DmPoint(point) for point in util.as_array(self._data['dm'],'points'))

    @property
    def departures(self):
        return util.as_array(self._data, 'departureList')

    @property
    def trips(self):
        return (DmDeparture(dep) for dep in util.as_array(self._data, 'departureList'))

    @property
    def lines(self):
        return (DmLine(line) for line in util.as_array(efa_dm_response['servingLines'], 'lines'))

class DmLine(object):
    def __init__(self, data):
        self._data = data

    @property
    def route_id(self):
        return self._data['mode']['diva']['stateless']

    @property
    def network(self):
        return self._data['mode']['diva']['network']
    
    @property
    def route_type(self):        
        return self.route_type_and_colors[0]
    
    @property
    def route_type_and_colors(self):        
        return route_type_and_colors[int(line['mode']['type'])]
            
    @property
    def route_short_name(self):
        route_short_name = line['mode']['number']           
        if len(route_short_name) > 6 and not any(char.isdigit() for char in route_short_name):
            return ''
        else:
            return route_short_name

    @property
    def route_long_name(self):
        route_long_name = line['mode']['desc']
        if (route_long_name == '' and self.route_short_name == ''):
            route_long_name = line['mode']['destination']
        elif route_short_name == route_long_name:
            route_long_name = ''
        return route_long_name

class DmPoint(object):
    def __init__(self, data):
        self._data = data

    @property
    def id(self):
        return self._data['ref']['id']
    
    @property
    def name(self):
        return self._data['name'].replace('\n',' ')

    @property
    def coords(self):
        return self._data['ref']['coords']

class DmDeparture(object):

    def __init__(self, data):
        self._data = data

    @property
    def serving_line(self):
        return self._data['servingLine']

    @property
    def stop_id(self):
        return self._data['stopID']

    @property
    def route_id(self):
        return self.serving_line['stateless']

    @property
    def service_id(self):
        # first approximation for service_id: assume weekday, saturday, sunday service
        weekday = self._data['dateTime']['weekday']
        if weekday == '1':
            service_id = '7' 
        elif weekday == '6':
            service_id = '6'
        else:
            service_id = '1'
        return service_id

    @property
    def trip_id(self):
        '''Constructs a unique trip_id which is is built
        using the route_id, the schedule_id and its hour/minute
        at the first stop.'''
        route_id = self.route_id
        key = self.serving_line['key']
        service_id = self.service_id 
        hour_minute = self.departure_datetime
        return '{}-{}-{}-{}'.format(route_id, service_id, key, hour_minute)    
    
    @property
    def departure_datetime(self):
        if self._data['prevStopSeq']:
            prevStop = self._data['prevStopSeq'][0] if isinstance(self._data['prevStopSeq'], list) else self._data['prevStopSeq'] 
            #try:
            depDateTime = prevStop['ref']['depDateTime']
            hour_minute = util.convert_to_gtfs_time(*(depDateTime.split(' ')[1].split(':')))
        else:
            hour_minute = self.retrieve_hour_minute(trip['dateTime'])
        return hour_minute
 
    @property
    def direction(self):
        return self.serving_line['direction']

    @property
    def prev_stops(self):
        return [DmStop(stop) for stop in util.as_array_when_single_is_record(self._data,'prevStopSeq')]

    @property
    def onward_stops(self):
        return [DmStop(stop) for stop in util.as_array_when_single_is_record(self._data,'onwardStopSeq')]

    @property
    def is_on_demand_trip(self):
        line = self.serving_line
        return '715' == route_type_and_colors[int(line['motType'])][0]  
    
    @property
    def network(self):
        return self.serving_line['liErgRiProj']['network']

    @property
    def route_type_and_colors(self):
        line = self.serving_line
        return route_type_and_colors[int(line['motType'])]
   
    @property
    def route_type(self):
        return self.route_type_and_colors[0]

    @property
    def start_hour(self):
        return int(self.departure_datetime[-5:-3])

    @property
    def stop_time(self):
        self.retrieve_hour_minute(self._data['dateTime'], self.start_hour) + ':00'

    def retrieve_hour_minute(self, dateTime, start_hour_int = None):
        return util.convert_to_gtfs_time(dateTime['hour'],dateTime['minute'], start_hour_int)
  
class DmStop(object):
    def __init__(self, data):
        self._data = data

    @property
    def stop_id(self):
        stop_ref = self._data['ref']
        if 'pointGid' in stop_ref:
            id = stop_ref['pointGid']
        elif 'gid' in stop_ref:
            id = stop_ref['gid']
            #print('No pointGid for stop ',id,', falling back to gid')
        else:
            id = stop_ref['id']
            #print('Neither pointGid nor gid for stop ',id,', falling back to id')
        return id

    def is_point_gid_consistent_wih_gid(self):
        stop_ref = self._data['ref']
        return 'pointGid' in stop_ref and 'gid' in stop_ref and not stop_ref['pointGid'].startswith(stop_ref['gid'])
    
    @property
    def point_gid(self):
        stop_ref = self._data['ref']
        return stop_ref['pointGid'] if 'pointGid' in stop_ref else None  
    
    @property
    def gid(self):
        stop_ref = self._data['ref']
        return stop_ref['gid'] if 'gid' in stop_ref else None

    @property
    def platform(self):
        stop_ref = self._data['ref']
        return stop_ref['platform'] if 'platform' in stop_ref else ''

    @property
    def coords(self):
        stop_ref = self._data['ref']
        return stop_ref['coords']

    @property
    def name(self):
        return self._data['name'].replace('\n',' ')

    @property
    def id(self):
        return self._data['ref']['id']

    @property
    def arrival_date_time(self):
        stop_ref = self._data['ref']
        return stop_ref['arrDateTime'] if 'arrDateTime' in stop_ref else stop_ref['depDateTime']

    @property
    def departure_date_time(self):
        stop_ref = self._data['ref']
        return stop_ref['depDateTime'] if 'depDateTime' in stop_ref else stop_ref['arrDateTime']
