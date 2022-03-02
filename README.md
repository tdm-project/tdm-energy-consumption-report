# TDM Edge Energy Consumption Report

The TDM Edge Energy Consumption Report is an application specifically designed for the [TDM Edge Gateway](http://www.tdm-project.it/en/) devices paired with the EmonTx energy monitors. The application, running in the background, periodically
* collects the pulse measurements from the InfluxDB database to compute the consumption of electric energy;
* sends the data to a TDM web server, which produces a PDF report about the user consumptions and sends it to the user email address.


## Configurations
Settings are retrieved from both configuration file and command line.
Values are applied in the following order, the last overwriting the previous:

1. configuration file section `GENERAL` for the common options (`logging`, InfluxDB parameters, ...);
2. configuration file section `Energy_Consumption_Report` for both common and specific options;
3. command line options.


### Configuration file

`logging_level`
: threshold level for log messages (default: `20`)

`influxdb_host`
: hostname or address of the influx database (default: `influxdb`)

`influxdb_port`
: port of the influx database (default: `8086`)

`gps_location`
: GPS coordinates of the sensor expressed as latitude and longitude (default: `0.0,0.0`)

`measurement_ts`
: name of the InfluxDB *measurement* storing the EmonTx pulses time series

`email_address`
: email address where to receive the report prepared by the web service

`web_server_url`
: URL of the web service from which to request the energy consumption report

`sqlite_db`
: name of the SQLite database to store the report requests

`sqlite_db_table`
: name of the SQLite table to store the report requests

`reporting_interval`
: frequency, in seconds, between consecutive report requests

#### Options accepted in `GENERAL` section

* `logging_level`
* `influxdb_host`
* `influxdb_port`
* `gps_location`

In the following example of configuration file, the `logging_level` setting is overwritten to `20` only for the `Energy_Consumption_Report` application, while other applications use `10` as specified in the `GENERAL` section:

```ini
[GENERAL]
influxdb_host = influxdb
influxdb_port = 8086
gps_location = 0.0,0.0
logging_level = 10

[Energy_Consumption_Report]
measurement_ts = emontx3
email_address = username@example.com
web_server_url = https://tdm-or5.jicsardegna.it/get_report
sqlite_db = reporting.db
sqlite_db_table = report_requests
reporting_interval = 86400
```


### Command line

`-h`, `--help`
: show this help message and exit

`-c FILE`, `--config-file FILE`
: specify the config file

`-l LOGGING_LEVEL`, `--logging-level LOGGING_LEVEL`
: threshold level for log messages (default: `20`)

`--influxdb-host INFLUXDB_HOST`
: hostname or address of the influx database (default: `influxdb`)

`--influxdb-port INFLUXDB_PORT`
: port of the influx database (default: `8086`)

`--gps-location GPS_LOCATION`
: GPS coordinates of the sensor expressed as latitude and longitude (default: 0.0,0.0)

`--measurement-ts MEASUREMENT_TS`
: name of the time series containing the pulse measurements (default: `emontx3`)

`--email-address EMAIL_ADDRESS`
: email address where to receive the report prepared by the web service (default: `None`)

`--web-server-url WEB_SERVER_URL`
: URL of the web service from which to request the energy consumption report (default: `https://tdm-or5.jicsardegna.it/get_report`)

`--sqlite-db SQLITE_DB`
: name of the SQLite database to store the report requests (default: `reporting.db`)

`--sqlite-db-table SQLITE_DB_TABLE`
: name of the SQLite table to store the report requests (default: `report_requests`)

`--reporting-interval REPORTING_INTERVAL`
: frequency, in seconds, between consecutive report requests (default: `86400`)