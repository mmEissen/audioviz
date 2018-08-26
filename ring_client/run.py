import typing as t
import sys

from PyQt5.QtWidgets import QApplication

import ring_client
import qt5_client


class Pulse:
    def __init__(self, num_leds: int) -> None:
        self._num_leds = num_leds

    def __call__(self, timestamp: float) -> t.List[ring_client.RGBWPixel]:
        intensity = (timestamp % 5) / 5
        return [ring_client.RGBWPixel(red=intensity, green=intensity, blue=intensity) for _ in range(self._num_leds)]


def main() -> None:
    application = QApplication(sys.argv)
    client = qt5_client.Qt5RingClient(60, 4)
    loop = ring_client.RenderLoop(client, Pulse(60))
    loop.start()
    return_code = application.exec_()
    loop.stop()
    sys.exit(return_code)


if __name__ == '__main__':
    main()