import typing as t
import sys
import os

USE_MOCK = bool(os.environ.get('RING_QTMOCK_CLIENT'))
if USE_MOCK:
    from PyQt5.QtWidgets import QApplication
    import qt5_client

import ring_client


class Pulse:
    def __init__(self, num_leds: int) -> None:
        self._num_leds = num_leds

    def __call__(self, timestamp: float) -> t.List[ring_client.RGBWPixel]:
        intensity = (timestamp % 5) / 5
        return [ring_client.RGBWPixel(red=intensity, green=intensity, blue=intensity) for _ in range(self._num_leds)]


def qtmock_client_and_wait():
    application = QApplication(sys.argv)
    client = qt5_client.Qt5RingClient(60, 4)
    return client, application.exec_


def client_and_wait():
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tcp_to_led', 'config.h')
    client = ring_client.RingClient.from_config_header(config_file)

    def wait() -> int:
        input()
        return 0
    
    return client, wait


def main() -> None:
    if USE_MOCK:
        client, wait = qtmock_client_and_wait()
    else:
        client, wait = client_and_wait()
    
    loop = ring_client.RenderLoop(client, Pulse(60))
    loop.start()

    return_code = wait()

    loop.stop()
    sys.exit(return_code)


if __name__ == '__main__':
    main()