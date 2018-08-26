import abc
import re
import socket
import time
import threading
from collections import deque
import typing as t

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
        r, g, b, w = self.get_rgbw()
        return bytes(map(self._value_to_byte, [g, r, b, w]))
    
    def set_rgbw(self, rgbw):
        red, green, blue, white = rgbw
        self.set_rgb((red, green, blue))
        self.set_white(white)
    
    def get_rgbw(self):
        red, green, blue = self.get_rgb()
        return (red, green, blue, self.get_white())
    
    def __mul__(self, other):
        red, green, blue, white = self.get_rgbw()
        return self.__class__(
            red=red * other,
            green=green * other,
            blue=blue * other,
            white=white * other,
        )


class RingDetective(object):

    def __init__(self, port: int):
        self._socket = None
        self._port = port

    def _bind_socket(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except OSError as error:
            self._socket = None
            raise ConnectionError('Error creating socket') from error
        try:
            self._socket.bind(('', self._port))
        except OSError as error:
            self._socket.close()
            self._socket = None
            raise ConnectionError('Error connecting to server') from error
    
    def _find_ip(self):
        message = b''
        while message != b'LEDRing\n':
            message, _, _, (ip_address, _) = self._socket.recvmsg(32)
        return ip_address

    def find_ring_ip(self):
        self._bind_socket()
        return self._find_ip()


class AbstractClient(abc.ABC):
    def __init__(self, num_leds: int, num_colors: int) -> None:
        self.num_leds = num_leds
        self.num_colors = num_colors
        self.frame_size = num_leds * num_colors
        self._pixels = self.clear_frame()

    def __repr__(self) -> str:
        return '{}<{}X{}>'.format(self.__class__.__name__, self.num_colors, self.num_leds)

    def set_frame(self, frame: t.List[RGBWPixel]) -> None:
        self._pixels = frame
    
    def clear_frame(self) -> t.List[RGBWPixel]:
        return [RGBWPixel() for _ in range(self.num_leds)]
    
    @abc.abstractmethod
    def connect(self) -> None:
        pass
    
    @abc.abstractmethod
    def disconnect(self) -> None:
        pass
    
    @abc.abstractmethod
    def show(self) -> None:
        pass
    
    @abc.abstractmethod
    def is_connected(self) -> bool:
        pass


class RingClient(AbstractClient):
    
    def __init__(self, port: int, num_leds: int, num_colors: int) -> None:
        super().__init__(num_leds, num_colors)
        self._port = port
        self._socket = None

    @classmethod
    def from_config_header(cls, filename: str) -> 'RingClient':
        define_statement = re.compile(r'#define\W+(?P<name>\w+) (?P<value>.*)\n')
        with open(filename) as config_file:
            config_content = config_file.read()
        defines = dict(define_statement.findall(config_content))
        def _get_define(name: str) -> int:
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

    def is_connected(self) -> bool:
        return self._socket is not None

    def connect(self)-> None:
        ring_address = RingDetective(self._port).find_ring_ip()
        try:
            self._socket = socket.socket()
        except OSError as error:
            self._socket = None
            raise ConnectionError('Error creating socket') from error
        try:
            self._socket.connect((ring_address, self._port))
        except OSError as error:
            self._socket.close()
            self._socket = None
            raise ConnectionError('Error connecting to server') from error
    
    def disconnect(self) -> None:
        if self.is_connected():
            self._socket.close()
    
    def show(self) -> None:
        if not self.is_connected():
            raise NotConnectedError('Client must be connected before calling show()!')
        raw_data = b''.join(pixel.to_bytes() for pixel in self._pixels)
        # With the current implementation of tcp_to_led this might actually deadlock if raw_data
        # is longer than the buffer of the receiver.
        self._socket.sendall(raw_data)


class RenderLoop(threading.Thread):
    frame_buffer_size = 2

    def __init__(self, ring_client, update_fnc, max_framerate=60):
        super().__init__()
        self._frame_period = 1 / max_framerate
        self._update_fnc = update_fnc
        self._is_running = False
        self._ring_client = ring_client

    def run(self):
        self._ring_client.connect()
        self._is_running = True
        while self._is_running:
            draw_start_time = time.time()
            new_frame = self._update_fnc(draw_start_time)
            self._ring_client.set_frame(new_frame)
            self._ring_client.show()
            time_to_next_frame = self._frame_period - time.time() + draw_start_time
            if time_to_next_frame > 0:
                time.sleep(time_to_next_frame)
        self._ring_client.disconnect()
    
    def stop(self):
        self._is_running = False 
