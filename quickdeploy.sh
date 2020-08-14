#!/bin/bash

pushd "$(dirname $0)"
rsync -aP --delete --exclude-from='../airpixel/.gitignore' --exclude='../airpixel/.git/*' ../airpixel/ 192.168.4.1:/home/moritz/audio/airpixel
rsync -aP --delete --exclude-from='.gitignore' --exclude='.git/*' ./ 192.168.4.1:/home/moritz/audio/audioviz
popd
ssh 192.168.4.1 "sudo systemctl restart audioviz" 
