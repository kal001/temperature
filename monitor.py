#!/usr/bin/env python

import sqlite3
import threading
from time import time, sleep, gmtime, strftime

import serial
import requests


# global variables

#Sqlite Database where to store readings
dbname='/var/www/templog.db'

#Serial devices
DEVICE = '/dev/ttyAMA0'
#DEVICE = '/dev/tty.Bluetooth-Incoming-Port'
BAUD = 9600

ser = serial.Serial(DEVICE, BAUD)

#Timeout (in s) for waiting to read a temperature from RF sensors
TIMEOUT = 30

#Weather Underground Data
WUKEY = ''
STATION = ''
#Time between Weather Underground samples (s)
SAMPLE = 10*60

# store the temperature in the database
def log_temperature(temp):

    conn=sqlite3.connect(dbname)
    curs=conn.cursor()

    curs.execute("INSERT INTO temps values(datetime('now'), '{0}', '{1}' )".format(temp['temperature'],temp['id']))

    # commit the changes
    conn.commit()

    conn.close()

# get temperature
# returns -100 on error, or the temperature as a float
def get_temp():
    global ser

    tempvalue = -100
    deviceid = '??'
    voltage = 0

    fim = time()+ TIMEOUT

    while (time()<fim) and (tempvalue == -100):
        n = ser.inWaiting()
        if n != 0:
            data = ser.read(n)
            nb_msg = len(data) / 12
            for i in range (0, nb_msg):
                msg = data[i*12:(i+1)*12]

                #print (msg)

                deviceid = msg[1:3]

                if msg[3:7] == "TMPA":
                    tempvalue = msg[7:]

                if msg[3:7] == "BATT":
                    voltage = msg[7:11]
                    if voltage == "LOW":
                        voltage = 0
        else:
            sleep(5)

    return {'temperature':tempvalue, 'id':deviceid}

def get_temp_wu():
    try:
        conn=sqlite3.connect(dbname)
        curs=conn.cursor()
        query = "SELECT baudrate, porta, id, active FROM sensors WHERE id like'W_'"

        curs.execute(query)
        rows=curs.fetchall()

        conn.close()
        
        if rows != None:
            for row in rows[:]:
                WUKEY = row[1]
                STATION = row[0]

                if int(row[3])>0:
                    try:
                        r = requests.get("http://api.wunderground.com/api/{0}/conditions/q/{1}.json".format(WUKEY, STATION))
                        data = r.json()
                        log_temperature({'temperature': data['current_observation']['temp_c'], 'id': row[2]})
                    except Exception as e:
                        raise

    except Exception as e:
        text_file = open("debug.txt", "a+")
        text_file.write("{0} ERROR:\n{1}\n".format(strftime("%Y-%m-%d %H:%M:%S", gmtime()),str(e)))
        text_file.close()

# main function
# This is where the program starts 
def main():
    get_temp_wu()
    t =threading.Timer(SAMPLE,get_temp_wu)
    t.start()

    while True:
        temperature = get_temp()

        if temperature['temperature'] != -100:
            #print ("temperature="+str(temperature))

            # Store the temperature in the database
            log_temperature(temperature)
        #else:
            #print ("temperature=ERROR-Timeout!")

        if t.is_alive() == False:
            t =threading.Timer(SAMPLE,get_temp_wu)
            t.start()

if __name__=="__main__":
    main()
