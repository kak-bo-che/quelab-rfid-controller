# Python Code for Quelab RFID reader

The Arduino nano is expected to be connected to */dev/ttyUSB0* on the host machine

## Using Docker to run
```bash
docker build -t rfid-controller .
./runit.sh
```

## Using python virtualenv
```bash
virtualenv -p python3 venv
source venv/bin/activate
pip3 install -r requirements.txt
pip3 install .
WA_API_KEY=$(cat rfidreader.txt) rfidreader /dev/ttyUSB0
```