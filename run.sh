#!/bin/bash

cd $(dirname $0)

source /home/moritz/audio/.venv/bin/activate
exec python -m airpixel
