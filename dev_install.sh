#!/bin/bash

set -e

pushd "$(dirname "$0")"

git checkout $1
git clean -fdX

cp -f ./audioviz.service /etc/systemd/system/audioviz.service

systemctl enable audioviz
systemctl restart audioviz

popd
