def lpad(value, fill_char, length):
    pad = fill_char * (length - len(value))
    return pad + value

def convert_to_gtfs_time(hour_str, minute_str, start_hour_int = None):
    hour_int = int(hour_str)
    if hour_int < 4 or start_hour_int != None and start_hour_int > hour_int:
        hour_int += 24
    return lpad(str(hour_int), '0', 2) + ':' + lpad(minute_str, '0', 2)

def as_array(node, key):
    value = node[key]
    if isinstance(value, list):
        return value
    elif value == None:
        return []
    else:
        return [next(iter(value.values()))]
        
def as_array_when_single_is_record(node, key):
    value = node[key]
    if isinstance(value, list):
        return value
    elif value == None:
        return []
    else:
        return [value]
        
class TripSorter():
    
    SEQ_IDX = 1
    ARRIVAL_TIME_IDX = 2
    DEPARTURE_TIME_IDX = 3
        
    def sort(self, stop_times):
        '''Sorts a collection of stop_times by time, keeping the order of
            stops with the same time'''
        sorted_stop_times = []
        max_time = None
        for stop_time in stop_times:
            if not max_time or stop_time[self.ARRIVAL_TIME_IDX] >= max_time:
                sorted_stop_times.append(stop_time)
                max_time = stop_time[self.DEPARTURE_TIME_IDX]
            else:
                onward_stop_idx = self.index_first_onward_stop(sorted_stop_times, stop_time[self.ARRIVAL_TIME_IDX], stop_time[self.DEPARTURE_TIME_IDX])
                sorted_stop_times.insert(onward_stop_idx, stop_time)
        return sorted_stop_times
                     
    def index_first_onward_stop(self, stop_times, arr_time, dep_time):
        idx = 0
        for stop in stop_times:
            if stop[self.ARRIVAL_TIME_IDX] > dep_time or stop[self.DEPARTURE_TIME_IDX] > arr_time:
                return idx
            else:
                idx += 1
                
        return idx
