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

import json
import pandas as pd
import requests
import sqlite3
from datetime import date, timedelta
from influxdb import DataFrameClient
from sys import exit

# ---------------------------------------------------------------------------- #

def get_first_timestamp(client: DataFrameClient, field_name: str,
                        measurement_name: str, dt: bool = False) -> str:
    """
    Return the timestamp corresponding to the first data point of "field" from
    "measurement" as a "datetime" or as a "string".
    """

    q = client.query(f"""
                         SELECT "{field_name}"
                         FROM "{measurement_name}"
                         LIMIT 1;
                      """)[measurement_name].index[0]
    if dt:
        return q
    else:
        return str(q)[:19]

# ---------------------------------------------------------------------------- #

def preprocessing(client: DataFrameClient, params: dict) -> pd.DataFrame:
    """
    Query EmonTx measurements from InfluxDB and prepare the dataframe containing
    the hourly-averaged power load measurements.
    """

    logger = params['LOGGER']
    measurement_ts = params['MEASUREMENT_TS']

    # ------------------------------------------------------------------------ #

    # Get timestamp of earlier pulse measurement
    first_timestamp = get_first_timestamp(client=client,
                                          field_name='pulse',
                                          measurement_name=measurement_ts)

    logger.debug(f'Earliest timestamp in "{measurement_ts}" '
                 f'time series: {first_timestamp}')

    # ------------------------------------------------------------------------ #

    # Query and estimate power consumption from the "pulse" time series
    query = f"""
            SELECT * FROM (
                           SELECT NON_NEGATIVE_DERIVATIVE(MAX(pulse), 1h) as power
                           FROM "{measurement_ts}"
                           WHERE time >= '{first_timestamp}'
                           GROUP BY time(1h)
                           FILL(null))
            WHERE power < 15000;
            """
    logger.debug(f'Querying field "power" from measurement "{measurement_ts}"...')

    try:
        # Query power consumption data
        y = client.query(query)[measurement_ts]
        logger.debug(f'Retrieved {y.shape[0]} measurements.')

        # Remove negative power values and outliers
        y = y[(y >= 0) & (y < 15000)]

        # Compute hourly mean of power absorption, i.e. energy consumption in kWh
        y = y.resample('1h').mean()
        logger.debug(f'Head of "y" time series: {y.head()}')

    except KeyError as e:
        logger.error(e)
        exit(0)

    if y.size < 2:
        logger.error(('A larger number of valid measurements is requested for '
                      'computing the power load forecasts.'))
        exit(0)

    return y

# ---------------------------------------------------------------------------- #

def sending(y: pd.DataFrame, params: dict):
    """
    Compose the HTTP post request and sent it to the TDM server
    """

    logger = params['LOGGER']
    url = params['WEB_SERVER_URL']
    email_address = params['EMAIL_ADDRESS']

    # Create body and headers of request
    body = json.dumps({'data': y.to_json(),
                       'email_address': email_address})
    headers = {'Content-Type': 'application/json'}

    # Send HTTP post request
    logger.debug('Sending data to TDM server...')
    return requests.post(url, headers=headers, data=body, verify=False)

# ---------------------------------------------------------------------------- #

def create_sqlite_table(params: dict):
    """
    Function for creating the table for storing the report requests.
    """

    logger = params['LOGGER']
    table_name = params['SQLITE_DB_TABLE']

    try:
        with sqlite3.connect(params['SQLITE_DB']) as connection:
            cursor = connection.cursor()
            cursor.execute(f"""CREATE TABLE {table_name} (timestamp TEXT,
                                                          response INTEGER)""")
    except sqlite3.OperationalError as e:
        logger.debug(f'Impossibile creare la tabella "{table_name}": "{e}"')

# ---------------------------------------------------------------------------- #

def check_report_status(params: dict) -> (bool, str):
    """
    Function to check whether a user has already requested the report for the
    specified month.
    """

    logger = params['LOGGER']
    table_name = params['SQLITE_DB_TABLE']
    today_date = date.today()

    # Set date to include measurements up to the last day of the previous month
    previous_month_date = date(today_date.year, today_date.month, day=1) - \
                               timedelta(days=1)

    try:
        with sqlite3.connect(params['SQLITE_DB']) as connection:
            cursor = connection.cursor()
            cursor.execute(f"""SELECT * FROM {table_name}""")
            records = cursor.fetchall()
    except Exception as e:
        logger.error('Impossibile leggere i record dalla tabella '
                     f'"{table_name}": "{e}"')

    timestamp = f'{previous_month_date.year}-{previous_month_date.month:02d}'
    return ((timestamp, 200) in records, timestamp)

# ---------------------------------------------------------------------------- #

def update_sqlite_db(params: dict, timestamp: str, status_code: int):
    """
    Update the table of the SQLite database when a report is sent successfully.
    """

    logger = params['LOGGER']
    table_name = params['SQLITE_DB_TABLE']

    try:

        with sqlite3.connect(params['SQLITE_DB']) as connection:
            cursor = connection.cursor()
            cursor.execute("""INSERT INTO report_requests (timestamp, response)
                              VALUES (?,?)""", (timestamp, status_code))

            connection.commit()
            logger.debug(f'Record ({timestamp}, {status_code}) successfully '
                         f'inserted in table "{table_name}"')
    except Exception as e:
        connection.rollback()
        logger.error(f'Could not insert record ({timestamp}, {status_code}) '
                     f'into table "{table_name}": "{e}"')

# ---------------------------------------------------------------------------- #
