import csv
from zipfile import ZipFile, ZIP_DEFLATED

class GtfsStore():
    STOP_TIME_TRIP_ID_IDX = 0
    STOP_TIME_SEQ_NR = 1
    STOP_TIME_STOP_ID_IDX = 4
    
    agencies = {}
    stops = {}
    routes = {}
    trips = {}
    stop_times = {}
    calendar_dates = []
    
    agencies_fields = 'agency_id,agency_name,agency_url,agency_timezone'
    feed_info_fields = 'feed_id,feed_publisher_name,feed_publisher_url,feed_lang'
    calendar_fields = 'service_id,start_date,end_date,monday,tuesday,wednesday,thursday,friday,saturday,sunday'
    calendar_dates_fields = 'date,service_id,exception_type'
    route_fields = 'route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_color,route_text_color'
    trip_fields = 'trip_id,route_id,service_id,trip_headsign' 
    #stop_fields = 'stop_id,stop_name,stop_desc,stop_lat,stop_lon,stop_url,location_type,parent_station'
    stop_fields = 'stop_id,stop_name,platform_code,stop_lat,stop_lon,stop_source'
    stop_time_fields = 'trip_id,stop_sequence,arrival_time,departure_time,stop_id,stop_time_source,pickup_type,drop_off_type'
    
   
    def init_static_content(self):
        self.feed_info= {'nvbv': ['nvbv','mfdz','http://mfdz.de/','de']}
        self.calendar = {'1': ['1', '20180601','20181209', 1, 1, 1, 1, 1, 0, 0],
                         '6': ['6', '20180601','20181209', 0, 0, 0, 0, 0, 1, 0],
                         '7': ['7', '20180601','20181209', 0, 0, 0, 0, 0, 0, 1]}
        self.calendar_dates = [
            ['20181003', '7', '1'],['20181003', '1', '2'], # Tag der deutschen Einheit
            ['20181101', '7', '1'],['20181101', '1', '2'], # Allerheiligen
            ['20181225', '7', '1'],['20181225', '1', '2'], # 1. Weihnachtsfeiertag
            ['20181226', '7', '1'],['20181226', '1', '2'],] # 2. Weihnachtsfeiertag
        
    def cache(self, entitities, entity_store, key_columns = 1):
        '''Caches entities in entity_store, using the concatenated key column values as key'''
        for entity in entitities:
            if key_columns == 2:
                # TODO Currently, only stop_times uses 2 key_columns
                # so we perform stop_times dependend workaround for stop_id here
                key = entity[0]+"#"+str(entity[1])
                # current_stop has no pointGid, so we'll override the stop info as soon as we found it
                if not key in entity_store or (self.is_stop_id_a_point_gid(entity) and self.is_stop_id_a_point_gid(entity_store[key])):
                    entity_store[key] = entity
            else:
                key = entity[0]
                if not key in entity_store:
                    entity_store[key] = entity
    
    def is_stop_times_extracted(self, trip_id):
        return trip_id+"#1" in self.stop_times
        
    def is_stop_id_a_point_gid(self, stop_time):
        return ':' in stop_time[self.STOP_TIME_STOP_ID_IDX]
        
    def stops_without_point_gid(self, trip_id):
        stop_times_without_point_gid = []
        stop_seq = 1
        while True:
            stop_time_id = str(trip_id)+"#"+str(stop_seq)
            if stop_time_id not in self.stop_times:
                return stop_times_without_point_gid
            stop_time = self.stop_times[stop_time_id]
            if not self.is_stop_id_a_point_gid(stop_time):
                stop_times_without_point_gid.append(stop_time)
            stop_seq += 1
            
    def update_stop_id(self, stop, stop_id):
        key= str(stop[0])+"#"+str(stop[1])
        self.stop_times[key][self.STOP_TIME_STOP_ID_IDX] = stop_id
                
        
    def export(self, gtfszip_filename, gtfsfolder):
        
        self._write_csvfile(gtfsfolder, 'agency.txt', self.agencies, self.agencies_fields)
        self._write_csvfile(gtfsfolder, 'feed_info.txt', self.feed_info, self.feed_info_fields)
        self._write_csvfile(gtfsfolder, 'routes.txt', self.routes, self.route_fields)
        self._write_csvfile(gtfsfolder, 'trips.txt', self.trips, self.trip_fields)
        self._write_csvfile(gtfsfolder, 'calendar.txt', self.calendar, self.calendar_fields)
        self._write_csvfile(gtfsfolder, 'calendar_dates.txt', self.calendar_dates, self.calendar_dates_fields)
        self._write_csvfile(gtfsfolder, 'stops.txt', self.stops, self.stop_fields)
        self._write_csvfile(gtfsfolder, 'stop_times.txt', self.stop_times, self.stop_time_fields)
        self._zip_files(gtfszip_filename, gtfsfolder)
    
    def _zip_files(self, gtfszip_filename, gtfsfolder):
        gtfsfiles = ['agency.txt', 'feed_info.txt', 'routes.txt', 'trips.txt', 
                'calendar.txt', 
                'calendar_dates.txt', 
                'stops.txt', 'stop_times.txt']
        with ZipFile(gtfszip_filename, 'w', compression=ZIP_DEFLATED) as gtfszip:
            for gtfsfile in gtfsfiles:
                gtfszip.write(gtfsfolder+'/'+gtfsfile, gtfsfile)
  
    def _write_csvfile(self, gtfsfolder, filename, content, headers):
        with open(gtfsfolder+"/"+filename, 'w', newline="\n", encoding="utf-8") as csvfile:
            self._write_csv(csvfile, content, headers)
    
    def _write_csv(self, csvfile, content, headers):
        fieldnames = headers.split(',')
        writer = csv.DictWriter(csvfile, fieldnames)
        writer.writeheader()
        if isinstance(content, list):
            for entity in content:
                writer.writerow(dict(zip(fieldnames,entity)))
        else:
            for key in sorted(content):
                entity = content[key]
                writer.writerow(dict(zip(fieldnames,entity)))
    
    def filter_unused_stops(self):
        used_stops = {}
        for stop_time in self.stop_times.values():
            stopID = stop_time[4].strip()
            if stopID in self.stops:
                used_stops[stopID] = self.stops[stopID]    
            else: 
                print('Stop ', stopID,' used, but not stored', len(stopID))
        self.stops = used_stops
