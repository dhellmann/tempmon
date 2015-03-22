=======================================
 tempmon -- Temperature monitor daemon
=======================================

tempmon uses temperusb_ to read temperature value from TEMPer_ sensors
on the USB bus and OWM_ to find the local reported temperature and
publishes the results to `plot.ly`_

.. _temperusb: https://pypi.python.org/pypi/temperusb
.. _TEMPer: http://www.amazon.com/gp/product/B002VA813U/ref=as_li_tl?ie=UTF8&camp=1789&creative=390957&creativeASIN=B002VA813U&linkCode=as2&tag=hellflynet-20&linkId=VHDXEZ2QB74BXBM5
.. _plot.ly: https://plot.ly
.. _OWM: http://openweathermap.org/

Setup
=====

#. Sign up for a plot.ly account.
#. From your `plot.ly settings page`_, create one stream token per
   sensor device
#. Install tempmon and its dependencies. A virtualenv works fine for
   this.
#. Sign up for a OWM account and find your API key on `your settings
   page <http://openweathermap.org/my>`__.
4. Create a configuration file using YAML syntax and containing at
   least the basic plot.ly authentication data:

    ::

      plotly:
        username:
        api-key:
        stream-tokens:
          - token1
          - token2
      weather:
        api-key:
        place: "City, State"

5. Run ``tempmon -c $CONFIG_FILENAME``.  Add ``-v`` to see the log
   output on the console for debugging.

Other Configuration Settings
============================

graph-title

  The title of the graph defaults to "Temperature".

retention-period

  The number of days for which data should be kept. tempmon uses this
  value to compute the number of points to save based on the
  ``frequency``.

frequency

  How often to collect data, in minutes. This value is approximately
  how fast tempmon will poll the device. The minimum frequency is 1
  minute.

units

  The units to report the temperature in. Either ``celsius`` or
  ``fahrenheit``. Defaults to ``fahrenheit``.

.. _plot.ly settings page: https://plot.ly/settings/api
