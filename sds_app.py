#!/usr/bin/env python3

import sqlite3
import rrdtool
import random
import serial
import argparse
import os, sys
import logging
import struct
import time, datetime
from sds011 import SDS011
import pickle
import signal
import http.client, urllib   # http and url libs used for HTTP POSTs
import socket            # socket used to get host name/IP
import threading
lock = threading.Lock()

server = "data.sparkfun.com" # base URL of your feed
publicKey = "1n4x2aapnqIpXp2zZzwo" # public key, everyone can see this
privateKey = "0mbx4yyBmZFjYjVk8kqB"  # private key, only you should know
fields = ["pm10", "pm25"] # Your feed's data fields

GRENZWERTE = [50, 25]
WARM_UP_DELAY = 45

logging.basicConfig(format='%(levelname)s:%(message)s', level=getattr(logging, 'INFO'))


with lock:
    save_current_delay = False

if not os.path.isfile('/home/pi/feinstaub/feinstaub.sqlite3'):
    conn = sqlite3.connect('/home/pi/feinstaub/feinstaub.sqlite3', detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()

    c.execute('''CREATE TABLE feinstaub
             (date DATETIME, pm10 real, pm25 real)''')
else:
    conn = sqlite3.connect('/home/pi/feinstaub/feinstaub.sqlite3', detect_types=sqlite3.PARSE_DECLTYPES)
    sql = conn.cursor()

             
def house_keeping():
    global save_current_delay
    logging.debug('House keeping')
    with lock:
        save_current_delay = True
    house_delay = random.randrange(150, 600)
    logging.debug('House keeping end, restart timer ({0} secs)'.format(house_delay))
    threading.Timer(house_delay, house_keeping).start()

class SENSOR:
    def __init__(self):
        # Create an instance of your sensor
        self.sensor = SDS011('/dev/ttyUSB0')
        self.rolling_average = [None, None]
        self.last_values = [None, None]
        # Now we have some details about it
        logging.debug('Device ID')
        logging.debug(self.sensor.device_id)
        logging.debug('Firmware')
        logging.debug(self.sensor.firmware)
        logging.debug('Workstate')
        logging.debug(self.sensor.workstate)

        # Set dutycyle to nocycle (permanent)
        self.sensor.dutycycle = 0

    def update_average(self, values):
        percentage_old = 0.9
        if self.rolling_average[0] == None:
            for i in [0, 1]:
                self.rolling_average[i] = values[i]
            
        else:
            for i in [0, 1]:
                self.rolling_average[i] = percentage_old * self.rolling_average[i] + (1-percentage_old) * values[i]


    def wake_up(self):
        try:
            self.sensor.workstate = SDS011.WorkStates.Measuring
        except:
            try:
                logging.warn('First wake not successful')
                self.sensor.workstate = SDS011.WorkStates.Measuring
            except:
                logging.error('Double wake not effective')

    def measure(self, warm_up = False):
        while True:
            values = self.sensor.get_values()
            if values is not None:
                logging.info('Values measured: PM10: {0}, PM2.5: {1}'.format(values[0], values[1]))
                break
            time.sleep(2)
        self.update_average(values)
        return values
        
    def sleep(self):
        logging.debug("Going to sleep a while")
        self.sensor.workstate = SDS011.WorkStates.Sleeping
    
    def significant_deviation_from_average(self, values):
        # Significant changes upwards means more particles
        up_sgn_level = 0.3
        up_abs_sign_level = 4

        # Significant changes downwards means less particles
        down_sgn_level = 0.7
        down_abs_sign_level = 15
        result = False
        
        for i in [0, 1]:
            if (values[i] - self.rolling_average[i])/self.rolling_average[i] > up_sgn_level and \
              values[i] - self.rolling_average[i] > up_abs_sign_level or \
              (self.rolling_average[i] - values[i])/self.rolling_average[i] > down_sgn_level and \
              self.rolling_average[i] - values[i] > down_abs_sign_level:
                logging.info('Sign. deviation to average (No. {0}). Value: {1}, Average: {2}'.format(i, values[i], self.rolling_average[i]))
                result = True
                break
        return result

DELAYS = [30, 60, 3*60, 5*60, 15*60, 30*60]
#DELAYS = [3, 6, 8, 9, 15]    

def change_delay(cur_delay, add_factor):
    result = min(max(cur_delay + add_factor, 0), len(DELAYS)-1)
    return result

def exit_gracefully(signal, frame):
    logging.debug('Exiting')
    pickle.dump(current_delay_no, open('/home/pi/feinstaub/current_delay.p', 'wb'))
    conn.close()
    sys.exit(0)

if __name__ == "__main__":
    sds = None
    while sds == None:
        try:
            sds = SENSOR()
        except:
            logging.error('No sensor found')
            time.sleep(60)   
        else:
            break

    if not os.path.isfile('/home/pi/feinstaub/feinstaub.rrd'):
        logging.debug('Creating new RRD file')
        ret = rrdtool.create('/home/pi/feinstaub/feinstaub.rrd', '--step', '30', '--start', '0',
                                'DS:pm10:GAUGE:120:0:999',
                                'DS:pm25:GAUGE:120:0:999',
                                'RRA:AVERAGE:0.5:1:600',
                                'RRA:AVERAGE:0.005:120:24',
                                'RRA:AVERAGE:0.5:7:52',
                                'RRA:MAX:0.5:1:600',
                                'RRA:MAX:0.005:120:700',
                                'RRA:MAX:0.5:7:52')
        if ret:
            logging.warn('RRD create with message')
            logging.warn(rrdtool.error())
    
    #logging.info('Random data')
    #for i in range(100):
    #    ret = rrdtool.update('/home/pi/feinstaub/feinstaub.rrd','N:{0}:{1}'.format(random.randrange(0,999), random.randrange(0,999)))
    #    time.sleep(0.1)   
    #sys.exit()
    house_keeping()
    try:
        current_delay_no = pickle.load(open('current_delay.p', 'rb'))
    except:
        current_delay_no = 0
    signal.signal(signal.SIGINT, exit_gracefully)
    
    while True:
        logging.debug('Current delay: {0} seconds'.format(DELAYS[current_delay_no]))
        if sds.sensor.workstate == SDS011.WorkStates.Sleeping:
            sds.wake_up()
            logging.debug('Waking up, delay for {0} secs'.format(WARM_UP_DELAY))
            time.sleep(WARM_UP_DELAY)
        values = sds.measure()
        if sds.significant_deviation_from_average(values):
            logging.debug('Significant deviation to average')
            current_delay_no = change_delay(current_delay_no, -1)
        else:
            logging.debug('No significant deviation to average')
            current_delay_no = change_delay(current_delay_no, 1)
            
        with lock:
            if save_current_delay:
                logging.debug('Saving current_delay to pickle jar')        
                pickle.dump(current_delay_no, open('/home/pi/feinstaub/current_delay.p', 'wb'))
                logging.info('Graphing Feinstaub to JPG')
                ret = rrdtool.graph( '/home/pi/feinstaub/feinstaub.gif', '--start', '-1d',
                                     'DEF:graphpm10=/home/pi/feinstaub/feinstaub.rrd:pm10:AVERAGE',
                                     'AREA:graphpm10#00FF00:PM 10 (avg.)',
                                     '--title=Feinstaubmessung',
                                     '--vertical-label=Particle per m3')

#                ret = rrdtool.graph( '/home/pi/feinstaub/feinstaub.jpg', '--start', '-1d',
#                                     'DEF:graphpm10=/home/pi/feinstaub/feinstaub.rrd:pm10:AVERAGE',
#                                     'DEF:graphpm25=/home/pi/feinstaub/feinstaub.rrd:pm25:AVERAGE',
#                                     'DEF:graphmaxpm10=/home/pi/feinstaub/feinstaub.rrd:pm10:MAX',
#                                     'DEF:graphmaxpm25=/home/pi/feinstaub/feinstaub.rrd:pm25:MAX',
#                                     'AREA:graphpm10#00FF00:PM 10 (avg.)',
#                                     'LINE1:graphpm25#d0000FF:PM 2.5 (avg.)',
#                                     'AREA:graphmaxpm10#00FF00:PM 10 (max.)',
#                                     'LINE1:graphmaxpm25#d0000FF:PM 2.5 (max.)',
#                                     '--title=Feinstaubmessung',
#                                     '--vertical-label=Particle per m3')



                if ret and len(ret) == 3:
                    logging.debug('RRD graph with message: {0}'.format(ret))

                logging.debug('Finished')
                save_current_delay = False

        #wget -qO- "http://data.sparkfun.com/input/1n4x2aapnqIpXp2zZzwo?private_key=0mbx4yyBmZFjYjVk8kqB&pm10=$PPM10&pm25=$PPM25" &> /dev/null
        logging.info("Logging to data.sparkfun.com")
        # Our first job is to create the data set. Should turn into
        # something like "light=1234&switch=0&name=raspberrypi"
        data = {} # Create empty set, then fill in with our three fields:
        # Field 0, light, gets the local time:
        data[fields[0]] = values[0]
        # Field 1, switch, gets the switch status:
        data[fields[1]] = values[1]
        # Next, we need to encode that data into a url format:
        params = urllib.parse.urlencode(data)

        # Now we need to set up our headers:
        headers = {} # start with an empty set
        # These are static, should be there every time:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Connection"] = "close"
        headers["Content-Length"] = len(params) # length of data
        headers["Phant-Private-Key"] = privateKey # private key header

        # Now we initiate a connection, and post the data
        c = http.client.HTTPConnection(server)
        # Here's the magic, our reqeust format is POST, we want
        # to send the data to data.sparkfun.com/input/PUBLIC_KEY.txt
        # and include both our data (params) and headers
        c.request("POST", "/input/" + publicKey + ".txt", params, headers)
        try:
            r = c.getresponse(timeout=4) # Get the server's response and print it
        except:
            logging.error('No connection to server possible')
        else:
            logging.debug('Status of post request: {0}, {1}'.format(r.status, r.reason))
        
        logging.info("Logging to file")
        ret = rrdtool.update('/home/pi/feinstaub/feinstaub.rrd','N:{0}:{1}'.format(values[0], values[1]));
        if ret:
            logger.debug('Message when updating')
            logger.debug(ret)
            logger.debug(rrdtool.error())

        logging.info("Logging to database")
        now = datetime.datetime.now()
        sql.execute('''INSERT INTO feinstaub VALUES (?, ?, ?)''', (datetime.datetime.now(), values[0], values[1]))
        conn.commit()

        real_delay = DELAYS[current_delay_no]
        shown_delay = real_delay
        exceeding_limits = False
        for i in range(2):
            if values[i] >= GRENZWERTE[i]:
                real_delay = DELAYS[0]
                shown_delay = real_delay
                logging.info('Limit(s) exceeded')
                break
        
        if  real_delay >= 3*60:
            logging.debug('Putting sensor to sleep')
            real_delay -= WARM_UP_DELAY
            sds.sleep()
        logging.info('Daemon waiting for: {0} seconds'.format(shown_delay))
        time.sleep(real_delay)
    


#                ret = rrdtool.graph( '/home/pi/feinstaub/feinstaub.jpg', '--start', '-1d',
#                                     'DEF:graphpm10=/home/pi/feinstaub/feinstaub.rrd:pm10:AVERAGE',
#                                     'DEF:graphpm25=/home/pi/feinstaub/feinstaub.rrd:pm25:AVERAGE',
#                                     'DEF:graphmaxpm10=/home/pi/feinstaub/feinstaub.rrd:pm10:MAX',
#                                     'DEF:graphmaxpm25=/home/pi/feinstaub/feinstaub.rrd:pm25:MAX',
#                                     'AREA:graphpm10#00FF00:PM 10 (avg.)',
#                                     'LINE1:graphpm25#d0000FF:PM 2.5 (avg.)',
#                                     'AREA:graphmaxpm10#00FF00:PM 10 (max.)',
#                                     'LINE1:graphmaxpm25#d0000FF:PM 2.5 (max.)',
#                                     '--title=Feinstaubmessung',
#                                     '--vertical-label=Particle per m3')

