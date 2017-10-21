import time
import codecs
import json
import logging
import signal
from datetime import datetime, timezone

import serial
from .cached_logins import CachedLogins
import paho.mqtt.publish as publish
from queue import Queue, Empty
from quelabrfid.wildapricot import WildApricotApi
from simple_hdlc import HDLC

class SerialControl():
    def __init__(self, serial_path, api_key=None, cached_logins=None, mqtt_host='localhost', log_level=logging.INFO):
        self.serial_port = serial.Serial(serial_path)
        self.serial_connection = HDLC(self.serial_port, little_endian=True)
        self.last_rfid_time = time.monotonic()
        self.queue = Queue()
        self.serial_connection.queue = self.queue
        self.configure_logging(log_level)
        self.last_status = {}
        self.cached_logins = CachedLogins(cached_logins)
        self.mqtt_topic =  'quelab/door/entry'
        self.mqtt_status = 'quelab/door/status'
        self.mqtt_host = mqtt_host
        signal.signal(signal.SIGTERM, self.stop)
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
        self.last_status['connected'] = self.wa_api.connected
        self.last_status['timestamp'] = datetime.now(tz=timezone.utc).isoformat()
        self.last_status['arduino_connected'] = False

        publish.single(self.mqtt_status, json.dumps(self.last_status),
                        hostname=self.mqtt_host, retain=True)
        exit(1)


    def run(self):
        # This is the main worker thread processing events as they arrive from
        # the serial port
        self.start()
        while True:
            time.sleep(0.1)
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

        message['connected'] = self.wa_api.connected
        message['timestamp'] = datetime.now(tz=timezone.utc).isoformat()
        message['arduino_connected'] = True

        publish.single(self.mqtt_status, json.dumps(message),
                        hostname=self.mqtt_host, retain=True)


    def handle_member_signin(self, contact, rfid):
            self.unlock_door(contact['DisplayName'])
            avatar = self.wa_api.get_contact_avatar(contact)
            contact['avatar'] = avatar
            contact['signin_time'] = datetime.now(tz=timezone.utc).isoformat()
            contact['source'] = 'rfid'
            self.cached_logins.update_cached_logins(rfid, contact)
            publish.single(self.mqtt_topic, json.dumps(contact), hostname=self.mqtt_host)


    def rfid_received(self, message):
        try:
            contact = self.wa_api.find_contact_by_rfid(message['rfid'])
            if WildApricotApi.is_active_member(contact):
                self.handle_member_signin(contact, message['rfid'])
            else:
                self.access_denied(contact['DisplayName'])

        except IndexError:
            self.logger.warn("(Network Connected) Unknown RFID: {}".format(message['rfid']))

        except TypeError:
            cached_login = self.cached_logins.check_cached_logins(message['rfid'])
            if cached_login:
                self.unlock_door(cached_login['DisplayName'])
            else:
                self.logger.warn("(Network Disconnected) Unknown RFID: {}".format(message['rfid']))

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
