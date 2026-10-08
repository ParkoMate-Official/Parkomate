"""The ONE focus style (G2): a 1 px primary border with a 3 px primary halo at 40 %, drawn
around the focused control - only while the operator navigates with the keyboard
(like CSS ``:focus-visible``). A mouse click or touch hides it; Tab / arrow keys show it.

One overlay per window follows the focused widget (moves, resizes, scrolls). Widgets may set
the dynamic property ``ring_radius`` (default: the control radius).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QWidget

from parkomate.ui.components.base import qcolor
from parkomate.ui.theme.tokens import ALPHA, COLORS, RADIUS, SIZES

NAVIGATION_KEYS = {
    Qt.Key.Key_Tab,
    Qt.Key.Key_Backtab,
    Qt.Key.Key_Up,
    Qt.Key.Key_Down,
    Qt.Key.Key_Left,
    Qt.Key.Key_Right,
    Qt.Key.Key_Home,
    Qt.Key.Key_End,
    Qt.Key.Key_PageUp,
    Qt.Key.Key_PageDown,
}
POINTER_EVENTS = {
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseButtonDblClick,
    QEvent.Type.TouchBegin,
    QEvent.Type.TabletPress,
}
FOLLOW_EVENTS = {
    QEvent.Type.Move,
    QEvent.Type.Resize,
    QEvent.Type.Show,
    QEvent.Type.Hide,
    QEvent.Type.ParentChange,
}


class FocusRing(QWidget):
    """The overlay: transparent for the mouse, always on top inside its window."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self.setObjectName("FocusRing")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.target: QWidget | None = None
        self.hide()

    def margin(self) -> int:
        return SIZES.focus_ring + SIZES.focus_border

    def follow(self, target: QWidget | None) -> None:
        self.target = target
        self.reposition()

    def reposition(self) -> None:
        target = self.target
        window = self.parentWidget()
        if target is None or window is None or not target.isVisible() or not self._visible(target):
            self.hide()
            return
        top_left = target.mapTo(window, target.rect().topLeft())
        margin = self.margin()
        self.setGeometry(QRect(top_left, target.size()).adjusted(-margin, -margin, margin, margin))
        self.show()
        self.raise_()
        self.update()

    @staticmethod
    def _visible(target: QWidget) -> bool:
        """False when the widget is scrolled out of its scroll area."""
        region = target.visibleRegion()
        return not region.isEmpty()

    def paintEvent(self, _event: QPaintEvent) -> None:
        target = self.target
        if target is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = float(target.property("ring_radius") or RADIUS.control)
        halo = SIZES.focus_ring
        border = SIZES.focus_border
        outer = QRectF(self.rect()).adjusted(halo / 2, halo / 2, -halo / 2, -halo / 2)
        painter.setPen(QPen(qcolor(COLORS.primary, ALPHA.focus_halo), halo))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        r_outer = min(radius + halo / 2 + border, outer.height() / 2, outer.width() / 2)
        painter.drawRoundedRect(outer, r_outer, r_outer)
        inner = QRectF(self.rect()).adjusted(
            halo + border / 2, halo + border / 2, -halo - border / 2, -halo - border / 2
        )
        painter.setPen(QPen(QColor(COLORS.primary), border))
        r_inner = min(radius, inner.height() / 2, inner.width() / 2)
        painter.drawRoundedRect(inner, r_inner, r_inner)
        painter.end()


class FocusRingManager(QObject):
    """Application-wide event filter that drives one FocusRing per window."""

    _instance: FocusRingManager | None = None

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self.keyboard = False
        self._rings: dict[int, FocusRing] = {}
        self._watched: set[int] = set()  # ids of the focused widget and its ancestors
        app.installEventFilter(self)
        app.focusChanged.connect(self._focus_changed)

    @classmethod
    def install(cls, app: QApplication) -> FocusRingManager:
        if cls._instance is None:
            cls._instance = FocusRingManager(app)
        return cls._instance

    @classmethod
    def instance(cls) -> FocusRingManager | None:
        return cls._instance

    def ring_for(self, widget: QWidget | None) -> FocusRing | None:
        if widget is None:
            return None
        return self._rings.get(id(widget.window()))

    def visible_target(self) -> QWidget | None:
        for ring in self._rings.values():
            if ring.isVisible():
                return ring.target
        return None

    # ------------------------------------------------------------------ events
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if kind == QEvent.Type.KeyPress:
            if event.key() in NAVIGATION_KEYS and not self.keyboard:  # type: ignore[attr-defined]
                self.keyboard = True
                self._show_for(QApplication.focusWidget())
        elif kind in POINTER_EVENTS:
            if self.keyboard:
                self.keyboard = False
                self._hide_all()
        elif kind in FOLLOW_EVENTS and id(watched) in self._watched:
            ring = self._current_ring()
            if ring is not None:
                ring.reposition()
        return False

    def _current_ring(self) -> FocusRing | None:
        for ring in self._rings.values():
            if ring.target is not None:
                return ring
        return None

    def _focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        if self.keyboard:
            self._show_for(new)
        else:
            self._hide_all()

    def _show_for(self, widget: QWidget | None) -> None:
        self._hide_all()
        if widget is None or isinstance(widget, FocusRing) or widget.isWindow():
            return
        parent = widget.parentWidget()
        if isinstance(parent, QAbstractScrollArea) and parent.viewport() is widget:
            widget = parent
        window = widget.window()
        ring = self._rings.get(id(window))
        if ring is None:
            key = id(window)
            ring = FocusRing(window)
            self._rings[key] = ring

            def forget(*_args: object) -> None:
                self._rings.pop(key, None)

            window.destroyed.connect(forget)
        self._watch(widget)
        ring.follow(widget)

    def _watch(self, widget: QWidget) -> None:
        """Follow moves / resizes of the widget and every ancestor (scrolling moves them)."""
        chain: set[int] = set()
        current: QWidget | None = widget
        while current is not None and not current.isWindow():
            chain.add(id(current))
            current = current.parentWidget()
        self._watched = chain

    def _unwatch(self) -> None:
        self._watched = set()

    def _hide_all(self) -> None:
        self._unwatch()
        for ring in list(self._rings.values()):
            try:
                ring.follow(None)
            except RuntimeError:
                continue
