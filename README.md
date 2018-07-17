# efa2gtfs

### Credits

This project was inspired by dmccue's efa2gtfs, a collection of helpful scripts to extract efa data, convert it into gtfs and visualize it.  

### Description

efa2gtfs extracts GTFS data from MDV's EFA.

MDV (Mentz Datenverarbeitung) is a german software company that makes transport and timetable software.

Their product known as "Elektronische Fahrplanauskunft" (EFA) provides an XML/JSON based API
https://de.wikipedia.org/wiki/Elektronische_Fahrplanauskunft
https://www.mentzdv.de

GTFS is the open General Transit Feed Specification, commonly used by google maps:
https://github.com/google/transitfeed/wiki

Please feel free to contribute, accepting pull requests

This project is in no way affiliated with any of the companies or products mentioned

### Related projects

EFA was previously known as diva and some projects exist for converting the previous format to gtfs
https://github.com/stkdiretto/diva2gtfs

OpenEFA has some documentation relating to the API
https://code.google.com/p/openefa

Golang client for EFA
https://github.com/michiwend/goefa

### EFA API documentation

- http://data.linz.gv.at/katalog/linz_ag/linz_ag_linien/fahrplan/LINZ_AG_Linien_Schnitstelle_EFA_v7_Echtzeit.pdf

- http://content.tfl.gov.uk/journey-planner-api-documentation.pdf
 
### How to run
    

    To run the source code, the following software is required:

    Python 3.5.1 (or higher)
    Additional packages to be installed via pip are specified in requirements.txt
    
    
#### Configuration
To import departures from an efa endpoint, configure the following parameters in the config.ini:

	[default]
	BaseURL: http://www.efa-bw.de/nvbw/
	SleepInterval: 0.1
	StopsFile: examples/stops.txt
	SkipUntilStop: 


| Parameter       | Description       | Example         |
| --------------- |:-----------------|:---------------|
| BaseURL       | URL of the efa endpoint  | http://www.efa-bw.de/nvbw/ |
| SleepInterval | seconds to wait before performing another request to the efa server| 0.1|
| StopsFile     | csv file with stop_ids in first column | examples/stops.txt |
| SkipUntilStop | First stop that should be requested, all stops before this are skipped |7023124 |

#### Crawling and caching efa departures
The download can be started as follows: 

    import datetime
    from efa2gtfs.crawler import EfaCrawler
     
    efa_crawler = efa2gtfs.crawler.EfaCrawler()
    start = datetime.datetime(2018,7, 13, 1, 0)
    end = datetime.datetime(2018,7, 16, 1, 0)
    efa_crawler.load_trips_between(start, end, './out/cached_efa_responses')

As start/endtime, a date/time range from friday (begin of service) to sunday (end of service) should be specified.

Note: depending on the number of stops, the total download size might become quite large. E.g. Baden-Württemberg takes ~150.000 files with a total size of 110GB, total import duration.  

#### Parsing trips and generating GTFS
To parse the dm_response files retrieved via the crawler and generate GTFS from these, proceed as follows:
    
    import efa2gtfs.converter
    
    e2g = efa2gtfs.converter.Converter()
	networks_to_ignore = ['vvs','frb','vrn']
    e2g.import_from_dir('examples/efa_files_cache', networks_to_ignore)
    e2g.export_gtfs('out/examples/gtfs.zip', 'out/gtfs')
    
### Progress 

From: https://developers.google.com/transit/gtfs/reference

| Filename        | Required          | Status          |
| --------------- |:-----------------:| ---------------:|
| agency.txt | y | Incomplete - Manual editing afterwards required |
| stops.txt | y | Complete |
| routes.txt | y | Complete |
| trips.txt | y | Complete |
| stop_times.txt | y | Complete |
| calendar.txt | y | Static - Rudimentary support |
| calendar_dates.txt | y | Static - Rudimentary support |
| fare_attributes.txt | n |  |
| fare_rules.txt | n |  |
| shapes.txt | n |  |
| frequencies.txt | n |  |
| transfers.txt | n |  |
| feed_info.txt | y | Static - Work in progress|

### Known issues
#### Efa data quality issues
For efa-bw, we encountered various data quality issues (e.g., flipped lat/lon for stop coordinates, wrong or not provided stop locations or ids, non-chronological stop ordering in stop sequences). To discover such issues, we recommend doing some quality checks using google's transitfeed/veedvalidator. To handle such data issues, we introduced various patching mechanisms, which can be configured. 
#### calender and calender_dates
Currently, efa2gtfs only differentiates between monday-friday, saturday and sunday trips, i.e., holydays or pre-holiday schedules are not taken into account yet.
#### start/end of service day
Currently, efa2gtfs assumes that trips starting between 0am and 4am belong to the preceding service day, which will not be correct for every route.
#### Feed info
From efa, we use the 'network' information to create an agency "stub" with limited data. The agencies information has to be added manually.
#### Feed validity period
The feed validity period is hard coded. If you want to change it, you currently need to edit the feed_info.txt manually. Ideally, it should be extracted from dmResponse dateTime/ttpFrom/ and dateTime/ttpTo.
### Further issues
Well, there will be further issues. If you encounter any, please file an issue report. Fixes or enhancement contributions are welcome.