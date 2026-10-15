"""Repair tab on the 12-column grid.

Left 5 columns: the faulty boards (Open / Closed, find by scanning or typing the ID or MAC).
Right 7 columns: the selected board - what failed, the four steps (Rejected → Repaired →
Tested again → Accepted / Scrapped), the repair form and, when asked, the scrap form.
The next step is THE primary action in the bottom bar (see ``RepairViewModel``).
"""

from __future__ import annotations

from typing import Any, ClassVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from parkomate.core.enums import (
    RepairAction,
    RepairEventKind,
    RepairStatus,
    ScrapReason,
)
from parkomate.core.models import Device, RepairEventRecord
from parkomate.i18n import t
from parkomate.ui.components.buttons import AppButton
from parkomate.ui.components.cards import Card, EmptyState, InlineMessage
from parkomate.ui.components.chips import StatusChip
from parkomate.ui.components.data import ChipDelegate, DataTable
from parkomate.ui.components.inputs import FormField, Select, TextField
from parkomate.ui.components.layout import ScrollArea, column_grid
from parkomate.ui.components.segmented import SegmentedControl
from parkomate.ui.components.stepper import StepList
from parkomate.ui.components.text import MessageText, Text
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme.tokens import SPACE
from parkomate.ui.viewmodels.repair import RepairViewModel
from parkomate.ui.viewmodels.station import StationController
from parkomate.workflow.repair import Fault, RepairCaseDetail, RepairService

STATUS_CHIP: dict[RepairStatus, str] = {
    RepairStatus.WAITING: "warning",
    RepairStatus.REPAIRED: "info",
    RepairStatus.RETESTING: "working",
    RepairStatus.PASSED: "success",
    RepairStatus.ACCEPTED: "success",
    RepairStatus.SCRAPPED: "danger",
}


def local_dt(value: Any) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M") if value is not None else ""


Line = tuple[str, dict[str, Any]]
"""A message key and its params (``*_key`` params are translated too)."""


class LinePool:
    """The text lines under one step; widgets are reused, never deleted (stable layout)."""

    def __init__(self, layout: QVBoxLayout) -> None:
        self._layout = layout
        self._lines: list[MessageText] = []

    def show(self, lines: list[Line]) -> None:
        while len(self._lines) < len(lines):
            line = MessageText("", "body", "secondary", wrap=True)
            self._layout.addWidget(line)
            self._lines.append(line)
        for index, widget in enumerate(self._lines):
            if index < len(lines):
                key, params = lines[index]
                widget.set_key(key, **params)
                widget.setVisible(True)
            else:
                widget.set_key(None)
                widget.setVisible(False)

    def texts(self) -> list[str]:
        return [w.text() for w in self._lines if not w.isHidden()]


def fault_params(fault: Fault) -> dict[str, Any]:
    device = fault.device
    stage = device.reject_stage
    code = device.reject_check_code
    return {
        "box": stage.letter if stage else "-",
        "stage_key": stage.label_key if stage else "stage.rejected",
        "check_key": code.label_key if code else "stage.rejected",
    }


