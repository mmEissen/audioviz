import ring_client
import typing as t
from threading import Thread

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtWidgets import QWidget


class LedRingWidget(QWidget):
    _radius = 200
    _led_radius = 10
    _size = _radius * 2 + _led_radius

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
        angle = 360 / self.num_leds

        for color in self.colors:
            painter.setBrush(color)
            painter.drawEllipse(center, self._led_radius, self._led_radius)
            painter.rotate(angle)

        painter.end()


class Qt5RingClient(ring_client.AbstractClient):

    def __init__(self, num_leds: int, num_colors: int) -> None:
        super().__init__(num_leds, num_colors)
        self._main_widget = LedRingWidget(num_leds)
    
    def connect(self) -> None:
        self._main_widget.show()
    
    def disconnect(self) -> None:
        self._main_widget.close()
    
    def is_connected(self) -> bool:
        return not self._main_widget.isHidden()
    
    def show(self) -> None:
        self._main_widget.colors = [QColor(pixel.red * 255, pixel.green * 255, pixel.blue * 255) for pixel in self._pixels]
        self._main_widget.update()

    