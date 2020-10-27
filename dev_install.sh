#!/bin/bash

set -e

pushd "$(dirname "$0")"

git fetch
git checkout $1
git clean -df

poetry install --no-dev

sudo cp -f ./audioviz.service /etc/systemd/system/audioviz.service

sudo systemctl daemon-reload
sudo systemctl enable audioviz
sudo systemctl restart audioviz

popd
