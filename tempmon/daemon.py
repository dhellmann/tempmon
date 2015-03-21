import argparse
import datetime
import logging
import logging.handlers
import os
import time

import plotly.plotly as py
from plotly.graph_objs import Scatter, Layout, Figure
import yaml
from temperusb import TemperHandler

# Measure every 5 minutes
DEFAULT_FREQUENCY = 5
# Keep a week's worth of measurements
DEFAULT_RETENTION_PERIOD = 7
# Sorry, Europe
DEFAULT_UNITS = 'fahrenheit'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--config-file', '-c',
        default=os.path.expanduser('~/.tempmon/tempmon.yaml'),
        help='Where to load configuration settings. Defaults to %(default)s',
    )
    parser.add_argument(
        '--log-file',
        default=os.path.expanduser('~/.tempmon/tempmon.log'),
        help='Where to write logs. Defaults to %(default)s',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        default=False,
    )
    args = parser.parse_args()

    # Configure logging to minimize disk space
    log = logging.getLogger('')
    log.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(
        args.log_file,
        maxBytes=4096,
        backupCount=1,
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    log.addHandler(handler)
    logging.captureWarnings(True)

    if args.verbose:
        out = logging.StreamHandler()
        out.setFormatter(logging.Formatter('%(message)s'))
        out.setLevel(logging.DEBUG)
        log.addHandler(out)
    else:
        # Quiet the chatty requests module
        logging.getLogger('requests').setLevel(logging.WARN)

    log.info('Loading configuration from %s', args.config_file)
    with open(args.config_file) as f:
        config = yaml.load(f)
    username = config['username']
    api_key = config['api-key']
    stream_tokens = config['stream-tokens']
    title = config.get('graph-title', 'Temperature')
    retention_period = config.get('retention-period', DEFAULT_RETENTION_PERIOD)
    frequency = config.get('frequency', DEFAULT_FREQUENCY)
    if frequency < 1:
        log.warning('Cannot poll more often than 1 minute')
        frequency = 1
    units = config.get('units', DEFAULT_UNITS)
    log.info('Polling every %s minutes, keeping %s days',
             frequency, retention_period)

    # Make sure we can communicate with the devices
    th = TemperHandler()
    devs = th.get_devices()
    if not devs:
        raise RuntimeError('No temperature sensors found')
    for dev in devs:
        log.info('Found sensor on bus %s at port %s',
                 dev.get_bus(), dev.get_ports())

    # Make sure our plotly login details work
    py.sign_in(username, api_key)
    max_points = 24 * (60 / frequency) * retention_period
    traces = [
        Scatter(
            x=[],
            y=[],
            stream={
                'token': t,
                'maxpoints': max_points,
            }
        )
        for t in stream_tokens
    ]
    layout = Layout(title=title)
    fig = Figure(data=traces, layout=layout)

    streams = [
        py.Stream(t)
        for t in stream_tokens
    ]
    for s in streams:
        s.open()

    log.info('Output graph visible at %s', py.plot(fig, filename=title))
    delay = frequency * 60

    log.info('Starting polling')
    while True:
        x = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        for dev, stream in zip(devs, streams):
            try:
                temp = dev.get_temperature(format=units)
            except Exception:
                log.warning('Could not read temperature', exc_info=True)
                break
            try:
                stream.write({'x': x, 'y': temp})
            except Exception:
                log.warning('Could not update plotly', exc_info=True)
                break
        # delay between stream posts is expressed as a frequency
        # in minutes
        time.sleep(delay)


if __name__ == '__main__':
    main()
