import argparse
import datetime
import logging
import logging.handlers
import os
import time

import plotly.plotly as py
from plotly.graph_objs import Scatter, Layout, Figure, YAxis
from temperusb import TemperHandler
import yaml
import yweather


# Measure every 5 minutes
DEFAULT_FREQUENCY = 5
# Keep a week's worth of measurements
DEFAULT_RETENTION_PERIOD = 7
# Sorry, Europe
DEFAULT_UNITS = 'fahrenheit'

LOG = logging.getLogger('')


def setup_logging(log_file, verbose):
    # Configure logging to minimize disk space
    LOG.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=4096,
        backupCount=1,
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    LOG.addHandler(handler)
    logging.captureWarnings(True)

    if verbose:
        out = logging.StreamHandler()
        out.setFormatter(logging.Formatter('%(message)s'))
        out.setLevel(logging.DEBUG)
        LOG.addHandler(out)
    else:
        # Quiet the chatty requests module
        logging.getLogger('requests').setLevel(logging.WARN)


def get_sensors():
    th = TemperHandler()
    devs = th.get_devices()
    if not devs:
        raise RuntimeError('No temperature sensors found')
    return devs


def create_plot(username, api_key,
                weather_token,
                sensor_tokens, sensor_names,
                title, units,
                max_points):
    py.sign_in(username, api_key)
    traces = [
        Scatter(
            x=[],
            y=[],
            name=n,
            stream={
                'token': t,
                'maxpoints': max_points,
            }
        )
        for t, n in zip(sensor_tokens, sensor_names)
    ]
    traces.append(
        Scatter(
            x=[],
            y=[],
            name='Outside Temperature',
            stream={
                'token': weather_token,
                'maxpoints': max_points,
            }
        )
    )
    layout = Layout(
        title=title,
        yaxis=YAxis(
            title='Degrees %s' % units.title(),
        ),
        showlegend=True,
    )
    fig = Figure(data=traces, layout=layout)
    plot_url = py.plot(fig, filename=title, extend=True, auto_open=False)
    LOG.info('Output graph visible at %s', plot_url)

    sensor_streams = [
        py.Stream(t)
        for t in sensor_tokens
    ]
    for s in sensor_streams:
        s.open()

    weather_stream = py.Stream(weather_token)
    weather_stream.open()

    return sensor_streams, weather_stream


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--config-file', '-c',
        default=os.path.expanduser('~/.tempmon/tempmon.yaml'),
        help='Where to load configuration settings. Defaults to %(default)s',
    )
    parser.add_argument(
        '--log-file', '-l',
        default=os.path.expanduser('~/.tempmon/tempmon.log'),
        help='Where to write logs. Defaults to %(default)s',
    )
    parser.add_argument(
        '--pid-file', '-p',
        default=None,
        help='Where to write the pid file. Defaults to not writing one.',
    )
    parser.add_argument(
        '--history-file',
        default=None,
        help='Where to write the recording history for playback',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        default=False,
    )
    args = parser.parse_args()

    if args.pid_file:
        with open(args.pid_file, 'w') as f:
            f.write('%s\n' % os.getpid())

    setup_logging(args.log_file, args.verbose)

    LOG.info('Loading configuration from %s', args.config_file)
    with open(args.config_file) as f:
        config = yaml.load(f)
    plotly = config['plotly']
    username = plotly['username']
    api_key = plotly['api-key']
    sensor_tokens = plotly['sensor-stream-tokens']
    title = config.get('graph-title', 'Temperature')
    retention_period = config.get('retention-period', DEFAULT_RETENTION_PERIOD)
    frequency = config.get('frequency', DEFAULT_FREQUENCY)
    if frequency < 1:
        LOG.warning('Cannot poll more often than 1 minute')
        frequency = 1
    units = config.get('units', DEFAULT_UNITS)
    LOG.info('Polling every %s minutes, keeping %s days',
             frequency, retention_period)
    weather_stream_token = plotly['weather-stream-token']
    weather = config['weather']
    place = weather['place']
    LOG.info('Monitoring weather at %r', place)

    # Make sure we can communicate with the devices
    devs = get_sensors()
    sensor_names = []
    if len(devs) > 1:
        name_format = 'Sensor %(num)s (%(bus)s/%(ports)s)'
    else:
        name_format = 'Sensor'
    for n, dev in enumerate(devs, 1):
        bus = dev.get_bus()
        ports = dev.get_ports()
        LOG.info('Found sensor on bus %s at port %s',
                 bus, ports)
        name = name_format % {'bus': bus, 'ports': ports, 'num': n}
        sensor_names.append(name)

    # Connect to weather service
    weather_client = yweather.Client()
    location_id = weather_client.fetch_woeid(place)

    # Make sure our plotly login details work
    max_points = 24 * (60 / frequency) * retention_period
    sensor_streams, weather_stream = create_plot(
        username,
        api_key,
        weather_stream_token,
        sensor_tokens,
        sensor_names,
        title,
        units,
        max_points,
    )

    history_file = (
        args.history_file
        or
        os.path.join(os.path.dirname(args.config_file), 'tempmon.dat')
    )
    if os.path.exists(history_file):
        LOG.info('Loading history from %s', history_file)
        with open(history_file, 'r') as f:
            history = yaml.load(f)
        LOG.info('Found %d history points', len(history))
        if history:
            LOG.info('Posting historical data')
            for entry in history:
                x = entry['date']
                try:
                    weather_stream.write({'x': x, 'y': entry['weather']})
                except Exception:
                    LOG.warning('Could not update plotly', exc_info=True)
                for stream, sensor_entry in zip(sensor_streams,
                                                entry['sensors']):
                    try:
                        stream.write({'x': x, 'y': sensor_entry['temp']})
                    except Exception:
                        LOG.warning('Could not update plotly', exc_info=True)
    else:
        history = []
        LOG.info('History file %s not found', history_file)

    LOG.info('Starting polling')
    delay = frequency * 60
    while True:
        x = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        history_entry = {
            'date': x,
            'weather': None,
            'sensors': []
        }
        # Reported temperature from weather service
        try:
            weather = weather_client.fetch_weather(location_id, metric=False)
            temp = weather['condition']['temp']
            history_entry['weather'] = temp
        except Exception:
            LOG.warning('Could not get weather report', exc_info=True)
        else:
            try:
                weather_stream.write({'x': x, 'y': temp})
            except Exception:
                LOG.warning('Could not update plotly', exc_info=True)
        # Temperature sensors
        for dev, stream, token in zip(devs, sensor_streams, sensor_tokens):
            try:
                temp = dev.get_temperature(format=units)
                history_entry['sensors'].append({'temp': temp, 'token': token})
            except Exception:
                LOG.warning('Could not read temperature', exc_info=True)
                continue
            try:
                stream.write({'x': x, 'y': temp})
            except Exception:
                LOG.warning('Could not update plotly', exc_info=True)
                continue
        # Save the history
        history.append(history_entry)
        history = history[-1 * max_points:]
        with open(history_file, 'w') as f:
            yaml.dump(history, f)
        # delay between stream posts is expressed as a frequency
        # in minutes
        time.sleep(delay)


if __name__ == '__main__':
    main()
