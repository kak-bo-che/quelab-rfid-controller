from datetime import datetime
import time
import codecs
import json
import logging
import pickle

import serial
from queue import Queue, Empty
from quelabrfid.wildapricot import WildApricotApi
from simple_hdlc import HDLC

class SerialControl():
    def __init__(self, serial_path, api_key=None, cached_logins=None, log_level=logging.INFO):
        self.serial_port = serial.Serial(serial_path)
        self.serial_connection = HDLC(self.serial_port, little_endian=True)
        self.last_rfid_time = time.monotonic()
        self.queue = Queue()
        self.serial_connection.queue = self.queue
        self.configure_logging(log_level)
        self.last_status = {}
        self.login_path = cached_logins
        self.cached_logins = self._load_cached_login_file()

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
        # Messages are not processed here directly, they are placed on a queue
        # so that message processing is quick
        self.logger.debug("Received: {}".format(data.decode('utf-8')))
        message = json.loads(data.decode('utf-8'))
        if message['message'] == 'rfid_card':
            if time.monotonic() - self.last_rfid_time > 1.5:
                self.last_rfid_time = time.monotonic()
                self.queue.put(message)
        else:
            self.queue.put(message)

    def _load_cached_login_file(self):
        logins = []
        try:
            with open(self.login_path, 'rb') as login_file:
                logins = pickle.load(login_file)

        except (TypeError, EOFError, FileNotFoundError):
            # None is not a valid path
            pass
        return logins

    def _dump_cached_login_file(self):
        with open(self.login_path, 'wb') as logins:
            pickle.dump(self.cached_logins, logins)

    def _check_cached_logins(self, rfid):
        return next((login[1] for login in self.cached_logins if login[0] == rfid), None)

    def _update_cached_logins(self, rfid, user_name):
        # remove if rfid already accepted
        self.cached_logins = list(filter(lambda x: x[0] != rfid, self.cached_logins))
        self.cached_logins.insert(0, (rfid, user_name, datetime.now()))

        self.cached_logins = self.cached_logins[0:10] # limit to last 10 entries
        self._dump_cached_login_file()
        self.logger.info(self.cached_logins)

    def process_message(self, message):
        # Asyncronous Message Processor
        if message['message'] == 'rfid_card':
            self.rfid_received(message)
        elif message['message'] == 'status':
            self.status_received(message)

    def status_received(self, message):
        # {"message":"status","door_open":false,"locked":true,"lock_open":false}
        status = "Door: "
        if self.wa_api.connected:
            connected = "(Network Connected)"
        else:
            connected = "(Network Disconnected)"
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
            self.logger.debug("{} Status: {}".format(connected,status))
        else:
            self.logger.info("{} Status: {}".format(connected, status))
        self.last_status = message

    def rfid_received(self, message):
        try:
            contact = self.wa_api.find_contact_by_rfid(message['rfid'])
            if self._is_active_member(contact):
                self.unlock_door(contact['DisplayName'])
                self._update_cached_logins(message['rfid'], contact['DisplayName'])
            else:
                self.access_denied(contact['DisplayName'])

        except IndexError:
            self.logger.warn("(Network Connected) Unknown RFID: {}".format(message['rfid']))

        except TypeError:
            cached_login = self._check_cached_logins(message['rfid'])
            if cached_login:
                self.unlock_door(cached_login)
            else:
                self.logger.warn("(Network Disconnected) Unknown RFID: {}".format(message['rfid']))

    def _is_active_member(self, contact):
        for field in contact['FieldValues']:
            if field['FieldName'] == 'Membership status':
                status = field['Value'].get('Value')
        if status in ['Lapsed', 'Active']:
            return True
        else:
            return False

    def access_denied(self, user_name):
        self.logger.info("Access denied to: {}".format(user_name))

    def unlock_door(self, user_name):
        command = {"message": "lock_ctrl", "unlock": True}
        self.serial_connection.sendFrame( codecs.encode(json.dumps(command)))
        if self.wa_api.connected:
            self.logger.info("(Network Connected) Opening door for: {}".format(user_name))
        else:
            self.logger.info("(Network Disconnected) Opening door for: {}".format(user_name))
        self.logger.debug("Sending: {}".format(json.dumps(command)))
