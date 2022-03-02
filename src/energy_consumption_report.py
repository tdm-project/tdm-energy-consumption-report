#!/usr/bin/env python
#
#  Copyright 2021, CRS4 - Center for Advanced Studies, Research and Development
#  in Sardinia
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

# ---------------------------------------------------------------------------- #

import argparse
import configparser
import logging
import sys
from influxdb import DataFrameClient
from time import time

import reporting
import continuous_scheduler

# ---------------------------------------------------------------------------- #

INFLUXDB_HOST = 'influxdb'        # INFLUXDB address
INFLUXDB_PORT = 8086               # INFLUXDB port
INFLUXDB_DB = 'Emon'               # INFLUXDB database
INFLUXDB_USER = 'root'             # INFLUXDB username
INFLUXDB_PASS = 'root'             # INFLUXDB password
GPS_LOCATION = '0.0,0.0'

MEASUREMENT_TS = 'emontx3'         # Time series containing measurements
EMAIL_ADDRESS = 'username@example.com'
WEB_SERVER_URL = 'https://tdm-or5.jicsardegna.it/get_report'
SQLITE_DB = '/sqlite_db/reporting.db'
SQLITE_DB_TABLE = 'report_requests'
REPORTING_INTERVAL = 60*60*24

APPLICATION_NAME = 'Energy_Consumption_Report'

# ---------------------------------------------------------------------------- #

def str_to_bool(parameter):
    """
    Utility for converting a string to its boolean equivalent.
    """
    if isinstance(parameter, bool):
        return parameter
    if parameter.lower() in {'false', 'f', '0', 'no', 'n'}:
        return False
    elif parameter.lower() in {'true', 't', '1', 'yes', 'y'}:
        return True
    raise ValueError(f'"{parameter}" is not a valid boolean value.')

# ---------------------------------------------------------------------------- #

