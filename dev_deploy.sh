#!/bin/bash

set -e

pushd "$(dirname "$0")"

ssh -At 192.168.2.196 "bash -l /home/moritz/audioviz/dev_install.sh $(git rev-parse HEAD)"

popd
