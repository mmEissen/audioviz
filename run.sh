#!/bin/bash

cd $(dirname $0)

source /home/moritz/audio/.venv/bin/activate
export RING_VOLUME_MIN="6e-13"
exec python -m airpixel.framework