def configuration_parser(p_args=None):
    pre_parser = argparse.ArgumentParser(add_help=False)

    pre_parser.add_argument(
        '-c', '--config-file', dest='config_file', action='store',
        type=str, metavar='FILE',
        help='specify the config file')

    args, remaining_args = pre_parser.parse_known_args(p_args)

    v_general_config_defaults = {'logging_level': logging.INFO,
                                 'influxdb_host': INFLUXDB_HOST,
                                 'influxdb_port': INFLUXDB_PORT,
                                 'influxdb_database': INFLUXDB_DB,
                                 'influxdb_username': INFLUXDB_USER,
                                 'influxdb_password': INFLUXDB_PASS,
                                 'gps_location': GPS_LOCATION}

    v_specific_config_defaults = {'measurement_ts': MEASUREMENT_TS,
                                  'email_address': EMAIL_ADDRESS,
                                  'web_server_url': WEB_SERVER_URL,
                                  'sqlite_db': SQLITE_DB,
                                  'sqlite_db_table': SQLITE_DB_TABLE,
                                  'reporting_interval': REPORTING_INTERVAL}

    v_config_section_defaults = {'GENERAL': v_general_config_defaults,
                                 APPLICATION_NAME: v_specific_config_defaults}

    # Default config values initialization
    v_config_defaults = {}
    v_config_defaults.update(v_general_config_defaults)
    v_config_defaults.update(v_specific_config_defaults)

    if args.config_file:
        _config = configparser.ConfigParser()
        _config.read_dict(v_config_section_defaults)
        _config.read(args.config_file)

        # Filter out GENERAL options not listed in v_general_config_defaults
        _general_defaults = {_key: _config.get('GENERAL', _key) for _key in
                             _config.options('GENERAL') if _key in
                             v_general_config_defaults}

        # Updates the defaults dictionary with general and application specific
        # options
        v_config_defaults.update(_general_defaults)
        v_config_defaults.update(_config.items(APPLICATION_NAME))

    parser = argparse.ArgumentParser(parents=[pre_parser],
                          description=('Read pulse measurements from InfluxDB '
                                       'and send them to the TDM web service '
                                       'to receive a report about the '
                                       'consumption of electric energy.'),
                          formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.set_defaults(**v_config_defaults)

    parser.add_argument(
        '-l', '--logging-level', dest='logging_level', action='store',
        type=int,
        help='threshold level for log messages (default: {})'
             .format(logging.INFO))

    parser.add_argument(
        '--influxdb-host', dest='influxdb_host', action='store',
        type=str,
        help='hostname or address of the influx database (default: {})'
             .format(INFLUXDB_HOST))

    parser.add_argument(
        '--influxdb-port', dest='influxdb_port', action='store',
        type=int,
        help='port of the influx database (default: {})'.format(INFLUXDB_PORT))

    parser.add_argument(
        '--gps-location', dest='gps_location', action='store',
        type=str,
        help=('GPS coordinates of the sensor expressed as latitude and '
              'longitude (default: {})').format(GPS_LOCATION))

    parser.add_argument(
        '--measurement-ts', dest='measurement_ts', action='store',
        type=str,
        help=('name of the time series containing the pulse measurements '
              '(default: {})').format(MEASUREMENT_TS))

    parser.add_argument(
        '--email-address', dest='email_address', action='store',
        type=str,
        help=('email address where to receive the report prepared by the '
              'web service (default: {})').format(EMAIL_ADDRESS))

    parser.add_argument(
        '--web-server-url', dest='web_server_url', action='store',
        type=str,
        help=('URL of the web service from which to request the energy '
              'consumption report (default: {})').format(WEB_SERVER_URL))

    parser.add_argument(
        '--sqlite-db', dest='sqlite_db', action='store',
        type=str,
        help=('name of the SQLite database to store the status of the '
              'monthly reports (default: {})').format(SQLITE_DB))

    parser.add_argument(
        '--sqlite-db-table', dest='sqlite_db_table', action='store',
        type=str,
        help=('name of the SQLite table to store the status of the '
              'monthly reports (default: {})').format(SQLITE_DB_TABLE))

    parser.add_argument(
        '--reporting-interval', dest='reporting_interval', action='store',
        type=int,
        help=('frequency, in seconds, between consecutive report requests '
              '(default: {} seconds)').format(REPORTING_INTERVAL))

    return parser.parse_args(remaining_args)

# ---------------------------------------------------------------------------- #

def reporting_task(params: dict):

    logger = params['LOGGER']
    logger.info('Starting reporting task...')
    start_time = time()

    # Create SQLite table, if necessary
    reporting.create_sqlite_table(params)

    # Check whether the email has been successfully sent for the previous month
    report_received, previous_month_date = reporting.check_report_status(params)

    # Send the data and request a report if it has not been received yet
    if not report_received:

        # Connect to the database "Emon" in InfluxDB
        client = DataFrameClient(host=params['INFLUXDB_HOST'],
                                 port=params['INFLUXDB_PORT'],
                                 username=params['INFLUXDB_USER'],
                                 password=params['INFLUXDB_PASS'],
                                 database=params['INFLUXDB_DB'])

        # Query and preprocess power load measurements
        y = reporting.preprocessing(client, params)

        try:
            # Send the data to the TDM server
            response = reporting.sending(y, params)

            logger.debug(f'Response status code: {response.status_code}')
            logger.debug(f'Response message: {response.json()}')

            # Update database in case of positive response from the TDM server
            if response.status_code == 200:
                reporting.update_sqlite_db(params, previous_month_date,
                                           response.status_code)

        except Exception as e:
            logger.error(e)
        finally:
            logger.info('Reporting task completed in '
                        f'{round(time()-start_time)} seconds!')
            client.close()
    else:
        logger.info(f'The report for month "{previous_month_date}" '
                    'had been already sent.')

# ---------------------------------------------------------------------------- #

def main():

    # Initializes the default logger
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO)
    logger = logging.getLogger(APPLICATION_NAME)

    # Checks the Python Interpeter version
    if (sys.version_info < (3, 0)):
        logger.error('Python 3 is requested! Leaving the program.')
        sys.exit(-1)

    # Parse arguments
    args = configuration_parser()

    logger.setLevel(args.logging_level)
    logger.info(f'Starting application "{APPLICATION_NAME}"...')
    logger.debug(f'Arguments: {vars(args)}')

    v_latitude, v_longitude = map(float, args.gps_location.split(','))

    v_influxdb_host = args.influxdb_host
    v_influxdb_port = args.influxdb_port

    v_influxdb_database = args.influxdb_database
    v_influxdb_username = args.influxdb_username
    v_influxdb_password = args.influxdb_password

    # Check if "Emon" database exists
    _client = DataFrameClient(host=v_influxdb_host,
                              port=v_influxdb_port,
                              username=v_influxdb_username,
                              password=v_influxdb_password,
                              database=v_influxdb_database)

    _dbs = _client.get_list_database()
    logger.debug(f'List of InfluxDB databases: {_dbs}')
    if v_influxdb_database not in [_d['name'] for _d in _dbs]:
        logger.info(f'InfluxDB database "{v_influxdb_database}" not found. '
                    'Creating a new one.')
        _client.create_database(v_influxdb_database)

    _client.close()

    # Pack all parameters in a dictionary
    _userdata = {'LOGGER': logger,
                 'LATITUDE': v_latitude,
                 'LONGITUDE': v_longitude,
                 'INFLUXDB_HOST': v_influxdb_host,
                 'INFLUXDB_PORT': v_influxdb_port,
                 'INFLUXDB_USER': v_influxdb_username,
                 'INFLUXDB_PASS': v_influxdb_password,
                 'INFLUXDB_DB': v_influxdb_database,
                 'MEASUREMENT_TS': args.measurement_ts,
                 'EMAIL_ADDRESS': args.email_address,
                 'WEB_SERVER_URL': args.web_server_url,
                 'SQLITE_DB': args.sqlite_db,
                 'SQLITE_DB_TABLE': args.sqlite_db_table,
                 'REPORTING_INTERVAL': args.reporting_interval}

    # Instantiate the scheduler and repeatedly run the "reporting task"
    # 24 hours after its previous execution
    _main_scheduler = continuous_scheduler.MainScheduler()
    _main_scheduler.add_task(reporting_task, 0, args.reporting_interval, 0,
                             _userdata)
    _main_scheduler.start()

# ---------------------------------------------------------------------------- #

if __name__ == '__main__':
    main()

# ---------------------------------------------------------------------------- #
