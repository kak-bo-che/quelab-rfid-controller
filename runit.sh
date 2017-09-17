#!/bin/bash
docker run -it --rm -v $(pwd):/source --device=/dev/ttyUSB0 rfid-controller $*