class RepairView(QWidget):
    vm: RepairViewModel
    FILTERS: ClassVar[list[tuple[bool, str]]] = [
        (True, "repair.filter.open"),
        (False, "repair.filter.closed"),
    ]
    COLUMNS = (
        "repair.col.board",
        "repair.col.status",
        "repair.col.fault",
    )  # fault last: it may shorten

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self.vm = controller.repair
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.left = self._build_list()
        self.right_scroll = ScrollArea()
        self.right = self.right_scroll.layout_
        layout.addLayout(column_grid(self.left, self.right_scroll))
        self._build_detail()
        self.vm.changed.connect(self.update_view)
        language_notifier().changed.connect(self._retranslate)
        self._retranslate()
        self.update_view()

    # ================================================================== left: the list
    def _build_list(self) -> Card:
        card = Card("repair.list_title", icon="build")
        self.count_chip = StatusChip(compact=True)
        card.add_trailing(self.count_chip)
        self.filter = SegmentedControl(self.FILTERS)
        self.filter.changed.connect(lambda value: self.vm.set_show_open(bool(value)))
        card.body.addWidget(self.filter, 0, Qt.AlignmentFlag.AlignLeft)
        self.search = TextField("repair.search_hint", max_width=None)
        self.search.setProperty("enter_submits", True)
        self.search.returnPressed.connect(self._search)
        self.search.textChanged.connect(self._search_cleared)
        card.body.addWidget(self.search)
        self.table = DataTable(
            self.COLUMNS,
            mono=(0,),
            empty=("task_alt", "repair.empty_title", "repair.empty_body"),
        )
        self.table.setItemDelegateForColumn(1, ChipDelegate({}, self.table))
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.body.addWidget(self.table, 1)
        return card

    def _search(self) -> None:
        self.vm.set_search(self.search.text())

    def _search_cleared(self, text: str) -> None:
        if not text.strip() and self.vm.search:
            self.vm.set_search("")

    def _selected(self) -> None:
        ids = self.table.selected_data()
        if ids:
            self.vm.select(int(ids[0]))

    # ================================================================== right: the case
    def _build_detail(self) -> None:
        self.result = InlineMessage()
        self.right.addWidget(self.result)
        self.empty = Card()
        self.empty.body.addWidget(
            EmptyState("build", "repair.none_selected_title", "repair.none_selected_body")
        )
        self.right.addWidget(self.empty)

        # board header + what failed
        self.board_card = Card(icon="memory")
        self.board_title = Text("", "mono_title")
        self.board_card.header.insertWidget(1, self.board_title, 1)
        self.status_chip = StatusChip()
        self.status_chip.reserve(*(s.label_key for s in RepairStatus))
        self.board_card.add_trailing(self.status_chip)
        self.board_info = MessageText("", "body", "secondary", wrap=True)
        self.board_card.body.addWidget(self.board_info)
        self.fault_card = Card("repair.fault_title", icon="error", compact=True)
        self.fault_card.set_variant("danger")
        self.fault_line = MessageText("", "body_lg_strong", wrap=True)
        self.fault_reason = MessageText("", "body", wrap=True)
        self.fault_when = MessageText("", "caption", "tertiary", wrap=True)
        for widget in (self.fault_line, self.fault_reason, self.fault_when):
            self.fault_card.body.addWidget(widget)
        self.fault_card.body.setSpacing(SPACE.xs)
        self.board_card.body.addWidget(self.fault_card)
        self.right.addWidget(self.board_card)

        # the four steps
        self.steps_card = Card("repair.steps_title")
        self.steps = StepList(
            [
                "repair.step.rejected",
                "repair.step.repaired",
                "repair.step.retested",
                "repair.step.decision",
            ]
        )
        self.step_rejected, self.step_repaired, self.step_retested, self.step_decision = (
            self.steps.items
        )
        self.step_lines: list[LinePool] = []
        for item in self.steps.items:
            body = QVBoxLayout()
            body.setSpacing(SPACE.xs)
            item.body.addLayout(body)
            self.step_lines.append(LinePool(body))
        self.steps_card.body.addWidget(self.steps)

        # repair form
        self.repair_card = Card("repair.form_title", subtitle_key="repair.form_help", icon="edit")
        self.action_select = Select(max_width=None)
        self.action_select.set_placeholder_key("repair.form.action_placeholder")
        self.action_select.activated.connect(self._action_chosen)
        self.repair_card.body.addWidget(FormField("repair.form.action", self.action_select))
        self.note = TextField("repair.form.note_placeholder", max_width=None)
        self.note.textChanged.connect(self.vm.set_note)
        self.repair_card.body.addWidget(FormField("repair.form.note", self.note))
        row = QHBoxLayout()
        row.addStretch(1)
        self.save_button = AppButton("action.save_repair", variant="tonal", icon="check")
        self.save_button.clicked.connect(self.vm.save_repair)
        row.addWidget(self.save_button)
        self.repair_card.body.addLayout(row)
        self.right.addWidget(self.repair_card)

        # scrap form
        self.scrap_card = Card(
            "repair.scrap_title", subtitle_key="repair.scrap_help", icon="dangerous"
        )
        self.scrap_card.set_variant("danger")
        self.scrap_select = Select(max_width=None)
        self.scrap_select.set_placeholder_key("repair.form.reason_placeholder")
        self.scrap_select.activated.connect(self._reason_chosen)
        self.scrap_card.body.addWidget(FormField("repair.form.reason", self.scrap_select))
        self.scrap_note = TextField("repair.form.note_placeholder", max_width=None)
        self.scrap_note.textChanged.connect(self.vm.set_scrap_note)
        self.scrap_card.body.addWidget(FormField("repair.form.note", self.scrap_note))
        self.right.addWidget(self.scrap_card)
        # the history last: what to do now is always on screen first
        self.right.addWidget(self.steps_card)
        self.right.addStretch(1)

    def _action_chosen(self, index: int) -> None:
        value = self.action_select.itemData(index)
        self.vm.set_action(RepairAction(value) if value else None)

    def _reason_chosen(self, index: int) -> None:
        value = self.scrap_select.itemData(index)
        self.vm.set_scrap_reason(ScrapReason(value) if value else None)

    def _retranslate(self, *_args: object) -> None:
        for select, values in (
            (self.action_select, list(RepairAction)),
            (self.scrap_select, list(ScrapReason)),
        ):
            current = select.currentData()
            select.blockSignals(True)
            select.clear()
            for value in values:
                select.addItem(t(value.label_key), value.value)
            select.setCurrentIndex(select.findData(current) if current else -1)
            select.blockSignals(False)
        self.action_select.setAccessibleName(t("repair.form.action"))
        self.scrap_select.setAccessibleName(t("repair.form.reason"))
        self.search.setAccessibleName(t("repair.search_hint"))
        self.table.setAccessibleName(t("repair.list_title"))
        delegate = self.table.itemDelegateForColumn(1)
        if isinstance(delegate, ChipDelegate):
            delegate.tones = {
                t(status.label_key).upper(): STATUS_CHIP[status] for status in RepairStatus
            }
        self.update_view()

    # ================================================================== render
    def update_view(self, *_args: object) -> None:
        vm = self.vm
        self._render_list()
        detail = vm.detail
        self.empty.setVisible(detail is None)
        for widget in (self.board_card, self.steps_card):
            widget.setVisible(detail is not None)
        if vm.message is None:
            self.result.clear()
            self.result.setVisible(False)
        else:
            key, params = vm.message
            self.result.ok(t(key, **params))
            self.result.setVisible(True)
        if detail is None:
            self.repair_card.setVisible(False)
            self.scrap_card.setVisible(False)
            return
        self._render_board(detail)
        self._render_steps(detail)
        self._render_forms(detail)

    def _render_list(self) -> None:
        vm = self.vm
        self.filter.set_value(vm.show_open, animate=False)
        self.count_chip.set_state(
            "warning" if vm.open_count else "success", "repair.open_count", n=vm.open_count
        )
        if self.search.text().strip() != vm.search and not self.search.hasFocus():
            self.search.setText(vm.search)
        rows = []
        for view in vm.cases:
            fault = view.latest_fault
            stage = fault.reject_stage
            code = fault.reject_check_code
            fault_text = t(
                "repair.col.fault_cell",
                box=stage.letter if stage else "-",
                check=t(code.label_key) if code else "",
            )
            rows.append([view.board_id, t(view.case.status.label_key), fault_text])
        self.table.blockSignals(True)
        self.table.fill(rows, [view.case.id for view in vm.cases])
        for row, view in enumerate(vm.cases):
            if view.case.id == vm.selected_id:
                self.table.selectRow(row)
                break
        else:
            self.table.clearSelection()
        self.table.blockSignals(False)

    def _render_board(self, detail: RepairCaseDetail) -> None:
        view = detail.view
        case = detail.case
        self.board_title.setText(view.board_id)
        self.status_chip.set_state(STATUS_CHIP[case.status], case.status.label_key)
        self.board_info.set_key(
            "repair.board_info",
            mac=case.mac_address,
            case=case.id,
            repairs=view.repairs,
            retests=view.retests,
        )
        latest = detail.faults[-1] if detail.faults else Fault(view.origin, None)
        again = latest.device.id != view.origin.id
        self.fault_card.set_title_key("repair.fault_again" if again else "repair.fault_title")
        self.fault_line.set_key("repair.fault_line", **fault_params(latest))
        device = latest.device
        if device.reject_reason_key:
            self.fault_reason.set_key(device.reject_reason_key, **device.reject_reason_params)
        else:
            self.fault_reason.set_key(None)
            self.fault_reason.setText(device.reject_reason or "")
        opened = next(
            (e for e in detail.events if e.device_row_id == device.id),
            None,
        )
        who = detail.operator_name(opened.operator_id) if opened else ""
        self.fault_when.set_key(
            "repair.fault_when", time=local_dt(device.finished_at), who=who or "-"
        )

    def _render_steps(self, detail: RepairCaseDetail) -> None:
        case = detail.case
        status = case.status
        events = detail.events
        pools = self.step_lines
        # 1 - rejected
        self.step_rejected.set_state(
            "pass", "repair.caption.when", time=local_dt(detail.view.origin.finished_at)
        )
        pools[0].show([("repair.fault_line", fault_params(Fault(detail.view.origin, None)))])
        # 2 - repaired
        repairs = [e for e in events if e.event is RepairEventKind.REPAIRED]
        pools[1].show([self._repair_line(detail, event) for event in repairs])
        if status is RepairStatus.WAITING:
            self.step_repaired.set_state("working", "repair.caption.repair_now")
        elif repairs:
            self.step_repaired.set_state("pass", "repair.caption.repairs", n=len(repairs))
        else:
            self.step_repaired.set_state("pending")
        # 3 - tested again
        runs = {run.id: run for run in detail.runs}
        retest_events = [
            e
            for e in events
            if e.event
            in (
                RepairEventKind.RETEST_PASSED,
                RepairEventKind.RETEST_FAILED,
                RepairEventKind.RETEST_CANCELLED,
            )
        ]
        pools[2].show(
            [
                self._retest_line(event, runs.get(event.device_row_id or -1))
                for event in retest_events
            ]
        )
        last = retest_events[-1].event if retest_events else None
        if status is RepairStatus.RETESTING:
            self.step_retested.set_state("working", "repair.caption.on_line")
        elif status in (RepairStatus.PASSED, RepairStatus.ACCEPTED) or (
            last is RepairEventKind.RETEST_PASSED
        ):
            self.step_retested.set_state("pass", "repair.caption.passed")
        elif last is RepairEventKind.RETEST_FAILED and status is RepairStatus.WAITING:
            self.step_retested.set_state("fail", "repair.caption.failed_again")
        elif status is RepairStatus.REPAIRED:
            self.step_retested.set_state("working", "repair.caption.test_now")
        else:
            self.step_retested.set_state("pending")
        # 4 - decision
        closing = next(
            (
                e
                for e in reversed(events)
                if e.event in (RepairEventKind.ACCEPTED, RepairEventKind.SCRAPPED)
            ),
            None,
        )
        pools[3].show([self._closing_line(detail, closing)] if closing is not None else [])
        if status is RepairStatus.ACCEPTED:
            self.step_decision.set_state("pass", "repair.status.accepted")
        elif status is RepairStatus.SCRAPPED:
            self.step_decision.set_state("fail", "repair.status.scrapped")
        elif status is RepairStatus.PASSED:
            self.step_decision.set_state("working", "repair.caption.accept_now")
        else:
            self.step_decision.set_state("pending")

    @staticmethod
    def _repair_line(detail: RepairCaseDetail, event: RepairEventRecord) -> Line:
        action = event.action or ""
        key = RepairAction(action).label_key if action in RepairAction else "repair.action.other"
        return (
            "repair.entry",
            {
                "action_key": key,
                "note": f" - {event.note}" if event.note else "",
                "time": local_dt(event.created_at),
                "who": detail.operator_name(event.operator_id) or "-",
            },
        )

    @staticmethod
    def _retest_line(event: RepairEventRecord, run: Device | None) -> Line:
        if event.event is RepairEventKind.RETEST_FAILED and run is not None:
            stage = run.reject_stage
            code = run.reject_check_code
            return (
                "repair.retest_failed_line",
                {
                    "time": local_dt(event.created_at),
                    "box": stage.letter if stage else "-",
                    "check_key": code.label_key if code else "stage.rejected",
                },
            )
        key = (
            "repair.retest_passed_line"
            if event.event is RepairEventKind.RETEST_PASSED
            else "repair.retest_cancelled_line"
        )
        return key, {"time": local_dt(event.created_at)}

    @staticmethod
    def _closing_line(detail: RepairCaseDetail, event: RepairEventRecord) -> Line:
        reason = event.action or ""
        reason_key = (
            ScrapReason(reason).label_key
            if event.event is RepairEventKind.SCRAPPED and reason in ScrapReason
            else "repair.accepted_line"
        )
        return (
            "repair.closing_line",
            {
                "what_key": reason_key,
                "note": f" - {event.note}" if event.note else "",
                "time": local_dt(event.created_at),
                "who": detail.operator_name(event.operator_id) or "-",
            },
        )

    def _render_forms(self, detail: RepairCaseDetail) -> None:
        vm = self.vm
        repairable = RepairService.repair_blocker(detail.case) is None
        self.repair_card.setVisible(repairable and not vm.scrapping)
        index = self.action_select.findData(vm.action.value) if vm.action else -1
        if self.action_select.currentIndex() != index:
            self.action_select.setCurrentIndex(index)
        if self.note.text() != vm.note:
            self.note.blockSignals(True)
            self.note.setText(vm.note)
            self.note.blockSignals(False)
        reason = vm.repair_reason()
        self.save_button.setEnabled(reason is None)
        self.save_button.set_caption(reason)
        was_visible = self.scrap_card.isVisible()
        self.scrap_card.setVisible(vm.scrapping)
        if vm.scrapping and not was_visible:
            self.right_scroll.ensureWidgetVisible(self.scrap_card)
        index = self.scrap_select.findData(vm.scrap_reason.value) if vm.scrap_reason else -1
        if self.scrap_select.currentIndex() != index:
            self.scrap_select.setCurrentIndex(index)
        if self.scrap_note.text() != vm.scrap_note:
            self.scrap_note.blockSignals(True)
            self.scrap_note.setText(vm.scrap_note)
            self.scrap_note.blockSignals(False)


__all__ = ["RepairView"]
