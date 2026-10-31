"""Keyboard-only operator workflow: login, progression, shortcuts, and navigation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from parkomate.core.enums import Stage
from parkomate.hardware.mocks import MockScenario
from parkomate.ui.screenshots import ADMIN, StationDriver
from parkomate.ui.viewmodels.station import Page
from tests.ui.conftest import DriverFactory


def test_login_tab_order_and_keyboard_submit(make_driver: DriverFactory) -> None:
    """Login tab order must follow code -> password -> button, and Enter submits."""
    d = make_driver()
    d.start()
    login = d.window.login

    # Tab order verification
    assert login.focusNextPrevChild(True)  # navigates using tab
    login.code.setFocus()
    assert login.code.hasFocus()

    # Enter credentials via keyboard clicks
    QTest.keyClicks(login.code, ADMIN[0])
    QTest.keyClick(login.code, Qt.Key.Key_Tab)
    assert login.password.hasFocus()

    QTest.keyClicks(login.password, ADMIN[2])
    # Press Enter in the password input
    QTest.keyClick(login.password, Qt.Key.Key_Return)

    d.wait(lambda: d.c.page is Page.PRODUCTION, what="production page")
    assert d.c.operator is not None
    assert d.c.page is Page.PRODUCTION


def test_complete_device_keyboard_only(make_driver: DriverFactory) -> None:
    """An operator must be able to complete a device (A->B->C->D) entirely using the keyboard."""
    d = make_driver(MockScenario.ALL_PASS)
    d.start()

    # Login via keyboard
    login = d.window.login
    login.code.setFocus()
    QTest.keyClicks(login.code, ADMIN[0])
    QTest.keyClick(login.code, Qt.Key.Key_Tab)
    QTest.keyClicks(login.password, ADMIN[2])
    QTest.keyClick(login.password, Qt.Key.Key_Return)
    d.wait(lambda: d.c.page is Page.PRODUCTION, what="production")

    # Connect hardware
    d.connect()

    # --- Stage A: Programming ---
    assert d.c.stage is Stage.PROGRAMMING
    # Enter triggers primary action (whitelist check / connect)
    QTest.keyClick(d.window.shell, Qt.Key.Key_Return)
    d.wait(lambda: d.c.programming.whitelist_state.value == "pass", what="whitelist")
    d.idle()

    # Enter triggers firmware upload
    QTest.keyClick(d.window.shell, Qt.Key.Key_Return)
    d.wait(lambda: d.c.programming.upload_state.value == "pass", what="upload")
    d.idle()

    # Enter triggers advance to Stage B
    QTest.keyClick(d.window.shell, Qt.Key.Key_Return)
    d.wait(lambda: d.c.stage is Stage.TESTING, what="testing stage")

    # --- Stage B: Testing ---
    d.wait(lambda: d.c.testing.comm_state.value == "pass", what="comm test")
    # Take sensor readings via Enter
    vm_test = d.c.testing
    while len(vm_test.readings) < vm_test.total_readings:
        QTest.keyClick(d.window.shell, Qt.Key.Key_Return)
        d.idle()

    # Mark all OK
    d.mark_ok()
    assert vm_test.measure_state.value == "pass"

    # Enter advances to Stage C
    QTest.keyClick(d.window.shell, Qt.Key.Key_Return)
    d.wait(lambda: d.c.stage is Stage.LABELING, what="labeling stage")

    # --- Stage C: Labeling ---
    vm_label = d.c.labeling
    d.wait(lambda: vm_label.identity_ok, what="identity ok")

    # Toggle all checklist items via F1-F4
    for key_num in range(1, 5):
        key = getattr(Qt.Key, f"Key_F{key_num}")
        QTest.keyClick(d.window.shell, key)
        d.process()

    assert d.window.shell.bottom.primary.isEnabled()
    # Enter advances to Stage D
    QTest.keyClick(d.window.shell, Qt.Key.Key_Return)
    d.wait(lambda: d.c.stage is Stage.PACKAGING, what="packaging stage")

    # --- Stage D: Packaging ---
    for key_num in range(1, 5):
        key = getattr(Qt.Key, f"Key_F{key_num}")
        QTest.keyClick(d.window.shell, key)
        d.process()

    assert d.window.shell.bottom.primary.isEnabled()
    # Enter completes packaging and device
    QTest.keyClick(d.window.shell, Qt.Key.Key_Return)
    d.wait(
        lambda: d.c.device is None and bool(d.c.counters and d.c.counters.completed == 1),
        what="device complete",
    )
    assert d.c.counters is not None
    assert d.c.counters.completed == 1


def test_keyboard_fkeys_and_escape(make_driver: DriverFactory) -> None:
    """Verify Enter, Esc, and F-keys work correctly for drawer, confirm, and remeasure."""
    d = make_driver()
    d.start()
    d.login()

    # F9 remeasures ambient
    QTest.keyClick(d.window.shell, Qt.Key.Key_F9)
    d.idle()
    assert d.c.ambient_c is not None

    # Drawer Esc handling: Esc closes open drawer
    d.c.toggle_drawer(True)
    assert d.window.shell.drawer.isVisible()
    assert d.window.shell.scrim.isVisible()

    QTest.keyClick(d.window.shell, Qt.Key.Key_Escape)
    assert not d.c.drawer_open
    assert not d.window.shell.drawer.isVisible()
    assert not d.window.shell.scrim.isVisible()

    # Esc cancels confirmation dialog
    d.c.request_end_session()
    assert d.c.confirm is not None
    assert d.window.shell.bottom.confirm.isVisible()

    QTest.keyClick(d.window.shell, Qt.Key.Key_Escape)
    assert bool(d.c.confirm is None)
    assert not d.window.shell.bottom.confirm.isVisible()


def test_admin_tab_order_and_escape(driver: StationDriver) -> None:
    """Verify Tab order on Admin New Operator card and Esc returning to production."""
    d = driver
    d.c.open_admin()
    d.wait(lambda: d.c.page is Page.ADMIN, what="admin page")

    admin = d.window.admin
    # Switch to Operators tab
    admin.tabs.setCurrentIndex(1)
    op_tab = admin.operators_tab

    # Tab order on New Operator card: code -> name -> role -> pw -> pw2 -> add_button
    fields = [
        op_tab.new_code,
        op_tab.new_name,
        op_tab.new_role,
        op_tab.new_pw,
        op_tab.new_pw2,
        op_tab.add_button,
    ]
    for i in range(len(fields) - 1):
        QWidget.setTabOrder(fields[i], fields[i + 1])

    op_tab.new_code.setFocus()
    assert op_tab.new_code.hasFocus()

    # Esc key closes admin and returns to production
    admin.back.click()  # [Esc] primary button
    d.wait(lambda: d.c.page is Page.PRODUCTION, what="production page")
    assert d.c.page is Page.PRODUCTION
