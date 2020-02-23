#!/bin/bash


nmcli c down EasyBox-419245 && nmcli c up AIRPIXEL

pushd "$(dirname $0)"
rsync -aP --delete --exclude-from='../airpixel/.gitignore' --exclude='../airpixel/.git/*' ../airpixel/ 192.168.4.1:/home/moritz/audio/airpixel
rsync -aP --delete --exclude-from='.gitignore' --exclude='.git/*' ./ 192.168.4.1:/home/moritz/audio/audioviz
popd

nmcli c down AIRPIXEL && nmcli c up EasyBox-419245
