#!/bin/bash

set -e

pushd "$(dirname "$0")"

ssh -At ubuntu "bash -l /home/moritz/audioviz/dev_install.sh $(git rev-parse HEAD)"

popd
