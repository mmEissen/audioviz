Audioviz
========

This project is a prototype and sandbox to play around with audio visualization on NeoPixels. I did a short talk on the topic which can be found on [youtube](https://youtu.be/JJu3Z-2arnY).



## Set up

Get Ubuntu 20 LTS for RaspberryPI 4 from here:
https://ubuntu.com/download/raspberry-pi

Flash it to an sd card with this:
https://www.balena.io/etcher/

Don't bother with setting up a wifi on boot. It probably won't work. Instead connect the raspi with an ethernet cable.

Wait for a while (a minute or two) and then ssh into the raspi with
```
ssh ubuntu@ubuntu
```

You will be prompted to change the password.

Create a user to match your current user and give them sudo

```
sudo adduser moritz
sudo usermod -aG sudo moritz
```

Log out of raspberry pi with CTRL+D
Add your ssh key to rspberry:
```
ssh-copy-id -i ~/.ssh/id_rsa.pub moritz@ubuntu
```

Now log back into raspberry pi with. This should no longer require password prompts.
```
ssh ubuntu
```

Check whether the unnatended upgrade has finished:
```
ps -aux | grep "/usr/bin/unattended-upgrade"
```
This should only show one line (the command itself).

Once it's done install network-manager, dnsmasq and hostapd:
```
sudo apt-get update
sudo apt-get install network-manager hostapd dnsmasq
```

`CTRL-D` again and copy the netplan over to the PI
```
scp netplan.yaml ubuntu:netplan.yaml
```
then back into the py with `ssh ubuntu`

unmask+enable hostapd
```
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
```

Move the netplan to the netplan directory, generate and apply
```
sudo mv netplan.yaml /etc/netplan/network.yaml
sudo netplan generate
sudo netplan apply
```

Install other dependencies from apt:
```
sudo apt-get update
sudo apt-get install libasound2-dev python3-dev gcc gfortran libopenblas-dev liblapack-dev cython3 python3-pip
```

Install poetry:
```
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python3 -
```

Install pybind11 from pip:
```
pip install pybind11
```

Log out and back in with ssh key forwarding:
```
ssh -A ubuntu
```

Clone the repo:
```
git clone git@github.com:mmEissen/audioviz.git
```

For some reason also had to, who the fuck knows why:
```
sudo systemctl disable systemd-resolved.service
sudo systemctl stop systemd-resolved.service
sudo rm /etc/resolv.conf
echo nameserver 8.8.8.8 > /etc/resolv.conf
```

Disable syslog once everything seems to be working
```
sudo systemctl disable rsyslog
sudo systemctl stop rsyslog
```
