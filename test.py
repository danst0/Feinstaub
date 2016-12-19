'''
Copyright 2016, Frank Heuer, Germany
test.py is demonstrating some capabilities of the SDS011 module.
If you run this using your Nova Fitness Sensor SDS011 and
do not get any error (one warning will be ok) all is fine.

This is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

'''
import time, sys
from sds011 import SDS011
import logging
import logging.handlers


# Uncomment this if you want logging.
'''
logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler('SDS011.log', \
mode='a', maxBytes=1048576, backupCount=5)

handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - \
%(filename)s:%(lineno)s - %(levelname)s - %(message)s')

handler.setFormatter(formatter)
logger.addHandler(handler)
'''

# Create a new sensor instance

'''
On Win, the path is one of the com ports. On Linux / Raspberry Pi
it depends. May be one of "/dev/ttyUSB..." or "/dev/ttyAMA...".
Have a look at Win or Linux documentation.
'''
# Create an instance of your sensor
sensor = SDS011('/dev/ttyUSB0')

# Now we have some details about it
print('Device ID')
print(sensor.device_id)
print('Firmware')
print(sensor.firmware)
print(sensor.dutycycle)
print(sensor.workstate)
print(sensor.reportmode)
# Set dutycyle to nocycle (permanent)
sensor.dutycycle = 0
sensor.workstate = SDS011.WorkStates.Measuring
print("Permanent measureing (and make the senor get old. Just 8000 hours working!)\n \
Do you really need permanent measurering?")
for a in range(10):
    while True:
        values = sensor.get_values()
        if values is not None:
            print("Values measured: ", values[0], "--", values[1])
            break

# Example of dutycycle
sensor.workstate = SDS011.WorkStates.Measuring
# Setting this to 0 means permanent (each second)
sensor.dutycycle = 2 # valid values between 0 and 30
print("You have to wait at most {0} minutes before the first measuring.".format(sensor.dutycycle))
for a in range(2):
    print("Dutycycle with a={0}.".format(a))
    while True:
        values = sensor.get_values()
        if values is not None:
            print("Values measured: ", values[0], "--", values[1])
            break


sys.exit()
# Example of switching the WorkState
for a in range(3):
    print("waking up if sleeping with a={0}.".format(a))
    sensor.workstate = SDS011.WorkStates.Measuring
    # Just to demonstrate. Should be 60 seconds to get right values. Sensor has to warm up!
    time.sleep(10)
    while True:
        values = sensor.get_values()
        if values is not None:
            print("Values measured: ", values[0], "--", values[1])
            break
        time.sleep(2)
    print("Going to sleep a while")
    sensor.workstate = SDS011.WorkStates.Sleeping
    time.sleep(5)
sensor.workstate = SDS011.WorkStates.Sleeping

print("Finished")
