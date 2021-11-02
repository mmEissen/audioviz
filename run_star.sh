#!/bin/bash

export PULSE_SOURCE='alsa_output.platform-bcm2835_audio.analog-stereo.monitor'
python -m audioviz.star $1 $2
