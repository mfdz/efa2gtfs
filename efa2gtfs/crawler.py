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

import configparser, requests, datetime, time, os, json

from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter



class EfaCrawler():

    def __init__(self, config_file = 'config.ini', config_section = 'default'):
        self._config = config = configparser.ConfigParser()
        self._config.read(config_file)
        self._config_section = config_section
        self._session = requests.Session()

        retries = Retry(total=10,
                backoff_factor=0.1,
                status_forcelist=[ 500, 502, 503, 504 ])

        self._session.mount('http://', HTTPAdapter(max_retries=retries))

    @property
    def skip_until_stop(self):
        return self._config.get(self._config_section,'SkipUntilStop')

    @property
    def efa_base_url(self):
        return self._config.get(self._config_section,'BaseURL')

    @property
    def sleep_interval(self):
        return float(self._config.get(self._config_section,'SleepInterval'))

    @property
    def stops_file(self):
        return self._config.get(self._config_section,'StopsFile')
        

    def _save(self, result_file_name, response):
        with open(result_file_name, "w", encoding="utf-8" ) as result_file:
            result_file.write(json.dumps(response, sort_keys = False, indent = 2))
        print("Wrote {}".format(result_file_name))

    def _as_idt_date_time(self, a_datetime):
        return (a_datetime.strftime('%y%m%d'),
            a_datetime.strftime('%H%M'))
        
    def _get_max_dep_datetime(self, root):
        '''Iterate over all departures in departurelist and extract maximum datetime'''
        if not 'departureList' in root or root['departureList'] is None:
            return None
        if isinstance(root['departureList'], list):
            departures = root['departureList']
        else:
            departures = [root['departureList']['departure']]
        last_departure = departures[-1]
        dt = last_departure['dateTime']
        return datetime.datetime(
            int(dt['year']), 
            int(dt['month']),
            int(dt['day']),
            int(dt['hour']),
            int(dt['minute'])) 

    def _get_route(self, baseurl,id, itd_date, itd_time):

        payload = {
            'locationServerActive': '1',
            'appCache': 'true',
            'googleAnalytics': 'false',
            'type_dm': 'stop',
            'limit': '999999',
            'outputFormat': 'JSON',
            #'coordListOutputFormat': 'STRING',
            'coordOutputFormat': 'WGS84',
            'language': 'de',
            'depType': 'stopEvents',
            'mode': 'direct',
            'includeCompleteStopSeq': '1',
            'name_dm': str(id),
            'itdDate': itd_date,
            'itdTime': itd_time,
            #'useProxFootSearch': '0',
            #'useAllStops': '1',
            #'useRealtime': '0',
            #'mergeDep': '1',
            #'useAllStops': '1',
            #'maxTimeLoop': '1',
            #'canChangeMOT': '0',
            #'useRealtime': '1',
            #'imparedOptionsActive': '1',
            #'excludedMeans': 'checkbox',
            #'useProxFootSearch': '0',
            #'itOptionsActive': '1',
            #'trITMOTvalue100': '15',
            #'lineRestriction': '400',
            #'changeSpeed': 'normal',
            #'routeType': 'LEASTINTERCHANGE',
            #'ptOptionsActive': '1',
            #'snapHouseNum': '1'
            
        }
        # http://www.efa-bw.de/nvbw/XML_DM_REQUEST?locationServerActive=1&appCache=true&googleAnalytics=false&type_dm=stop&limit=999999&outputFormat=JSON&coordOutputFormat=WGS84&language=de&depType=stopEvents&mode=direct&includeCompleteStopSeq=1&name_dm=2506793&itdDate=20180611&itdTime=1752
        response = self._session.get(baseurl + 'XML_DM_REQUEST', params=payload)
        response.encoding='utf-8'
        
        return response.json()

    def stops_from_file(self, fname, skip_until_stop_id = None):
        '''A generator function returning all stop_ids from a csv file whose first column is the stop_id.
        If skip_until_stop_id is provided, all stop_ids are skipped until the first time a stop_id of the given value is encountered.'''
        with open(fname, "r", encoding="utf-8") as f:
            content = f.readlines()
            for line in content:
                stop_id = line.partition(',')[0].replace('"','')
                if stop_id == 'stop_id' or skip_until_stop_id and not stop_id == skip_until_stop_id:
                    print ('Skipped {}'.format(stop_id))
                    continue
                skip_until_stop_id = None
                yield stop_id

    def load_trips_between(self, start_datetime, end_datetime, data_dir, stops_generator = None):
        '''For every stop_id returned by the provided stops_generator (or configured StopsFile), all departures for the period between start_datetime and end_datetime are retrieved and cached json files in data_dir.'''
        if not stops_generator:
            stops_generator = self.stops_from_file(self.stops_file, self.skip_until_stop)

        if not os.path.exists(data_dir): os.makedirs(data_dir)

        for stop_id in stops_generator:
            try:
                counter = 1
                (itd_date, itd_time) = self._as_idt_date_time(start_datetime)
                former_last_dep_datetime = None
                while True:
                    response = self._get_route(self.efa_base_url, int(stop_id), itd_date, itd_time) 
                    result_file_name = data_dir+"/"+stop_id+"_"+str(counter)+".json"
                    self._save(result_file_name, response)
                    time.sleep(self.sleep_interval)
                    
                    last_dep_datetime = self._get_max_dep_datetime(response)
                    # if results past intended range were returned or no new departures returned for this stop, leave
                    if last_dep_datetime is None or last_dep_datetime > end_datetime or former_last_dep_datetime == last_dep_datetime:
                        break
                    else:
                        # otherwise increment date/time and request again
                        (itd_date, idt_time) = self._as_idt_date_time(last_dep_datetime)
                        counter += 1
                        former_last_dep_datetime = last_dep_datetime
                        
            except ValueError as err:
                print ("\nValue Error! " + str(stop_id) + str(err))

