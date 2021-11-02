#!/bin/bash

# export PULSE_SOURCE='alsa_output.platform-bcm2835_audio.analog-stereo.monitor'
echo $USER
python -m audioviz.star $1 $2
