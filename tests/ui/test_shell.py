"""Tests for shell components: bar heights, overlay geometry, key handling."""

from __future__ import annotations

from datetime import UTC

import pytest
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
    """ErrorBanner height is computed from content and never clips."""
    banner = driver.window.shell.banner

    # Banner has min height when empty
    assert banner.height() >= 40

    # Show the banner
    from parkomate.core.errors import ErrorCode, ParkomateError

    error = ParkomateError(code=ErrorCode.MEAS_TIMEOUT)
    banner.show_error(error, has_retry=False, retry_key="action.try_again")
    driver.process(30)

    # Height should compute from content and be >= sizeHint
    assert banner.height() >= banner.sizeHint().height()

    banner.clear()


def test_error_banner_does_not_resize_stages(driver: StationDriver) -> None:
    """ErrorBanner adapts height and preserves stage width without horizontal shift."""
    from parkomate.core.errors import ErrorCode, ParkomateError

    banner = driver.window.shell.banner
    stack = driver.window.shell.stack
    initial_stack_width = stack.width()

    # Show the error banner
    error = ParkomateError(code=ErrorCode.MEAS_TIMEOUT)
    banner.show_error(error, has_retry=False, retry_key="action.try_again")
    driver.process(30)

    # Height adapts to content and width is preserved
    assert banner.height() >= banner.sizeHint().height()
    assert stack.width() == initial_stack_width
    assert stack.isVisible()


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


@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5])
def test_shell_no_clipping_at_scales(driver: StationDriver, scale: float) -> None:
    """Build the shell at 1366x768 with: long operator name, 3-step error banner, Marathi text.

    Assert no widget text is clipped (widget height >= sizeHint height) and
    no overlapping geometry between banner buttons.
    """
    from datetime import datetime

    from parkomate.core.enums import Role
    from parkomate.core.errors import ErrorCode, ParkomateError
    from parkomate.core.models import Operator

    d = driver
    # Resize window to effective size under scale factor
    d.window.resize(int(1366 / scale), int(768 / scale))

    # 1. Long operator name
    long_name = "Dr. Alexandrina Anastasia Montgomery-Smythe (Quality Inspector)"
    op = Operator(
        id=99,
        operator_code="OP-99",
        full_name=long_name,
        role=Role.OPERATOR,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    d.c.operator = op

    # 2. Marathi text
    d.c.set_language("mr")

    # 3. 3-step error banner (MEAS_TIMEOUT action has 3 steps)
    error = ParkomateError(code=ErrorCode.MEAS_TIMEOUT)
    d.window.shell.banner.show_error(error, has_retry=True, retry_key="action.try_again")

    d.process(60)

    info = d.window.shell.info
    banner = d.window.shell.banner

    # Assert InfoStrip height >= sizeHint height
    assert info.height() >= info.sizeHint().height()

    # Assert ErrorBanner height >= sizeHint height
    assert banner.height() >= banner.sizeHint().height()

    # Assert no widget text in banner is clipped
    assert banner.title.height() >= banner.title.heightForWidth(banner.title.width())
    assert banner.cause_label.height() >= banner.cause_label.heightForWidth(
        banner.cause_label.width()
    )
    assert banner.steps.height() >= banner.steps.heightForWidth(banner.steps.width())

    # Assert action buttons have min width and do not overlap
    assert banner.retry_button.width() >= 140
    retry_geo = banner.retry_button.geometry()
    details_geo = banner.details_link.geometry()
    assert not retry_geo.intersects(details_geo), f"Buttons overlap: {retry_geo} vs {details_geo}"

    # Clean up
    d.c.set_language("en")
    banner.clear()
    d.window.resize(1366, 768)
