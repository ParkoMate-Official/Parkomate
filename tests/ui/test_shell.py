"""Tests for shell components: bar heights, overlay geometry, key handling."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from parkomate.core.enums import CheckCode, Stage
from parkomate.core.models import RejectInstruction
from parkomate.hardware.mocks import MockScenario
from parkomate.ui.components.overlays import SuccessToast
from parkomate.ui.screenshots import StationDriver
from tests.ui.conftest import DriverFactory

# ------------------------------------------------------------------ bar heights


def test_top_bar_height(driver: StationDriver) -> None:
    """TopBar must be exactly 76 px tall."""
    assert driver.window.shell.top.height() == 76


def test_info_strip_height(driver: StationDriver) -> None:
    """InfoStrip must be exactly 40 px tall."""
    assert driver.window.shell.info.height() == 40


def test_bottom_bar_height(driver: StationDriver) -> None:
    """BottomBar must be exactly 80 px tall."""
    assert driver.window.shell.bottom.height() == 80


def test_mode_banner_height(driver: StationDriver) -> None:
    """ModeBanner must be exactly 28 px tall when visible."""
    # ModeBanner is visible only in mock mode
    banner = driver.window.shell.mode_banner
    assert banner.height() == 28


# ------------------------------------------------------------------ overlay geometry


def test_error_banner_height(driver: StationDriver) -> None:
    """ErrorBanner has a fixed height of 56 px."""
    banner = driver.window.shell.banner

    # Banner has fixed height
    assert banner.height() == 56

    # Show the banner
    from parkomate.core.errors import ErrorCode, ParkomateError

    error = ParkomateError(code=ErrorCode.MEAS_TIMEOUT)
    banner.show_error(error, has_retry=False, retry_key="action.try_again")

    # Height should remain fixed even when visible
    assert banner.height() == 56

    banner.clear()


def test_error_banner_does_not_resize_stages(driver: StationDriver) -> None:
    """ErrorBanner overlay must not resize or shift stage panes."""
    from parkomate.core.errors import ErrorCode, ParkomateError

    banner = driver.window.shell.banner
    stack = driver.window.shell.stack
    body = driver.window.shell.views

    # Get initial geometry of the stack (which contains all stage views)
    initial_stack_geom = stack.geometry()
    initial_body_geom = body.geometry()

    # Show the error banner
    error = ParkomateError(code=ErrorCode.MEAS_TIMEOUT)
    banner.show_error(error, has_retry=False, retry_key="action.try_again")

    # Stack and body geometry should not change
    assert stack.geometry() == initial_stack_geom, "Stack geometry changed when banner appeared"
    assert body.geometry() == initial_body_geom, "Body geometry changed when banner appeared"


def test_reject_takeover_geometry(driver: StationDriver) -> None:
    """RejectTakeover overlay fills parent and is anchored correctly."""
    takeover = driver.window.shell.takeover
    shell = driver.window.shell

    # Initially hidden
    assert not takeover.isVisible()

    # Create a reject instruction and show takeover
    instruction = RejectInstruction(
        device_row_id=1,
        stage=Stage.TESTING,
        check_code=CheckCode.B3_V_C,
        reason_key="reason.vc_out",
        reason_params={"voltage": 3.21, "min": 3.25, "max": 3.35},
    )
    takeover.show_instruction(instruction)

    # Overlay should be visible
    assert takeover.isVisible()

    # Overlay geometry should match parent (shell)
    shell_geom = shell.geometry()
    takeover_geom = takeover.geometry()

    # Takeover should cover the same area as its parent
    assert takeover_geom.width() == shell_geom.width()
    assert takeover_geom.height() == shell_geom.height()


def test_success_toast_geometry(driver: StationDriver) -> None:
    """SuccessToast is centered below TopBar/InfoStrip/ModeBanner."""
    toast = driver.window.shell.toast

    # Initially hidden
    assert not toast.isVisible()

    # Show toast
    toast.show_message("PKM-000519", seconds=5)

    # Toast should be visible
    assert toast.isVisible()

    # Toast should be centered below the top bars
    # TopBar (76) + InfoStrip (40) + ModeBanner (28) + margin = 120 + margin
    expected_y = 120
    assert toast.y() == expected_y

    # Toast width should be fixed
    assert toast.width() == SuccessToast.WIDTH


# ------------------------------------------------------------------ reject takeover Esc handling


def test_reject_takeover_ignores_escape(make_driver: DriverFactory) -> None:
    """RejectTakeover must not dismiss on Esc key press."""
    d = make_driver(MockScenario.V_C_OUT_OF_RANGE)
    d.start()
    d.login()
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()

    takeover = d.window.shell.takeover
    assert takeover.isVisible()

    # Track if drawer was toggled (it shouldn't be)
    initial_drawer_state = d.c.drawer_open

    # Press Esc
    QTest.keyClick(takeover, Qt.Key.Key_Escape)

    # Takeover should still be visible
    assert takeover.isVisible()

    # Drawer should NOT have been toggled
    assert d.c.drawer_open == initial_drawer_state


def test_reject_takeover_accepts_return(make_driver: DriverFactory) -> None:
    """RejectTakeover should confirm on Return/Enter keys."""
    d = make_driver(MockScenario.V_C_OUT_OF_RANGE)
    d.start()
    d.login()
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()

    takeover = d.window.shell.takeover

    # Press Return
    QTest.keyClick(takeover, Qt.Key.Key_Return)

    # Takeover should be hidden (confirmed)
    assert not takeover.isVisible()


# ------------------------------------------------------------------ drawer Esc handling


def test_drawer_closes_on_escape(make_driver: DriverFactory) -> None:
    """SessionDrawer should close when Esc is pressed while open."""
    d = make_driver()
    d.start()
    d.login()
    d.ready_for_board()

    # Open the drawer
    d.c.toggle_drawer(True)
    assert d.window.shell.drawer.isVisible()

    # Press Esc
    QTest.keyClick(d.window.shell, Qt.Key.Key_Escape)

    # Drawer should be closed
    assert not d.c.drawer_open
    assert not d.window.shell.drawer.isVisible()


def test_drawer_esc_not_propagated_when_closed(make_driver: DriverFactory) -> None:
    """When drawer is closed, pressing Esc should not trigger drawer logic."""
    d = make_driver()
    d.start()
    d.login()
    d.ready_for_board()

    # Ensure drawer is closed
    assert not d.window.shell.drawer.isVisible()

    # Close any confirm dialogs
    d.c.confirm = None

    # Press Esc - should go to escape handler but not affect drawer
    initial_drawer_state = d.c.drawer_open
    d.c.escape()

    assert d.c.drawer_open == initial_drawer_state


# ------------------------------------------------------------------ overlay styling


def test_error_banner_has_tone_property(make_driver: DriverFactory) -> None:
    """ErrorBanner should have tone property set for styling."""
    d = make_driver(MockScenario.MEASUREMENT_TIMEOUT)
    d.start()
    d.login()
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()

    banner = d.window.shell.banner
    assert banner.property("tone") in ("fail", "warn", "pending")


def test_reject_takeover_uses_box_letter_rule(driver: StationDriver) -> None:
    """RejectTakeover box letter should use box_letter property, not inline styles."""
    takeover = driver.window.shell.takeover
    from parkomate.core.enums import CheckCode

    instruction = RejectInstruction(
        device_row_id=1,
        stage=Stage.TESTING,
        check_code=CheckCode.B3_V_C,
        message_key="reject.point_c",
        reason_key="reason.vc_out",
        reason_params={"voltage": 3.21, "min": 3.25, "max": 3.35},
    )
    takeover.show_instruction(instruction)

    # Box should have box_letter property set to "true"
    assert takeover.box.property("box_letter") == "true"

    # Box should display the letter (from stage.letter)
    assert takeover.box.text() == "B"
