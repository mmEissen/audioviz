import typing as t
from threading import Thread

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtWidgets import QWidget
import numpy as np

import ring_client
import audio_tools


class LedRingWidget(QWidget):
    _radius = 300
    _led_radius = 10
    _size = _radius * 2 + _led_radius * 2

    def __init__(self, num_leds: int) -> None:
        super().__init__()
        self.num_leds = num_leds
        self.setAutoFillBackground(True)
        self.resize(self._size, self._size)
        self.colors = [QColor() for _ in range(num_leds)]

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.setPen(QPen(Qt.NoPen))

        center = QPointF(0, self._radius)
        rect_size = 2 * self._led_radius + 4
        angle = 360 / self.num_leds

        for color in self.colors:
            painter.setBrush(QColor())
            painter.drawRect(
                -rect_size / 2, self._radius + rect_size / 2, rect_size, -rect_size
            )
            painter.setBrush(color)
            painter.drawEllipse(center, self._led_radius, self._led_radius)
            painter.rotate(angle)

        painter.end()


class Qt5RingClient(ring_client.AbstractClient):
    def __init__(self, num_leds: int) -> None:
        super().__init__(num_leds)
        self._main_widget = LedRingWidget(num_leds)

    def connect(self) -> None:
        self._main_widget.show()

    def disconnect(self) -> None:
        self._main_widget.close()

    def is_connected(self) -> bool:
        return not self._main_widget.isHidden()

    def show(self) -> None:
        self._main_widget.colors = [QColor(*pixel.get_rgb()) for pixel in self._pixels]
        self._main_widget.update()


class MockSinInput(audio_tools.AbstractAudioInput):
    _frequency = 536
    _amplitude = 50

    def __init__(
        self,
        sample_rate: int = 44100,
        period_size: int = 512,
        buffer_size: int = audio_tools.MS_IN_SECOND * 10,
    ) -> None:
        super().__init__(sample_rate, period_size, buffer_size)

    def start(self):
        pass

    def stop(self):
        pass

    def get_samples(self, num_samples: int) -> t.Iterable[float]:
        return (
            np.sin(
                np.linspace(0, num_samples / self.sample_rate, num_samples)
                * np.pi
                * 2
                * self._frequency
            )
            * self._amplitude
        )