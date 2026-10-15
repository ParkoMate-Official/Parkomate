"""The Repair tab through the real UI on the mock bench: reject → repair → test again (the whole
line) → accept; a wrong board; scrap; and the language switch moving nothing."""

from __future__ import annotations

from parkomate.core.enums import RepairStatus, Stage
from parkomate.core.errors import ErrorCode
from parkomate.hardware.mocks import MockScenario
from parkomate.ui.screenshots import StationDriver
from parkomate.ui.viewmodels.station import Mode
from tests.ui.conftest import DriverFactory
from tests.ui.test_redesign import _assert_stable


def primary(d: StationDriver) -> str:
    action = d.window.shell.bottom.primary_action()
    assert action is not None
    return action.name


def reject_one_board(d: StationDriver) -> None:
    """V_C out of range: the board is rejected at B and its repair case opens."""
    d.start()
    d.login()
    d.ready_for_board()
    d.through_programming()
    d.read_all_sensors()
    d.mark_ok()
    d.wait(lambda: d.c.reject is not None, what="reject")
    d.enter()  # "Device placed in box"
    d.wait(lambda: d.c.reject is None and d.c.device is None, what="next board")


def open_repair(d: StationDriver) -> None:
    d.window.shell.top.mode.button(Mode.REPAIR).click()
    d.wait(lambda: d.c.mode is Mode.REPAIR, what="repair tab")
    d.process(30)


def save_repair(d: StationDriver, action: str = "regulator_replaced", note: str = "U3") -> None:
    view = d.window.shell.repair_view
    index = view.action_select.findData(action)
    view.action_select.setCurrentIndex(index)
    view.action_select.activated.emit(index)
    view.note.setText(note)
    d.process(20)
    assert view.save_button.isEnabled()
    view.save_button.click()
    d.process(20)


def test_repair_retest_and_accept(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.V_C_OUT_OF_RANGE)
    reject_one_board(d)
    open_repair(d)
    shell = d.window.shell
    view = shell.repair_view
    vm = d.c.repair
    assert shell.stack.currentWidget() is view
    assert shell.top.stepper.isHidden()  # no production stages on the Repair tab
    assert view.table.rowCount() == 1 and vm.detail is not None
    assert vm.case_status is RepairStatus.WAITING
    assert view.fault_card.isVisible()
    assert "Point C voltage" in view.fault_line.text()
    assert "3.21 V" in view.fault_reason.text() and "3.25-3.35 V" in view.fault_reason.text()
    assert view.table.item(0, 2).text() == "B · Point C voltage"
    assert primary(d) == "retest" and not shell.bottom.primary.isEnabled()
    assert shell.bottom.primary.caption() == "Save what you repaired first"
    assert not view.save_button.isEnabled()  # nothing chosen yet

    save_repair(d)
    assert vm.case_status is RepairStatus.REPAIRED
    assert view.result.text() == "Repair saved."
    assert view.step_repaired.state == "pass"
    assert primary(d) == "retest" and shell.bottom.primary.isEnabled()

    d.enter()  # Test again: the board goes through the whole line
    d.wait(lambda: d.c.mode is Mode.PRODUCTION and d.c.retest is not None, what="retest")
    assert shell.retest_banner.isVisible()
    assert d.c.stage is Stage.PROGRAMMING and not shell.top.stepper.isHidden()
    d.ready_for_board()
    d.full_device()  # the repaired board passes now
    d.wait(lambda: d.c.mode is Mode.REPAIR, what="back on the repair tab")
    assert d.c.retest is None and not shell.retest_banner.isVisible()
    assert vm.case_status is RepairStatus.PASSED
    assert view.step_retested.state == "pass"
    assert primary(d) == "accept"
    assert shell.bottom.primary.variant() == "success_filled"

    d.enter()  # Accept
    d.process(30)
    assert vm.message is not None and vm.message[0] == "repair.msg.accepted"
    assert vm.cases == [] and vm.detail is None  # nothing open any more
    assert d.c.counters is not None and d.c.counters.completed == 1
    assert d.c.counters.rejected == 1
    vm.set_show_open(False)
    assert [v.case.status for v in vm.cases] == [RepairStatus.ACCEPTED]
    assert view.step_decision.state == "pass"


