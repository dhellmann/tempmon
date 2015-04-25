#!/usr/bin/env python

import argparse
import sqlite3

import yaml

from tempmon import db

parser = argparse.ArgumentParser()
parser.add_argument('infile')
parser.add_argument('outfile')
args = parser.parse_args()

print('Setting up database %s' % args.outfile)
conn, ignore = db.open_db(args.outfile)

print('Reading input file %s' % args.infile)
with open(args.infile, 'r') as f:
    indata = yaml.load(f)

print('Processing %d entries' % len(indata))
for entry in indata:
    db.store_weather(conn, entry['date'], entry['weather'])
    for sensor in entry['sensors']:
        db.store_sensor_reading(conn, entry['date'], sensor['temp'], sensor['token'])
    conn.commit()
