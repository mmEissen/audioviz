#!/bin/bash

cd $(dirname $0)

source /home/moritz/audioviz/.venv/bin/activate
exec python -m airpixel
