#!/bin/bash
docker run -it \
           --rm \
           -v $(pwd):/source \
           -e WA_API_KEY=$WA_API_KEY \
           --device=/dev/ttyUSB0 \
           rfid-controller scripts/rfidreader /dev/ttyUSB0
