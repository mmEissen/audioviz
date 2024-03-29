# Setup

## raspotify:
https://github.com/dtcooper/raspotify
```
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
```

add user to audio group
```
sudo usermod -a -G audio moritz
```

## Loopback devices (Audio)

```
sudo apt install pulseaudio
sudo adduser moritz pulse-access 
sudo adduser moritz pulse
```

/etc/systemd/system/pulseaudio.service
```
[Unit]
Description=Pulse Audio

[Service]
Type=simple
ExecStart=/usr/bin/pulseaudio --system --disallow-exit --disable-shm --exit-idle-time=-1

[Install]
WantedBy=multi-user.target
```

systemctl daemon-reload
systemctl enable pulseaudio.service


/etc/pulse/system.pa
```
load-module module-native-protocol-unix auth-anonymous=1
```


```
nano /etc/asound.conf
```

```
pcm.!default {
        type hw
        card 1
}

ctl.!default {
        type hw
        card 1
}
```

```
sudo nano /etc/modprobe.d/alsa-base.conf
```
add
```
options snd_bcm2835 index=0,1 id=b1,Headphones
options snd_aloop index=2
```


setting gpu_mem=32 in /boot/config.txt

sudo pico /boot/cmdline.txt
Press the End key on your keyboard, then the space key, then paste the following text:

sdhci-bcm2708.missing_status=0 sdhci-bcm2708.sync_after_dma=0


## Raspian

Download and flash Raspberry Pi OS LITE onto an SD card

Open the SD cards boot dir and add a file `wpa_supplicant.conf`:
```
country=DE # Change if needed
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
network={
    ssid="name"
    psk="password"
    key_mgmt=WPA-PSK
}
```

Add an empty file called `ssh` to `boot` as well

Connect via ssh with
```
ssh pi@raspberrypi
```
and the password `raspberry`

Create a user to match the host machine user and give them sudo

```
sudo adduser moritz
sudo usermod -aG sudo moritz
```

Log out of raspberry pi with CTRL+D
Add your ssh key to rspberry:
```
ssh-copy-id -i ~/.ssh/id_rsa.pub moritz@raspberrypi
```

(Optional) Configure your router to always give the raspberry the same IP address for better fingerprint verification

possibly install driver:
```
# https://forums.raspberrypi.com/viewtopic.php?t=271924

sudo wget http://downloads.fars-robotics.net/wifi-drivers/install-wifi -O /usr/bin/install-wifi
sudo install-wifi
```


ensure that on-board wifi is wlan0:
```
ln -s /dev/null /etc/systemd/network/99-default.link  # if not already present 
sudo nano /etc/udev/rules.d/72-static-name.rules
```
```
ACTION=="add", SUBSYSTEM=="net", DRIVERS=="brcmfmac", NAME="wlan0"
ACTION=="add", SUBSYSTEM=="net", DRIVERS=="rtl8192eu", NAME="wlan1"
```

(driver name of second device is from `lsusb -t`)


Change the connected network interface to wlan1
```
sudo mv /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant-wlan1.conf
sudo reboot
```

```
sudo apt-get update
# do not sudo apt-get upgrade!
# this breaks the wifi
```


```
sudo apt-get install hostapd dnsmasq
```

```
sudo systemctl unmask hostapd
sudo systemctl disable hostapd
sudo systemctl disable dnsmasq
```

```
sudo nano /etc/hostapd/hostapd.conf
```

```
interface=wlan0
driver=nl80211
country_code=DE
ssid=AIRPIXEL
auth_algs=1
ignore_broadcast_ssid=0
hw_mode=g
wpa=2
wpa_passphrase=34D6MasF8B2M2ws8
wpa_key_mgmt=WPA-PSK
channel=4
```

```
sudo nano /etc/dhcpcd.conf
```

```
interface wlan0
static ip_address=192.168.4.1/24
```

```
sudo chmod 600 /etc/hostapd/hostapd.conf
sudo chown root:root /etc/hostapd/hostapd.conf
```

```
sudo nano /etc/dnsmasq.conf
```
```
interface=wlan0
no-dhcp-interface=wlan1
dhcp-range=interface:wlan0,192.168.4.1,192.168.4.100,infinite
```

```
sudo systemctl daemon-reload
sudo systemctl enable dhcpcd
sudo systemctl enable dnsmasq
sudo systemctl enable hostapd
sudo reboot
```


