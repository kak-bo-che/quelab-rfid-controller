import time
import serial
import codecs
import json
import logging
import os
from queue import Queue, Empty
from wildapricot import WildApricotApi
from simple_hdlc import HDLC

class SerialControl():
    def __init__(self, serial_path, api_key=None):
        self.serial_port = serial.Serial(serial_path)
        self.serial_connection = HDLC(self.serial_port, little_endian=True)
        self.last_rfid_time = time.monotonic()
        self.queue = Queue()
        self.serial_connection.queue = self.queue
        self.configure_logging()

        if api_key:
            self.wa_api = WildApricotApi(api_key)

    def configure_logging(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        hdlc_logger = logging.getLogger('simple_hdlc')
        hdlc_logger.setLevel(logging.WARNING)

    def start(self):
        self.logger.info("Starting Serial Reader")
        self.serial_connection.startReader(onFrame=self.frame_callback, onError=self.error_callback)

    def stop(self):
        # on loss of serial port exit immediately, have systemd/supervisord
        # restart the process on failure, otherwise the serial port will
        # continue to be reserved
        self.logger.error("Stopping Serial Reader")
        self.serial_connection.stopReader()
        self.serial_port.close()
        exit(1)


    def run(self):
        # This is the main worker thread processing events as they arrive from
        # the serial port
        self.start()
        while True:
            time.sleep(0.001)
            if not self.serial_connection.reader.isAlive():
                self.stop()
            try:
                item = self.queue.get(block=False, timeout=1)
                self.process_message(item)
                self.queue.task_done()
            except Empty:
                pass

    def error_callback(self, error):
        self.stop()

    def frame_callback(self, data):
        self.logger.debug("Received: {}".format(data.decode('utf-8')))
        message = json.loads(data.decode('utf-8'))
        if message['message'] == 'rfid_card':
            if time.monotonic() - self.last_rfid_time > 1.5:
                self.last_rfid_time = time.monotonic()
                self.queue.put(message)
        else:
            self.queue.put(message)

    def process_message(self, message):
        if message['message'] == 'rfid_card':
            contact = self.wa_api.find_contact_by_rfid(message['rfid'])
            if contact['Status'] == 'Active':
                self.unlock_door(contact['DisplayName'])
        elif message['message'] == 'status':
            self.status_received(message)

    def status_received(self, message):
        # {"message":"status","door_open":false,"locked":true,"lock_open":false}
        status = "Door: "
        if message['door_open'] == True:
            status = status + "open, "
        else:
            status = status + "closed, "
        if message['locked'] == True:
            status = status + "Latch: locked, "
        else:
            status = status + "Latch: unlocked, "
        if message['lock_open'] ==True:
            status = status + "Unlock signaled"
        else:
            status = status + "Lock signaled"

        self.logger.info("Status: {}".format(status))

    def unlock_door(self, user_name):
        command = {"message": "lock_ctrl", "unlock": True}
        self.serial_connection.sendFrame( codecs.encode(json.dumps(command)))
        self.logger.info("Opening door for: {}".format(user_name))
        self.logger.debug("Sending: {}".format(json.dumps(command)))

controller = SerialControl('/dev/ttyUSB0', os.environ['WA_API_KEY'])
controller.run()
