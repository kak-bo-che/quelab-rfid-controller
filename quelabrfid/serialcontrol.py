import time
import serial
import codecs
import json
import logging
from queue import Queue, Empty
from quelabrfid.wildapricot import WildApricotApi
from simple_hdlc import HDLC

class SerialControl():
    def __init__(self, serial_path, api_key=None, log_level=logging.INFO):
        self.serial_port = serial.Serial(serial_path)
        self.serial_connection = HDLC(self.serial_port, little_endian=True)
        self.last_rfid_time = time.monotonic()
        self.queue = Queue()
        self.serial_connection.queue = self.queue
        self.configure_logging(log_level)
        self.last_status = {}

        if api_key:
            self.wa_api = WildApricotApi(api_key)

    def configure_logging(self, level):
        self.logger = logging.getLogger()
        self.logger.setLevel(level)
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

    def _is_active_member(self, contact):
        for field in contact['FieldValues']:
             if field['FieldName'] == 'Membership status':
                 status = field['Value'].get('Value')
        if status in ['Lapsed', 'Active']:
            return True
        else:
            return False

    def process_message(self, message):
        if message['message'] == 'rfid_card':
            try:
                contact = self.wa_api.find_contact_by_rfid(message['rfid'])
                if self._is_active_member(contact):
                    self.unlock_door(contact['DisplayName'])
                else:
                    self.access_denied(contact['DisplayName'])
            except IndexError:
                self.logger.warn("Attempted entry with unknown RFID: {}".format(message['rfid']))
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
            status = status + "(Unlock signaled)"
        else:
            status = status + "(Lock signaled)"

        if self.last_status == message:
            self.logger.debug("Status: {}".format(status))
        else:
            self.logger.info("Status: {}".format(status))
        self.last_status = message

    def access_denied(self, user_name):
        self.logger.info("Access denied to: {}".format(user_name))

    def unlock_door(self, user_name):
        command = {"message": "lock_ctrl", "unlock": True}
        self.serial_connection.sendFrame( codecs.encode(json.dumps(command)))
        self.logger.info("Opening door for: {}".format(user_name))
        self.logger.debug("Sending: {}".format(json.dumps(command)))
