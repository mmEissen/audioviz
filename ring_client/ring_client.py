import abc
import re
import socket
import time
import threading
from collections import deque
import typing as t

import numpy as np
from profiler import Profiler


class InvalidConfigHeaderError(Exception):
    pass

class ConnectionError(OSError):
    pass

class NotConnectedError(Exception):
    pass

class PixelOutOfRangeError(IndexError):
    pass


class Pixel():
    # taken from https://learn.adafruit.com/led-tricks-gamma-correction/the-quick-fix
    _gamma_table = [
        0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
        0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  1,
        1,  1,  1,  1,  1,  1,  1,  1,  1,  2,  2,  2,  2,  2,  2,  2,
        2,  3,  3,  3,  3,  3,  3,  3,  4,  4,  4,  4,  4,  5,  5,  5,
        5,  6,  6,  6,  6,  7,  7,  7,  7,  8,  8,  8,  9,  9,  9, 10,
        10, 10, 11, 11, 11, 12, 12, 13, 13, 13, 14, 14, 15, 15, 16, 16,
        17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 24, 24, 25,
        25, 26, 27, 27, 28, 29, 29, 30, 31, 32, 32, 33, 34, 35, 35, 36,
        37, 38, 39, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 50,
        51, 52, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 68,
        69, 70, 72, 73, 74, 75, 77, 78, 79, 81, 82, 83, 85, 86, 87, 89,
        90, 92, 93, 95, 96, 98, 99, 101,102,104,105,107,109,110,112,114,
        115,117,119,120,122,124,126,127,129,131,133,135,137,138,140,142,
        144,146,148,150,152,154,156,158,160,162,164,167,169,171,173,175,
        177,180,182,184,186,189,191,193,196,198,200,203,205,208,210,213,
        215,218,220,223,225,228,231,233,236,239,241,244,247,249,252,255,
    ]

    _percieved_luminance = np.array([
        0.2126, 0.7152, 0.0722,
    ])

    def __init__(self, red, green, blue) -> None:
        self._values = np.array((red, green, blue))
    
    def __repr__(self) -> str:
        return '<{}:{}>'.format(self.__class__.__name__, self.get_rgbw())

    def get_rgbw(self):
        # For now just r, g, b, 0.
        # This might have a better solution:
        # http://www.mirlab.org/conference_papers/International_Conference/ICASSP%202014/papers/p1214-lee.pdf
        return np.append(self._values, [0]) * 255

    def get_rgb(self):
        return self._values * 255

    def to_bytes(self):
        return bytes(self._gamma_table[round(float(c))] for c in self.get_rgbw())


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

    def set_frame(self, frame: t.List[Pixel]) -> None:
        self._pixels = frame
    
    def clear_frame(self) -> t.List[Pixel]:
        return [Pixel(0, 0, 0) for _ in range(self.num_leds)]
    
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
    
    def __init__(
        self,
        port: int,
        num_leds: int,
        num_colors: int,
        frame_number_bytes: int,
    ) -> None:
        super().__init__(num_leds, num_colors)
        self._port = port
        self._ring_address = None
        self._tcp_socket = None
        self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._frame_number_bytes = frame_number_bytes

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
        frame_number_bytes = _get_define('FRAME_NUMBER_BYTES')

        return cls(port, num_leds, num_colors, frame_number_bytes)

    def is_connected(self) -> bool:
        return self._tcp_socket is not None

    def connect(self)-> None:
        self._ring_address = RingDetective(self._port).find_ring_ip()
        try:
            self._tcp_socket = socket.socket()
        except OSError as error:
            self._tcp_socket = None
            raise ConnectionError('Error creating socket') from error
        try:
            self._tcp_socket.connect((self._ring_address, self._port))
        except OSError as error:
            self._tcp_socket.close()
            self._tcp_socket = None
            raise ConnectionError('Error connecting to server') from error
    
    def disconnect(self) -> None:
        if self.is_connected():
            self._tcp_socket.close()
    
    def show(self) -> None:
        if not self.is_connected():
            raise NotConnectedError('Client must be connected before calling show()!')
        raw_data = (
            bytes([0] * self._frame_number_bytes) + 
            b''.join(pixel.to_bytes() for pixel in self._pixels)
        )
        self._udp_socket.sendto(raw_data, (self._ring_address, self._port))


class RenderLoop(threading.Thread):
    frame_buffer_size = 2

    def __init__(self, ring_client, update_fnc, max_framerate=120):
        super().__init__()
        self._frame_period = 1 / max_framerate
        self._update_fnc = update_fnc
        self._is_running = False
        self._ring_client = ring_client
        self._last_report = 0

    @Profiler.profile
    def _loop(self):
        draw_start_time = time.time()
        new_frame = self._update_fnc(draw_start_time)
        self._ring_client.set_frame(new_frame)
        self._ring_client.show()
        if draw_start_time - self._last_report > 5:
            self._last_report = draw_start_time
            print(Profiler.report(), end='\n\n')
        time_to_next_frame = self._frame_period - time.time() + draw_start_time
        if time_to_next_frame > 0:
            time.sleep(time_to_next_frame)

    def run(self):
        self._ring_client.connect()
        self._is_running = True
        while self._is_running:
            self._loop()
        self._ring_client.disconnect()
    
    def stop(self):
        self._is_running = False 
