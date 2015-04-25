"""Database management
"""

import logging
import os
import sqlite3


LOG = logging.getLogger(__name__)


_SCHEMA = """
create table weather (
    id integer primary key autoincrement not null,
    date text,
    temperature float
);

create table readings (
    id integer primary key autoincrement not null,
    date text,
    temperature float,
    token text
);
"""


def open_db(filename):
    make_schema = not os.path.exists(filename)
    conn = sqlite3.connect(filename)
    conn.row_factory = sqlite3.Row
    if make_schema:
        LOG.info('Creating history database %s', filename)
        create_schema(conn)
        history_points = 0
    else:
        LOG.info('Loading history from %s', filename)
        history_points = num_entries(conn)
        LOG.info('Found %d history points', history_points)
    return (conn, history_points)


def create_schema(connection):
    """Create the schema in the open database.
    """
    connection.executescript(_SCHEMA)


def store_weather(connection, date, temperature):
    connection.execute(
        "insert into weather (date, temperature) values (?, ?);",
        (date, float(temperature))
    )


def store_sensor_reading(connection, date, temperature, token):
    connection.execute(
        "insert into readings (date, temperature, token) values (?, ?, ?);",
        (date, float(temperature), token),
    )


def num_entries(connection):
    cursor = connection.cursor()
    cursor.execute('select count(*) from weather;')
    results = cursor.fetchone()
    return results[0]


def get_history(connection):
    weather_cursor = connection.cursor()
    weather_cursor.execute('select * from weather order by id;')
    weather = weather_cursor.fetchall()

    readings_cursor = connection.cursor()
    readings_cursor.execute('select * from readings order by id;')
    readings = readings_cursor.fetchall()

    return (weather, readings)
