#!/usr/bin/env python
""" Drone Pilot - Control of MRUAV """
""" mw-logdata.py: Script that logs data from a vehicle with MultiWii flight controller and a MoCap system."""

__author__ = "Aldo Vargas"
__copyright__ = "Copyright 2015 Aldux.net"

__license__ = "GPL"
__version__ = "1"
__maintainer__ = "Aldo Vargas"
__email__ = "alduxvm@gmail.com"
__status__ = "Development"

import time, datetime, csv, threading
from modules.pyMultiwii import MultiWii
import modules.UDPserver as udp
from modules.utils import *
from modules.pids import PID_Controller

# MRUAV initialization
#vehicle = MultiWii("/dev/tty.usbserial-A801WZA1")
vehicle = MultiWii("/dev/ttyUSB0")

vehicle.getData(MultiWii.ATTITUDE)

# Position coordinates [x, y, x] 
desiredPos = {'x':0.0, 'y':0.0, 'z':0.0} # Set at the beginning (for now...)
currentPos = {'x':0.0, 'y':0.0, 'z':0.0} # It will be updated using UDP

# Initialize RC commands and pitch/roll to be sent to the MultiWii 
rcCMD = [1500,1500,1500,1000,1000,1000,1000,1000]
desiredRoll = 1500
desiredPitch = 1500

# PID's initialization 
gains = {'kp':1.0, 'ki':0.1, 'kd':0.01, 'iMax':1}
rPIDvalue = 0.0
pPIDvalue = 0.0

# PID module pids
rollPID = PID_Controller(gains['kp'], gains['ki'], gains['kd'])
pitchPID = PID_Controller(gains['kp'], gains['ki'], gains['kd'])


# Function to update commands and attitude to be called by a thread
def control():
    global vehicle, rcCMD
    global rollPID, pitchPID
    global desiredPos, currentPos
    global desiredRoll, desiredPitch
    global rPIDvalue, pPIDvalue

    while True:
        if udp.active:
            print "UDP server is active..."
            break
        else:
            print "Waiting for UDP server to be active..."
        time.sleep(0.5)

    try:
        #st = datetime.datetime.fromtimestamp(time.time()).strftime('%m_%d_%H-%M-%S')+".csv"
        #f = open("logs/mw-"+st, "w")
        #logger = csv.writer(f)
        #logger.writerow(('timestamp','roll','pitch','yaw','proll','ppitch','throttle','pyaw','x','y','z'))
        while True:
            #elapsed = time.time()
            rcCMD[0] = udp.message[0]
            rcCMD[1] = udp.message[1]
            rcCMD[2] = udp.message[2]
            rcCMD[3] = udp.message[3]

            # Order of the position from Optitrack is: X, Z, Y
            currentPos['x'] = udp.message[5]
            currentPos['y'] = udp.message[4]
            currentPos['z'] = udp.message[6]

            rPIDvalue = rollPID.getCorrection(desiredPos['x'],currentPos['x'])
            pPIDvalue = pitchPID.getCorrection(desiredPos['y'],currentPos['y'])

            # Check before flying that compass is calibrated
            sinYaw = sin(radians( vehicle.attitude['heading'] ))
            cosYaw = cos(radians( vehicle.attitude['heading'] ))

            # Mellinger paper
            desiredRoll  = toPWM(degrees( (rPIDvalue * sinYaw - pPIDvalue * cosYaw) * (1 / g) ),1)
            desiredPitch = toPWM(degrees( (rPIDvalue * cosYaw + pPIDvalue * sinYaw) * (1 / g) ),1)

            if udp.message[7] == 1:
                rcCMD[0] = limit(desiredRoll,1300,1700)
                rcCMD[1] = limit(desiredPitch,1300,1700)

            rcCMD = [limit(n,1000,2000) for n in rcCMD]

            vehicle.sendCMD(16,MultiWii.SET_RAW_RC,rcCMD)

            #vehicle.sendCMD(16,MultiWii.SET_RAW_RC,rcCMD)
            #time.sleep(0.005) # Time to allow the Naze32 respond the last attitude command
            vehicle.getData(MultiWii.ATTITUDE)
            vehicle.getData(MultiWii.RC)
            #print "Time to ask two commands -> %0.3f" % (time.time()-elapsed)
            #print "%s %s" % (vehicle.attitude,rcCMD) 
            print "%s %s" % (vehicle.attitude,rcCMD) 

            # Save log
            logger.writerow((time.time(), \
                             vehicle.attitude['angx'], vehicle.attitude['angy'], vehicle.attitude['heading'], \
                             #vehicle.rcChannels['roll'], vehicle.rcChannels['pitch'], vehicle.rcChannels['throttle'], vehicle.rcChannels['yaw'], \
                             udp.message[0], udp.message[1], udp.message[3], udp.message[2], \
                             udp.message[5], udp.message[4], udp.message[6] ))
            time.sleep(0.01) # 100hz 

    except Exception,error:
        print "Error in control thread: "+str(error)
        f.close()

if __name__ == "__main__":
    try:
        logThread = threading.Thread(target=control)
        logThread.daemon=True
        logThread.start()
        udp.startTwisted()
    except Exception,error:
        print "Error on main: "+str(error)
        vehicle.ser.close()
    except KeyboardInterrupt:
        print "Keyboard Interrupt, exiting."
        exit()