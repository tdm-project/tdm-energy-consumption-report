#!/bin/sh

cd ${APP_HOME}
. venv/bin/activate
python3 src/energy_consumption_report.py $@
