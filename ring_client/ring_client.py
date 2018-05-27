import re
import socket

from colour import Color


class InvalidConfigHeaderError(Exception):
    pass

class ConnectionError(OSError):
    pass

class NotConnectedError(Exception):
    pass

class PixelOutOfRangeError(IndexError):
    pass

class RGBWPixel(Color):
    _white = 0

    def __setattr__(self, label, value):
        if label.startswith('_'):
            self.__dict__[label] = value
        else:
            super().__setattr__(label, value)

    def set_white(self, value):
        if 0 > value > 1.0:
            raise ValueError('White must be between 0 and 1. You provided {}.'.format(value))
        self._white = value
    
    def get_white(self):
        return self._white

    @staticmethod
    def _value_to_byte(value):
        return round(value * 255)

    def to_bytes(self):
        rgbw = (self.red, self.green, self.blue, self.white)
        return bytes(map(self._value_to_byte, rgbw))


class RingClient(object):
    
    def __init__(self, port: int, num_leds: int, num_colors: int, ring_address: str='192.168.4.1'):
        self._ring_address = ring_address
        self._port = port
        self._socket = None
        self.num_leds = num_leds
        self.num_colors = num_colors
        self.frame_size = num_leds * num_colors
        self._pixels = [RGBWPixel() for _ in range(num_leds)]

    def __repr__(self):
        return '{}@{}:{}'.format(self.__class__.__name__, self._ring_address, self._port)

    @classmethod
    def from_config_header(cls, filename):
        define_statement = re.compile(r'#define\W+(?P<name>\w+) (?P<value>.*)\n')
        with open(filename) as config_file:
            config_content = config_file.read()
        defines = dict(define_statement.findall(config_content))
        def _get_define(name):
            try:
                return int(defines[name])
            except KeyError as exception:
                raise InvalidConfigHeaderError('No define for {}'.format(name)) from exception
            except ValueError as exception:
                raise InvalidConfigHeaderError('{} is not an int'.format(name)) from exception
        
        port = _get_define('PORT')
        num_leds = _get_define('NUM_LEDS')
        num_colors = _get_define('NUM_COLORS')

        return cls(port, num_leds, num_colors)

    def is_connected(self):
        return self._socket is not None

    def connect(self):
        try:
            self._socket = socket.socket()
        except OSError as error:
            self._socket = None
            raise ConnectionError('Error creating socket') from error
        try:
            self._socket.connect((self._ring_address, self._port))
        except OSError as error:
            self._socket.close()
            self._socket = None
            raise ConnectionError('Error connecting to server') from error
    
    def disconnect(self):
        if self.is_connected():
            self._socket.close()
    
    def show(self):
        if not self.is_connected():
            raise NotConnectedError('Client must be connected before calling show()!')
        raw_data = b''.join(pixel.to_bytes() for pixel in self._pixels)
        # With the current implementation of tcp_to_led this might actually deadlock if raw_data
        # is longer thatn the buffer of the receiver.
        self._socket.sendall(raw_data)
    
    def set_pixel(self, number: int, pixel: RGBWPixel):
        try:
            self._pixels[number] = pixel
        except IndexError as error:
            raise PixelOutOfRangeError() from error


def main():
    rc = RingClient.from_config_header('../tcp_to_led/config.h')
    print(rc)
    input('connect?')
    rc.connect()
    input('set?')
    rc.set_pixel(10, RGBWPixel(white=1.0))
    rc.set_pixel(11, RGBWPixel(red=1, green=1, blue=1))
    rc.set_pixel(12, RGBWPixel(red=1, green=1, blue=1, white=1))
    rc.show()
    input('disconnect?')
    rc.disconnect()

if __name__ == '__main__':
    main()
