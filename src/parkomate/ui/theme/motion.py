"""Motion: durations, easing and a small animation helper.

Durations come from ``tokens.MOTION`` (120 ms hover/press, 200 ms state change, 280 ms
enter/exit, OutCubic). With reduced motion every animation jumps straight to its end value
and looping animations (camera scan line, spinner) stand still.

Reduced motion is on when ``[ui] reduce_motion = true`` in the settings OR Windows reports
that animations are switched off (Settings > Accessibility > Visual effects).
"""

from __future__ import annotations

import ctypes
import logging
import sys
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEasingCurve, QObject, QVariantAnimation

log = logging.getLogger(__name__)

_settings_reduce = False
_forced: bool | None = None  # tests / screenshots: None = follow settings + OS
_os_cache: bool | None = None


def os_prefers_reduced_motion() -> bool:
    """True when Windows has client-area animations switched off."""
    global _os_cache
    if _os_cache is not None:
        return _os_cache
    result = False
    if sys.platform == "win32":
        try:
            enabled = ctypes.c_bool(True)
            spi_get_client_area_animation = 0x1042
            ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
                spi_get_client_area_animation, 0, ctypes.byref(enabled), 0
            )
            result = bool(ok) and not enabled.value
        except (AttributeError, OSError):
            log.debug("could not read the Windows animation setting", exc_info=True)
    _os_cache = result
    return result


def configure(reduce_motion: bool) -> None:
    """Apply the ``ui.reduce_motion`` setting."""
    global _settings_reduce
    _settings_reduce = bool(reduce_motion)


def force(enabled: bool | None) -> None:
    """Override for tests and screenshots (``None`` = back to settings + OS)."""
    global _forced
    _forced = enabled


def motion_enabled() -> bool:
    if _forced is not None:
        return _forced
    return not (_settings_reduce or os_prefers_reduced_motion())


def duration(ms: int) -> int:
    return ms if motion_enabled() else 0


class Tween(QObject):
    """Animates one float from its current value to a target and calls ``on_value``."""

    def __init__(
        self,
        parent: QObject,
        on_value: Callable[[float], None],
        *,
        value: float = 0.0,
        ms: int,
        easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._on_value = on_value
        self._ms = ms
        self._animation = QVariantAnimation(self)
        self._animation.setEasingCurve(easing)
        self._animation.valueChanged.connect(self._changed)

    @property
    def value(self) -> float:
        return self._value

    def _changed(self, value: Any) -> None:
        self._value = float(value)
        self._on_value(self._value)

    def to(self, target: float, ms: int | None = None) -> None:
        if abs(target - self._value) < 1e-6 and self._animation.state() is not (
            QVariantAnimation.State.Running
        ):
            return
        self._animation.stop()
        length = duration(self._ms if ms is None else ms)
        if length <= 0:
            self._changed(target)
            return
        self._animation.setDuration(length)
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(float(target))
        self._animation.start()

    def jump(self, target: float) -> None:
        self._animation.stop()
        self._changed(target)

    def stop(self) -> None:
        self._animation.stop()


class FrameClock(QObject):
    """One ~60 fps timer shared by every looping animation (spinners, scan line).

    Runs only while something is subscribed and motion is enabled; ``phase(period)`` gives a
    0..1 position within a loop of ``period`` ms.
    """

    _instance: FrameClock | None = None

    def __init__(self) -> None:
        super().__init__()
        from PySide6.QtCore import QElapsedTimer, QTimer

        from parkomate.ui.theme.tokens import MOTION

        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._timer = QTimer(self)
        self._timer.setInterval(MOTION.frame_interval)
        self._timer.timeout.connect(self._tick)
        self._subscribers: dict[int, Callable[[], None]] = {}

    @classmethod
    def instance(cls) -> FrameClock:
        if cls._instance is None:
            cls._instance = FrameClock()
        return cls._instance

    def subscribe(self, owner: QObject, callback: Callable[[], None]) -> None:
        key = id(owner)
        if key in self._subscribers:
            return
        self._subscribers[key] = callback
        owner.destroyed.connect(lambda *_a, k=key: self._subscribers.pop(k, None))
        if motion_enabled() and not self._timer.isActive():
            self._timer.start()

    def unsubscribe(self, owner: QObject) -> None:
        self._subscribers.pop(id(owner), None)
        if not self._subscribers:
            self._timer.stop()

    def phase(self, period_ms: int) -> float:
        if not motion_enabled() or period_ms <= 0:
            return 0.0
        return (self._elapsed.elapsed() % period_ms) / period_ms

    def _tick(self) -> None:
        if not self._subscribers or not motion_enabled():
            self._timer.stop()
            return
        for callback in list(self._subscribers.values()):
            try:
                callback()
            except RuntimeError:  # the widget was deleted on the C++ side
                continue
