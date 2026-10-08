"""Icons: Material Symbols Rounded (weight 400, Apache 2.0), bundled as SVG in
``ui/assets/icons`` and recoloured at runtime from the tokens.

    icon_pixmap("check_circle", COLORS.success, 24, filled=True)
    Icon("usb", SIZES.icon_m, COLORS.text_2)

Each name has an outline file (``name.svg``) and a filled one (``name-fill.svg``).
"""

from __future__ import annotations

import math
from functools import lru_cache
from importlib import resources

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from parkomate.ui.theme.tokens import COLORS, SIZES

_FOLDER = resources.files("parkomate.ui.assets").joinpath("icons")


def icon_names() -> list[str]:
    return sorted(
        p.name.removesuffix(".svg")
        for p in _FOLDER.iterdir()
        if p.name.endswith(".svg") and not p.name.endswith("-fill.svg")
    )


# TEMPORARY: pre-redesign icon names used by screens not rebuilt yet.
_LEGACY = {
    "cross": "close", "warn": "warning", "clock": "schedule", "pcb": "developer_board",
    "screw": "build", "sticker": "label", "qr": "qr_code_2", "sensor": "sensors",
    "indicator": "lightbulb", "connector": "cable", "box": "inventory_2", "plug": "usb",
    "chip": "memory", "thermo": "device_thermostat", "camera": "photo_camera", "user": "person",
    "list": "fact_check",
}


@lru_cache(maxsize=512)
def _renderer(name: str, filled: bool) -> QSvgRenderer:
    name = _LEGACY.get(name, name)
    file = f"{name}-fill.svg" if filled else f"{name}.svg"
    entry = _FOLDER.joinpath(file)
    if not entry.is_file():
        entry = _FOLDER.joinpath("help.svg")  # unknown name: a visible question mark
    return QSvgRenderer(QByteArray(entry.read_bytes()))


@lru_cache(maxsize=2048)
def _image(name: str, color: str, px: int, filled: bool, alpha: float) -> QImage:
    image = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _renderer(name, filled).render(painter, QRectF(0, 0, px, px))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    tint = QColor(color)
    tint.setAlphaF(alpha)
    painter.fillRect(image.rect(), tint)
    painter.end()
    return image


def icon_image(
    name: str, color: str, size: int, *, filled: bool = False, dpr: float = 1.0, alpha: float = 1.0
) -> QImage:
    px = max(1, math.ceil(size * dpr))
    image = _image(name, color, px, filled, round(alpha, 3))
    if dpr != 1.0:
        image = QImage(image)
        image.setDevicePixelRatio(dpr)
    return image


def icon_pixmap(
    name: str, color: str, size: int, *, filled: bool = False, dpr: float = 1.0
) -> QPixmap:
    return QPixmap.fromImage(icon_image(name, color, size, filled=filled, dpr=dpr))


def qicon(name: str, color: str = COLORS.text_2, size: int = SIZES.icon_m) -> QIcon:
    return QIcon(icon_pixmap(name, color, size))


def paint_icon(
    painter: QPainter,
    name: str,
    rect: QRectF,
    color: str | QColor,
    *,
    filled: bool = False,
    alpha: float = 1.0,
) -> None:
    """Draw icon ``name`` centred in ``rect`` (square), tinted ``color``."""
    size = min(rect.width(), rect.height())
    if size <= 0:
        return
    hex_color = color.name() if isinstance(color, QColor) else color
    if isinstance(color, QColor) and color.alphaF() < 1.0:
        alpha *= color.alphaF()
    dpr = painter.device().devicePixelRatioF() if painter.device() is not None else 1.0
    image = icon_image(name, hex_color, math.ceil(size), filled=filled, dpr=dpr, alpha=alpha)
    target = QRectF(
        rect.x() + (rect.width() - size) / 2, rect.y() + (rect.height() - size) / 2, size, size
    )
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawImage(target, image)
    painter.restore()


class Icon(QWidget):
    """A fixed-size icon. Decorative: excluded from the accessibility tree by default."""

    def __init__(
        self,
        name: str,
        size: int = SIZES.icon_m,
        color: str | None = None,
        parent: QWidget | None = None,
        *,
        filled: bool = False,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._color = color or COLORS.text_2
        self._filled = filled
        self.setFixedSize(QSize(size, size))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_icon(self, name: str, color: str | None = None, *, filled: bool | None = None) -> None:
        self._name = name
        if color is not None:
            self._color = color
        if filled is not None:
            self._filled = filled
        self.update()

    def name(self) -> str:
        return self._name

    def color(self) -> str:
        return self._color

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        paint_icon(painter, self._name, QRectF(self.rect()), self._color, filled=self._filled)
        painter.end()
