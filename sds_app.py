#!/usr/bin/env python3

import httplib, urllib
import socket
import serial
import argparse
import os, sys
import logging
import struct
import time
from sds011 import SDS011
import pickle
import signal
from phant import Phant


class SENSOR:
    def __init__(self):
        # Create an instance of your sensor
        self.sensor = SDS011('/dev/ttyUSB0')
        self.rolling_average = [None, None]
        self.last_values = [None, None]
        # Now we have some details about it
        print('Device ID')
        print(self.sensor.device_id)
        print('Firmware')
        print(self.sensor.firmware)
        print('Workstate')
        print(self.sensor.workstate)

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
                print('First wake not successful')
                self.sensor.workstate = SDS011.WorkStates.Measuring
            except:
                print('Double wake not effective')

    def measure(self, warm_up = False):
        while True:
            values = self.sensor.get_values()
            if values is not None:
                print("Values measured: ", values[0], "--", values[1])
                break
            time.sleep(2)
        self.update_average(values)
        return values
        
    def sleep(self):
        print("Going to sleep a while")
        self.sensor.workstate = SDS011.WorkStates.Sleeping
    
    def significant_deviation_from_average(self, values):
        sgn_level = 0.2
        result = False
        for i in [0, 1]:
            if abs((values[i] - self.rolling_average[i])/self.rolling_average[i]) > sgn_level:
                print('Sign. deviation to average (No. {0}). Value: {1}, Average: {2}'.format(i, values[i], self.rolling_average[i]))
                result = True
                break
        return result

DELAYS = [20, 30, 1*60, 3*60, 5*60, 15*60, 30*60]
#DELAYS = [3, 6, 8, 9, 15]    

def change_delay(cur_delay, add_factor):
    result = min(max(cur_delay + add_factor, 0), len(DELAYS)-1)
    return result

def exit_gracefully(signal, frame):
    print('Exiting')
    pickle.dump(current_delay_no, open('current_delay.p', 'wb'))
    sys.exit(0)

if __name__ == "__main__":
    sds = SENSOR()
    try:
        current_delay_no = pickle.load(open('current_delay.p', 'rb'))
    except:
        current_delay_no = 0
    signal.signal(signal.SIGINT, exit_gracefully)
    
    while True:
        print('Current delay: {0} seconds'.format(DELAYS[current_delay_no]))
        if sds.sensor.workstate == SDS011.WorkStates.Sleeping:
            sds.wake_up()
            wake_delay = 45
            print('Waking up, delay for {0} secs'.format(wake_delay))
            time.sleep(wake_delay)
        values = sds.measure()
        if sds.significant_deviation_from_average(values):
            print('Significant deviation to average')
            current_delay_no = change_delay(current_delay_no, -1)
        else:
            print('No significant deviation to average')
            current_delay_no = change_delay(current_delay_no, 1)
#wget -qO- "http://data.sparkfun.com/input/1n4x2aapnqIpXp2zZzwo?private_key=0mbx4yyBmZFjYjVk8kqB&pm10=$PPM10&pm25=$PPM25" &> /dev/null
        p = Phant(publicKey='1n4x2aapnqIpXp2zZzwo', fields=['pm10', 'pm25'], privateKey='0mbx4yyBmZFjYjVk8kqB')
        
        p.log(values[0], values[1])
        print(p.remaining_bytes, p.cap)
        data = p.get()
        print(data['temp'])
        
        
        if  DELAYS[current_delay_no] >= 3*60:
            print('Putting sensor to sleep')
            sds.sleep()
        print('Sleeping for: {0} seconds'.format(DELAYS[current_delay_no]))
        time.sleep(DELAYS[current_delay_no])
    


    try:
        with serial.Serial(args.device, baudrate=9600) as ser:
            logging.info("Serial device initialized")
            read_full = False
            pm25 = 0
            pm10 = 0
            data = []
            while not read_full:
                if ser.read() == b'\xaa':
                    logging.debug("FIRST HEADER GOOD")
                    # FIRST HEADER IS GOOD
                    if ser.read() == b'\xc0':
                        # SECOND HEADER IS GOOD
                        logging.debug("SECOND HEADER GOOD")
                        for i in range(8):
                            byte = ser.read()
                            data.append(bytes2int(byte))

                        if data[-1] == 171:
                            # END BYTE IS GOOD. DO CRC AND CALCULATE
                            logging.debug("END BYTE GOOD")
                            if data[6] == sum(data[0:6])%256:
                                logging.debug("CRC GOOD")
                            pm25 = (data[0]+data[1]*256)/10
                            pm10 = (data[4]+data[3]*256)/10
                            read_full = True
            if args.url:
                logging.info("Posting to %s" % args.url)
                r = requests.post(args.url, data={"pm10": pm10, "pm2.5": pm25})
                logging.debug(r)
            logging.info("PM 10: %s" % pm10)
            logging.info("PM 2.5: %s" % pm25)
    except serial.SerialException as e:
        logging.critical(e)

    if args.powersaving and args.sysnode:
        logging.debug("Turning USB OFF")
        logging.debug(turn_off_usb(args.sysnode))



