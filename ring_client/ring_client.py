import re
import socket

import colour


class InvalidConfigHeaderError(Exception):
    pass

class ConnectionError(OSError):
    pass


class RingClient(object):
    
    def __init__(self, port: int, num_leds: int, num_colors: int, ring_address: str='192.168.4.1'):
        self._ring_address = ring_address
        self._port = port
        self._socket = None
        self.num_leds = num_leds
        self.num_colors = num_colors
        self.frame_size = num_leds * num_colors
        self._pixels = []

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


def main():
    rc = RingClient.from_config_header('../tcp_to_led/config.h')
    print(rc)
    input('connect?')
    rc.connect()
    input('disconnect?')
    rc.disconnect()

if __name__ == '__main__':
    main()
