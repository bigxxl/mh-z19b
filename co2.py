#!/usr/bin/python3

# -*- coding: utf8 -*-

# version 0.0.1

import serial, sched, time, socket, daemon, logging
import argparse
from daemon import pidfile
from logging.handlers import TimedRotatingFileHandler
import signal
import sys
import os.path



# Min
CO2_Level = 400
CO2_Prev = CO2_Level
Temp = 0

DEV = '/dev/ttyS1'
PIDFILE = '/var/run/co2.pid'
LOG_PATH = "/var/log/co2.log"
DATA_PATH = "/var/spool/co2"
#Main cycle delay
DELAY=10


def zero_calib():
        ser = serial.Serial(DEV, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.5)
        try:
                result=ser.write(bytes([0xff,0x01,0x87,0x00,0x00,0x00,0x00,0x00,0x78]))
        except:
                return 0
        print("Doing zero point calibration. Wait 1300 sec...")
        time.sleep(1300)
        

def set_range():
        ser = serial.Serial(DEV, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.5)
        try:
                # Set 5000 ppm range
                range1 = 5000 // 256
                range2 = 5000 % 256
                chk = (0x01 + 0x99 + range1 + range2) % 256
                chk = (0xff - chk) + 1
#                print(chk)
                result=ser.write(bytes([0xff,0x01,0x99,range1,range2,0x00,0x00,0x00,chk]))
                try:
                   s=ser.read(9)
                except:
                   print("error reading", DEV)
                   return 0
                if s[0] == 0xff and s[1] == 0x99:
                   return 1
        except:
                return 0



def get_co2():
        global Temp
        ser = serial.Serial(DEV, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.5)
        try:
                result=ser.write(bytes([0xff,0x01,0x86,0x00,0x00,0x00,0x00,0x00,0x79]))
        except:
                print("Error writing ",DEV)
                logger.error("Error writing "+DEV)
                return 0
        time.sleep(0.1)
        try:
                s=ser.read(9)
        except:
                logger.error("Error reading "+DEV)
                print("error reading", DEV)
                return 0
        chk = (s[1]+s[2]+s[3]+s[4]+s[5]+s[6]+s[7])%256
        chk = (0xff - chk) + 1
        if chk != s[8]:
                #CRC invalid, return 0
                logger.info("CRC invalid")
                print("CRC invalid")
                return 0
        else: print("CRC ok")
        #print(s[0], s[1])
        if s[0] == 0xff and s[1] == 0x86:
                Temp = s[4]-40
                return s[2]*256 + s[3]



def time_func():
    global CO2_Level
    global CO2_Prev
    CO2_Level = get_co2()
    if CO2_Level == 0:
        return
    CO2_Prev = CO2_Level
    print( CO2_Level )
    logger.info("Still work, co2 level: "+str(CO2_Level)+", internal temp: "+str(Temp))
    try:
      log_file = open(DATA_PATH, "w+")
      log_file.write(str(CO2_Level)) 
      log_file.seek(0)
      log_file.close()
    except Exception as e: 
            print("Exception Error:", e)	
            logger.exception("Exception Error while storing result:"+str(e))	




def program_cleanup(signum, frame):
    logger.info("Exiting on signal "+str(signum))
    sys.exit()


def main():

   try:
      while True:
         time_func()
         time.sleep(DELAY)

   except KeyboardInterrupt:
      logger.info("Exiting on keyboard interrupt.")


# If someting goes wrong
   except Exception as e: 
            print("Exception Error:", e)	
            logger.exception("Exception Error:"+str(e))	
            traceback.print_exc()



print("Starting.")
if set_range() == 1 : print ("Range = 5000 ppm")

logger = logging.getLogger("CO2 logger")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler(LOG_PATH)
handler = TimedRotatingFileHandler(LOG_PATH, when="W0", interval=1, backupCount=30)
handler.setFormatter(formatter)
logger.addHandler(handler)


parser = argparse.ArgumentParser()
parser.add_argument('-d', action='store_true')
parser.add_argument('-c', action='store_true')
args = parser.parse_args()

if os.path.isfile(PIDFILE): 
  print("Error! Stale pidfile found or program running! Check for", PIDFILE ) 
  sys.exit() 

print("Ok")

if args.c:
    zero_calib()
    sys.exit()

if args.d : 
    context = daemon.DaemonContext(pidfile=pidfile.TimeoutPIDLockFile(PIDFILE), files_preserve=[handler.stream])
    context.signal_map = {signal.SIGTERM: program_cleanup, signal.SIGHUP: program_cleanup}
    with context:
      logger.info("Run as daemon")
      main()
else: 
    main()

