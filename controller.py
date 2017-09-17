
from simple_hdlc import HDLC
import time
import serial
import codecs

ser = serial.Serial('/dev/ttyUSB0')

def frame_callback(data):
    print(data)

h = HDLC(ser, little_endian=True)


h.startReader(onFrame=frame_callback)

while True:
    time.sleep(5)
    h.sendFrame( codecs.encode('{"message":"lock_ctrl", "unlock":true}', 'ascii'))