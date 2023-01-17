# Python Code for Quelab RFID reader
This is the portion of of the Quelab sign in that listens for serial messages coming from the arduino nano
containing status information as well as rfid door open requests.
Status message are published as JSON to a mqtt server listening on localhost
to the 'quelab/door/status'.
```json
{
 "message":"status",
 "door_open":false,
 "locked":true,
 "lock_open":false,
 "connected":true,
 "timestamp":"2017-10-21T00:00:00",
 "arduino_connected": true
}
```
If an RFID door open request is successful the member information is  published
to the 'quelab/door/entry' topic.
The Member data is taken verbatim from the WildApricot2.1 api. With the addition
of the following fields:
```json
{
    "avatar": "base64 encoded image taken from WildApricot",
    "signin_time":"2017-10-21T00:00:00",
    "source": "rfid"
}
```

The Arduino nano is expected to be connected to */dev/ttyUSB0* on the host machine

## Installation and Setup
## Using Docker to run
```bash
docker build -t rfid-controller .
./runit.sh
```
The updated rfid_reader expects an mqtt server to be present. There is a docker-compose.yml
file available in the project directory to build/run the project.

Also no messages related to reading the rfid card are displayed in log messages by default this can be changed by passing the --verbose flag

## Using python virtualenv
```bash
virtualenv -p python3 venv
source venv/bin/activate
pip3 install -r requirements.txt
pip3 install .
WA_API_KEY=$(cat rfidreader.txt) rfidreader /dev/ttyUSB0
```

## Debian Installation
## Udev
Udev is the linux subsystem that maps events to devices, when the device
appears execute the following rules. The idVendor:1a86 and idProduct are
specific to the Quelab Arduino Nano used. They would have to be changed for a
different device. use ``` lsusb -v``` to discover those values for a different
device. The following rule will also create a symlink /dev/rfidreader that points
to the newly attached usb serial port.

*/etc/udev/rules.d/50-embedded_devices.rules*
```
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", GROUP="dialout", SYMLINK+="rfidreader", MODE="0666", TAG+="systemd", ENV{SYSTEMD_WANTS}="rfidreader.service"
```
```bash
sudo udevadm control --reload
# monitor device insertion
udevadm monitor --environment
```
## Systemd
Systemd will allow us to create a unit file that is run whenever the
rfidreader device appears to the system. By default for some reason Journald
does not persist logs accross boots, this can be changed by modifying
```Storage=auto to Storage=persistent```

*/etc/systemd/journald.conf*
```ini
[Journal]
#Storage=auto
Storage=persistent
```

There is a [race condition](https://github.com/systemd/systemd/issues/1397)
associated with systemd that when logs are set to persistent, the log
directory doesn't seem to have the correct permissions. After reboot I
manually set the guid to of the system.joural to systemd-journal, set the
group sticky bit for the parent directory.

 ```bash
sudo chgrp systemd-journal system.journal
sudo chmod g+s /var/log/journal/14a650e273914d2ba256bb1a4473ebf9/
```

Next up is the unit file for the rfidreader:
### */lib/systemd/system/rfidreader.service*
```ini
[Unit]
Description=Quelab RFID Reader
BindsTo=dev-rfidreader.device
After=dev-rfidreader.device

[Service]
Type=idle
Restart=always
RestartSec=3
User=doorctrl
EnvironmentFile=/home/doorctrl/quelab-rfid-controller/rfidreader.env
ExecStart=/usr/local/bin/rfidreader /dev/rfidreader

[Install]
WantedBy=multi-user.target
```

### */home/doorctrl/quelab-rfid-controller/rfidreader.env*
```ini
WA_API_KEY=[your API key from WildApricot HERE]
```

### Enable the systemd unit file
```bash
sudo cp rfidreader.service /lib/systemd/system/
# if the unit file has been modified it needs to be reloaded
sudo systemctl daemon-reload
sudo systemctl enable rfidreader.service
# add doorctrl to the journal group so it can view logs
usermod -a -G systemd-journal doorctrl
```

To check logs of the service use journalctl:
```bash
newgrp systemd-journal
journalctl -f -u rfidreader.service
```

