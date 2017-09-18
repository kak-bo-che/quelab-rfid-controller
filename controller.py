
from simple_hdlc import HDLC
import time
import serial
import codecs
import json

ser = serial.Serial('/dev/ttyUSB0')

def frame_callback(data):
    print("Received: ", data.decode('utf-8'))
    message = json.loads(data.decode('utf-8'))
    if message['message'] == 'rfid_card':
        unlock_door()

h = HDLC(ser, little_endian=True)

h.startReader(onFrame=frame_callback)

def unlock_door():
    command = {"message": "lock_ctrl", "unlock": True}
    h.sendFrame( codecs.encode(json.dumps(command)))
    print("Sending: ", json.dumps(command))

while True:
    time.sleep(1)
