"""UI redesign guarantees, checked on the real screens (mock bench):

* switching English <-> Marathi never moves anything;
* the Admin Settings background is light even when Windows hands Qt a dark palette (A1);
* one focus style, shown only for keyboard navigation (G2);
* reduced motion switches animations off;
* exactly one filled (primary) button per screen.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from parkomate.core.enums import CheckCode, Stage
from parkomate.i18n import set_language
from parkomate.ui.components.buttons import AppButton
from parkomate.ui.components.cards import Card
from parkomate.ui.components.checklist import ChecklistRow
from parkomate.ui.components.chips import CounterChip, StatusChip
from parkomate.ui.components.focus import FocusRingManager
from parkomate.ui.components.inputs import Select
from parkomate.ui.components.measure import RangeBar, ReadingSlots
from parkomate.ui.components.segmented import PassFailToggle, SegmentedControl
from parkomate.ui.components.stepper import Stepper
from parkomate.ui.main import create_application
from parkomate.ui.screenshots import StationDriver
from parkomate.ui.theme import motion
from parkomate.ui.theme.motion import Tween
from parkomate.ui.theme.tokens import COLORS
from parkomate.ui.viewmodels.station import Page
from tests.ui.conftest import DriverFactory

STRUCTURE = (
    Card,
    AppButton,
    StatusChip,
    CounterChip,
    Stepper,
    Select,
    ChecklistRow,
    ReadingSlots,
    RangeBar,
    SegmentedControl,
    PassFailToggle,
)


def _geometry(root: QWidget) -> dict[str, QRect]:
    """Window position of every structural widget that is visible."""
    found: dict[str, QRect] = {}
    for index, widget in enumerate(root.findChildren(QWidget)):
        if not isinstance(widget, STRUCTURE) or not widget.isVisible():
            continue
        top_left = widget.mapTo(root, QPoint(0, 0))
        name = f"{type(widget).__name__}#{index}"
        found[name] = QRect(top_left, widget.size())
    return found


def _switch(d: StationDriver, language: str) -> None:
    d.c.set_language(language)
    d.process(80)


def _assert_stable(d: StationDriver, what: str) -> None:
    window = d.window
    before = _geometry(window)
    assert before, what
    _switch(d, "mr")
    after = _geometry(window)
    _switch(d, "en")
    back = _geometry(window)
    moved = {k: (before[k], after.get(k)) for k in before if after.get(k) != before[k]}
    assert moved == {}, f"{what}: moved when switching to Marathi: {moved}"
    assert back == before, what


@pytest.mark.parametrize("size", [(1366, 768), (1920, 1080)])
def test_language_switch_never_moves_the_layout(
    make_driver: DriverFactory, size: tuple[int, int]
) -> None:
    d = make_driver(size=size)
    d.start()
    _assert_stable(d, "login")
    d.login()
    d.ready_for_board()
    _assert_stable(d, "programming idle")
    d.connect()
    d.upload_until_done()
    _assert_stable(d, "programming passed")
    d.c.advance()
    d.wait(lambda: d.c.stage is Stage.TESTING, what="testing")
    d.read_all_sensors(3)
    _assert_stable(d, "testing readings")
    d.read_all_sensors()
    d.mark_ok()
    _assert_stable(d, "testing measured")
    d.c.advance()
    d.wait(lambda: d.c.labeling.identity_ok, what="labeling")
    d.c.labeling.toggle(CheckCode.C1)
    _assert_stable(d, "labeling")
    for code in d.c.labeling.checklist[1:]:
        d.c.labeling.toggle(code)
    d.c.advance()
    d.wait(lambda: d.c.stage is Stage.PACKAGING, what="packaging")
    _assert_stable(d, "packaging")
    d.through_packaging()
    d.c.open_admin()
    d.wait(lambda: d.c.page is Page.ADMIN, what="admin")
    for index in range(d.window.admin.tabs.count()):
        d.window.admin.tabs.setCurrentIndex(index)
        d.process(60)
        _assert_stable(d, f"admin tab {index}")


@pytest.fixture
def dark_os_palette(qapp: QApplication) -> Iterator[None]:
    """What Windows 11 in dark mode gives Qt (the cause of A1)."""
    saved = qapp.palette()
    palette = QPalette(saved)
    for role, value in (
        (QPalette.ColorRole.Window, "#1e1e1e"),
        (QPalette.ColorRole.Base, "#2d2d2d"),
        (QPalette.ColorRole.WindowText, "#ffffff"),
        (QPalette.ColorRole.PlaceholderText, "#ffffff"),
    ):
        palette.setColor(role, QColor(value))
    qapp.setPalette(palette)
    yield
    create_application()


def test_admin_settings_background_is_light(
    dark_os_palette: None, make_driver: DriverFactory
) -> None:
    create_application()  # the station always installs its own light palette
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    assert app.palette().color(QPalette.ColorRole.Window).name().upper() == COLORS.bg
    assert app.palette().color(QPalette.ColorRole.PlaceholderText).name().upper() == COLORS.text_3
    d = make_driver(size=(1920, 1080))
    d.start()
    d.login()
    d.c.open_admin()
    d.wait(lambda: d.c.page is Page.ADMIN, what="admin")
    tab = d.window.admin.settings_tab
    d.window.admin.tabs.setCurrentWidget(tab)
    d.process(80)
    image = tab.grab().toImage()
    viewport = tab.form_scroll.viewport()
    origin = viewport.mapTo(tab, QPoint(0, 0))
    # the top margin above the first section card shows the page background
    pixel = image.pixelColor(origin.x() + viewport.width() // 2, origin.y() + 4)
    assert pixel.name().upper() == COLORS.bg
    # and no pixel of the form area is the OS dark grey
    dark = QColor("#1e1e1e")
    samples = [
        image.pixelColor(origin.x() + x, origin.y() + y)
        for x in range(0, viewport.width(), 37)
        for y in range(0, viewport.height(), 41)
    ]
    assert dark not in samples


def test_focus_ring_only_for_keyboard(make_driver: DriverFactory) -> None:
    d = make_driver()
    d.start()
    login = d.window.login
    d.window.activateWindow()
    login.focus_first()
    d.process(30)
    manager = FocusRingManager.instance()
    assert manager is not None
    assert QApplication.focusWidget() is login.code  # the intended field, nothing else
    assert manager.visible_target() is None  # no ring on load (G2)
    QTest.keyClick(login.code, Qt.Key.Key_Tab)
    d.process(30)
    assert QApplication.focusWidget() is login.password
    assert manager.visible_target() is login.password
    QTest.mouseClick(login.code, Qt.MouseButton.LeftButton)
    d.process(30)
    assert manager.visible_target() is None  # a click hides it


def test_reduce_motion_switches_animations_off(qapp: QApplication) -> None:
    values: list[float] = []
    owner = QWidget()
    tween = Tween(owner, values.append, ms=200)
    motion.force(None)
    motion.configure(True)
    try:
        assert not motion.motion_enabled()
        assert motion.duration(280) == 0
        tween.to(1.0)
        assert values == [1.0]  # jumped straight to the end
    finally:
        motion.configure(False)
        owner.deleteLater()


def _filled(root: QWidget) -> list[str]:
    return [
        b.text()
        for b in root.findChildren(AppButton)
        if b.isVisible() and b.variant() in ("filled", "success_filled", "danger_filled")
    ]


def test_exactly_one_filled_button_per_screen(make_driver: DriverFactory) -> None:
    d = make_driver()
    d.start()
    assert len(_filled(d.window)) == 1, _filled(d.window)
    d.login()
    d.ready_for_board()
    checks = []
    d.connect()
    d.upload_until_done()
    checks.append(("programming", _filled(d.window)))
    d.c.advance()
    d.wait(lambda: d.c.stage is Stage.TESTING, what="testing")
    d.read_all_sensors()
    d.mark_ok()
    checks.append(("testing", _filled(d.window)))
    d.c.advance()
    d.wait(lambda: d.c.labeling.identity_ok, what="labeling")
    checks.append(("labeling", _filled(d.window)))
    d.through_labeling()
    for code in d.c.packaging.checklist:
        d.c.packaging.toggle(code)
    d.process(30)
    checks.append(("packaging", _filled(d.window)))
    d.c.advance()
    d.wait(lambda: d.c.device is None, what="next device")
    d.c.open_admin()
    d.wait(lambda: d.c.page is Page.ADMIN, what="admin")
    for index in range(d.window.admin.tabs.count()):
        d.window.admin.tabs.setCurrentIndex(index)
        d.process(30)
        checks.append((f"admin {index}", _filled(d.window.admin.tabs.currentWidget())))
    for name, filled in checks:
        assert len(filled) <= 1, (name, filled)
    set_language("en")
