"""Draw the app icon (the product mark: blue rounded square, white "P") to ``parkomate.ico``.

    uv run python packaging/make_icon.py [target.ico]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

from parkomate.ui.main import create_application
from parkomate.ui.theme.tokens import COLORS

SIZE = 256


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("parkomate.ico")
    create_application()  # loads the bundled Noto Sans
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(COLORS.primary))
    painter.drawRoundedRect(QRectF(8, 8, SIZE - 16, SIZE - 16), 48, 48)
    font = QFont("Noto Sans")
    font.setPixelSize(int(SIZE * 0.62))
    font.setWeight(QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(COLORS.on_primary))
    painter.drawText(QRectF(0, 0, SIZE, SIZE * 0.96), Qt.AlignmentFlag.AlignCenter, "P")
    painter.end()
    if not pixmap.save(str(target), "ICO"):
        print(f"could not write {target}", file=sys.stderr)  # noqa: T201
        return 1
    print(target)  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