def test_retest_refuses_another_board(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.V_C_OUT_OF_RANGE)
    reject_one_board(d)
    open_repair(d)
    save_repair(d, "no_fault_found", "")
    d.enter()  # Test again
    d.wait(lambda: d.c.retest is not None, what="retest")
    d.ready_for_board()
    d.hardware.expect_board("24:6F:28:00:00:99")  # somebody plugs in another board
    d.c.programming.connect_board()
    d.wait(lambda: d.c.error is not None, what="wrong board")
    assert d.c.error is not None and d.c.error.error.code is ErrorCode.REPAIR_WRONG_BOARD
    assert d.c.device is None
    d.window.shell.retest_cancel.click()  # nothing started: no question asked
    d.wait(lambda: d.c.mode is Mode.REPAIR, what="back to repair")
    assert d.c.retest is None
    assert d.c.repair.case_status is RepairStatus.REPAIRED


def test_cancel_a_running_retest(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.V_C_OUT_OF_RANGE)
    reject_one_board(d)
    open_repair(d)
    save_repair(d, "resoldered", "")
    d.enter()
    d.wait(lambda: d.c.retest is not None, what="retest")
    d.ready_for_board()
    d.connect()
    assert d.c.device is not None and d.c.device.repair_case_id is not None
    assert d.window.shell.top.mode.button(Mode.REPAIR).isEnabled() is False
    d.c.set_mode(Mode.REPAIR)  # refused while the board is on the line
    assert d.c.mode is Mode.PRODUCTION
    d.c.request_cancel_retest()
    assert d.c.confirm is not None
    d.enter()  # yes, stop it
    d.wait(lambda: d.c.mode is Mode.REPAIR, what="back to repair")
    assert d.c.repair.case_status is RepairStatus.REPAIRED
    assert d.c.device is None


def test_scrap_a_board(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.V_C_OUT_OF_RANGE)
    reject_one_board(d)
    open_repair(d)
    view = d.window.shell.repair_view
    bottom = d.window.shell.bottom
    assert [b.objectName() for b in bottom.secondary_buttons() if b.isVisible()] == [
        "secondary_scrap"
    ]
    bottom.secondary_buttons()[0].click()
    d.process(20)
    assert view.scrap_card.isVisible() and not view.repair_card.isVisible()
    assert primary(d) == "scrap_confirm" and not bottom.primary.isEnabled()
    assert bottom.primary.caption() == "Choose a reason"
    d.c.escape()  # Esc closes the form, nothing scrapped
    d.process(20)
    assert not view.scrap_card.isVisible()
    assert d.c.repair.case_status is RepairStatus.WAITING
    d.c.repair.open_scrap()
    index = view.scrap_select.findData("physical_damage")
    view.scrap_select.setCurrentIndex(index)
    view.scrap_select.activated.emit(index)
    view.scrap_note.setText("burnt track")
    d.process(20)
    assert bottom.primary.isEnabled() and bottom.primary.variant() == "danger_filled"
    d.enter()
    d.process(30)
    assert d.c.repair.cases == []
    assert d.c.repair.status() is not None
    assert d.c.repair.status().key == "status.repair.none_open"  # type: ignore[union-attr]
    d.c.set_mode(Mode.PRODUCTION)
    assert d.c.mode is Mode.PRODUCTION and d.c.stage is Stage.PROGRAMMING


def test_repair_tab_language_switch_moves_nothing(make_driver: DriverFactory) -> None:
    d = make_driver(MockScenario.V_C_OUT_OF_RANGE)
    reject_one_board(d)
    _assert_stable(d, "production with the mode switch")
    open_repair(d)
    _assert_stable(d, "repair tab, waiting")
    save_repair(d)
    _assert_stable(d, "repair tab, repaired")
