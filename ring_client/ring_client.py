import abc
import re
import socket
import time
import threading
from collections import deque
import typing as t

import numpy as np

from .profiler import Profiler
from . import gamma_table


class InvalidConfigHeaderError(Exception):
    pass


class ConnectionError(OSError):
    pass


class NotConnectedError(Exception):
    pass


class PixelOutOfRangeError(IndexError):
    pass


class Pixel:
    # taken from https://learn.adafruit.com/led-tricks-gamma-correction/the-quick-fix
    _gamma_table = gamma_table.gamma_table

    _percieved_luminance = np.array([0.2126, 0.7152, 0.0722])

    def __init__(self, red, green, blue) -> None:
        self._values = np.array((red, green, blue))

    def __repr__(self) -> str:
        return "<{}:{}>".format(self.__class__.__name__, self.get_rgbw())

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
    def __init__(self, port: int) -> None:
        self._socket = None
        self._port = port

    def _bind_socket(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except OSError as error:
            self._socket = None
            raise ConnectionError("Error creating socket") from error
        try:
            self._socket.bind(("", self._port))
        except OSError as error:
            self._socket.close()
            self._socket = None
            raise ConnectionError("Error connecting to server") from error

    def _find_ip(self):
        message = b""
        while message != b"LEDRing\n":
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
        return "{}<{}X{}>".format(
            self.__class__.__name__, self.num_colors, self.num_leds
        )

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
        self, port: int, num_leds: int, num_colors: int, frame_number_bytes: int
    ) -> None:
        super().__init__(num_leds, num_colors)
        self._port = port
        self._ring_address = None
        self._tcp_socket: t.Optional[socket.socket] = None
        self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._frame_number_bytes = frame_number_bytes

    @classmethod
    def from_config_header(cls, filename: str) -> "RingClient":
        define_statement = re.compile(r"#define\W+(?P<name>\w+) (?P<value>.*)\n")
        with open(filename) as config_file:
            config_content = config_file.read()
        defines = dict(define_statement.findall(config_content))

        def _get_define(name: str) -> int:
            try:
                return int(defines[name])
            except KeyError as exception:
                raise InvalidConfigHeaderError(
                    "No define for {}".format(name)
                ) from exception
            except ValueError as exception:
                raise InvalidConfigHeaderError(
                    "{} is not an int".format(name)
                ) from exception

        port = _get_define("PORT")
        num_leds = _get_define("NUM_LEDS")
        num_colors = _get_define("NUM_COLORS")
        frame_number_bytes = _get_define("FRAME_NUMBER_BYTES")

        return cls(port, num_leds, num_colors, frame_number_bytes)

    def is_connected(self) -> bool:
        return self._tcp_socket is not None

    def connect(self) -> None:
        self._ring_address = RingDetective(self._port).find_ring_ip()
        try:
            self._tcp_socket = socket.socket()
        except OSError as error:
            self._tcp_socket = None
            raise ConnectionError("Error creating socket") from error
        try:
            self._tcp_socket.connect((self._ring_address, self._port))
        except OSError as error:
            self._tcp_socket.close()
            self._tcp_socket = None
            raise ConnectionError("Error connecting to server") from error

    def disconnect(self) -> None:
        if self.is_connected():
            self._tcp_socket = t.cast(socket.socket, self._tcp_socket)
            self._tcp_socket.close()

    def show(self) -> None:
        if not self.is_connected():
            raise NotConnectedError("Client must be connected before calling show()!")
        raw_data = bytes([0] * self._frame_number_bytes) + b"".join(
            pixel.to_bytes() for pixel in self._pixels
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
            print(Profiler.report(), end="\n\n")
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

