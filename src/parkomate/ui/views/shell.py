"""Production shell, top to bottom:

1. SimulationBand (amber, only on the simulated bench)
2. AppBar 72 px: mark + title | stage Stepper (centre) | SimulationChip · EN/मराठी · account
3. ContextBar 48 px: device · operator · session timer | counter chips
4. Content: error banner + the stage screen (12-column grid, max 1600 px, centred)
5. ActionBar 88 px: status (icon + text) | secondary + THE primary action (+ reason)

Overlays: session drawer (with scrim), reject takeover, success toast.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from parkomate.core.enums import PRODUCTION_STAGES, DeviceStatus, Stage
from parkomate.i18n import t
from parkomate.ui.components.base import Divider, add_shadow, qcolor
from parkomate.ui.components.buttons import AppButton
from parkomate.ui.components.cards import InlineConfirm, KpiTile
from parkomate.ui.components.chips import SimulationChip, StatusChip
from parkomate.ui.components.icons import Icon, qicon
from parkomate.ui.components.overlays import ErrorBanner, RejectTakeover, Toast
from parkomate.ui.components.popup import Menu, MenuItem
from parkomate.ui.components.segmented import LanguageSwitch
from parkomate.ui.components.shellparts import (
    AccountButton,
    ContextBar,
    ProductMark,
    SimulationBand,
    initials,
)
from parkomate.ui.components.stepper import Stepper
from parkomate.ui.components.text import Text, TrText
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme.tokens import ALPHA, COLORS, SIZES, SPACE
from parkomate.ui.viewmodels.base import Action, StatusLine
from parkomate.ui.viewmodels.station import Page, StationController
from parkomate.ui.views.stages import LabelingView, PackagingView, ProgrammingView, TestingView

# status tone -> (icon, graphic colour, text tone)
_TONE_ICON = {
    "pass": ("check_circle", COLORS.success, "success"),
    "fail": ("cancel", COLORS.danger, "danger"),
    "warn": ("warning", COLORS.warning, "warning"),
    "pending": ("schedule", COLORS.text_3, "secondary"),
    "info": ("info", COLORS.info, "primary"),
}


def format_duration(seconds: int) -> str:
    hours, rest = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def render_status(status: StatusLine) -> str:
    params = dict(status.params)
    keys = params.pop("items_keys", None)
    more = int(params.pop("more", 0) or 0)
    if keys is not None:
        params["items"] = ", ".join(t(k) if isinstance(k, str) else t(k[0], **k[1]) for k in keys)
    action_key = params.pop("action_key", None)
    if isinstance(action_key, str):
        action_params = params.pop("action_params", {})
        params["action"] = t(
            action_key, **(action_params if isinstance(action_params, dict) else {})
        )
    text = t(status.key, **params)
    if more:
        text = f"{text} {t('status.and_more', n=more)}"
    return text


def page_margin(width: int) -> int:
    """Side margin: 24 px (32 from 1600 px); the content is never wider than 1600 px."""
    margin = SIZES.page_margin_wide if width >= SIZES.wide_breakpoint else SIZES.page_margin
    return max(margin, (width - SIZES.content_max) // 2)


def stage_states(controller: StationController) -> list[str]:
    state = controller.device
    stages = list(PRODUCTION_STAGES)
    if state is not None and state.status is DeviceStatus.COMPLETE:
        return ["done"] * len(stages)
    rejected = controller.reject is not None or (
        state is not None and state.status is DeviceStatus.REJECTED
    )
    current = controller.stage if controller.stage in stages else Stage.PROGRAMMING
    index = stages.index(current)
    states = []
    for i in range(len(stages)):
        if i < index:
            states.append("done")
        elif i == index:
            states.append("rejected" if rejected else "active")
        else:
            states.append("upcoming")
    return states


def _paint_bar(widget: QWidget, *, line_at_top: bool) -> None:
    painter = QPainter(widget)
    rect = widget.rect()
    painter.fillRect(rect, QColor(COLORS.surface))
    y = 0 if line_at_top else rect.height() - SIZES.hairline
    painter.fillRect(QRectF(0, y, rect.width(), SIZES.hairline), QColor(COLORS.outline_soft))
    painter.end()


# ============================================================================ app bar


class _Avatar(QWidget):
    def __init__(self, label: Text) -> None:
        super().__init__()
        self.setFixedSize(SIZES.avatar, SIZES.avatar)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.primary_cont))
        painter.drawEllipse(QRectF(self.rect()))
        painter.end()


class AppBar(QFrame):
    def __init__(self, controller: StationController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("AppBar")
        self.setFixedHeight(SIZES.app_bar)
        grid = QGridLayout(self)
        grid.setContentsMargins(SIZES.page_margin, 0, SIZES.page_margin, 0)
        grid.setHorizontalSpacing(SPACE.l)
        left = QHBoxLayout()
        left.setSpacing(SPACE.m)
        left.addWidget(ProductMark())
        self.brand = TrText("app.brand", "body_lg_strong")
        left.addWidget(self.brand)
        left.addStretch(1)
        self.stepper = Stepper([stage.label_key for stage in PRODUCTION_STAGES])
        right = QHBoxLayout()
        right.setSpacing(SPACE.m)
        right.addStretch(1)
        self.mock = SimulationChip()
        right.addWidget(self.mock)
        self.language = LanguageSwitch()
        self.language.language_selected.connect(controller.set_language)
        right.addWidget(self.language)
        self.account = AccountButton()
        self.account.clicked.connect(self.open_menu)
        right.addWidget(self.account)
        grid.addLayout(left, 0, 0)
        grid.addWidget(self.stepper, 0, 1, Qt.AlignmentFlag.AlignCenter)
        grid.addLayout(right, 0, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        self.menu = self._build_menu()

    def _build_menu(self) -> Menu:
        menu = Menu(self)
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(SPACE.l, SPACE.s, SPACE.l, SPACE.s)
        row.setSpacing(SPACE.m)
        self.menu_avatar = Text("", "label", "info", align=Qt.AlignmentFlag.AlignCenter)
        row.addWidget(_Avatar(self.menu_avatar))
        names = QVBoxLayout()
        names.setSpacing(0)
        self.menu_name = Text("", "body_strong")
        self.menu_role = Text("", "caption", "secondary")
        names.addWidget(self.menu_name)
        names.addWidget(self.menu_role)
        row.addLayout(names, 1)
        menu.add_header(header)
        self.session_item = menu.add_item("menu.session", "history", self._open_drawer)
        self.admin_item = menu.add_item("action.admin", "admin_panel_settings", self.c.open_admin)
        self.logout_item = menu.add_item(
            "action.logout", "logout", self.c.request_end_session, danger=True
        )
        menu.closed.connect(self._menu_closed)
        return menu

    def _open_drawer(self) -> None:
        self.c.toggle_drawer(True)

    def _menu_closed(self) -> None:
        self.account.set_open(False)

    @property
    def admin_button(self) -> MenuItem:
        """The Admin entry of the account menu."""
        return self.admin_item

    def open_menu(self) -> None:
        self.refresh()
        self.account.set_open(True)
        self.menu.open_at(self.account, align_right=True)
        self.session_item.setFocus()

    def set_wide(self, wide: bool) -> None:
        self.account.set_compact(not wide)

    def refresh(self) -> None:
        c = self.c
        self.stepper.set_states(stage_states(c))
        self.language.sync(c.language())
        self.mock.setVisible(c.ctx.using_mocks)
        self.mock.set_scenario(str(getattr(c.ctx.hardware, "scenario", "")))
        operator = c.operator
        name = operator.full_name if operator else ""
        self.account.set_name(name)
        self.account.setAccessibleName(t("menu.account"))
        self.menu_avatar.setText(initials(name))
        self.menu_name.setText(name)
        self.menu_role.setText(
            f"{operator.operator_code} · {t(operator.role.label_key)}" if operator else ""
        )
        self.admin_item.setVisible(c.is_admin)  # operators never see Admin (T4)
        allowed = c.can_open_admin()
        self.admin_item.setEnabled(allowed)
        self.admin_item.set_reason(None if allowed else "gate.admin_device_busy")

    def paintEvent(self, _event: QPaintEvent) -> None:
        _paint_bar(self, line_at_top=False)


# ============================================================================ action bar


class ActionBar(QFrame):
    """Left: one status message with icon (in Testing also an 'x of y checks done' chip).
    Right: secondary actions + THE primary action; its disabled reason is a caption below."""

    def __init__(self, controller: StationController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("BottomBar")
        self.setFixedHeight(SIZES.action_bar)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SIZES.page_margin, 0, SIZES.page_margin, 0)
        self._stack = QStackedWidget()
        outer.addWidget(self._stack)
        self.normal = QWidget()
        row = QHBoxLayout(self.normal)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACE.m)
        self.progress = StatusChip("info")
        self.progress.reserve("status.checks_done")
        self.progress.setVisible(False)
        row.addWidget(self.progress)
        self.status_icon = Icon("info", SIZES.icon_m, COLORS.info, filled=True)
        row.addWidget(self.status_icon)
        self.status = Text("", "body_lg", wrap=True)
        row.addWidget(self.status, 1)
        self.secondary_box = QHBoxLayout()
        self.secondary_box.setSpacing(SPACE.m)
        row.addLayout(self.secondary_box)
        self.primary = AppButton(variant="filled")
        self.primary.setMinimumWidth(SIZES.primary_action)
        self.primary.clicked.connect(self._trigger_primary)
        row.addWidget(self.primary)
        self._stack.addWidget(self.normal)
        self.confirm = InlineConfirm()
        self.confirm.answered.connect(controller.answer)
        self._stack.addWidget(self.confirm)
        self._primary_action: Action | None = None
        self._secondary_actions: list[Action] = []
        self._secondary_buttons: list[AppButton] = []
        language_notifier().changed.connect(self.refresh)

    def primary_action(self) -> Action | None:
        return self._primary_action

    def secondary_buttons(self) -> list[AppButton]:
        return list(self._secondary_buttons)

    def _trigger_primary(self) -> None:
        if self._primary_action is not None:
            self._primary_action.trigger()

    def refresh(self, *_args: object) -> None:
        c = self.c
        confirm = c.confirm
        if confirm is not None:
            self._stack.setCurrentWidget(self.confirm)
            self.confirm.show_confirm(
                t(confirm.message_key, **_resolve(confirm.params)),
                confirm.yes_key,
                confirm.no_key,
                confirm.danger,
            )
            self.confirm.yes_button.setFocus()
            return
        self.confirm.setVisible(False)
        self._stack.setCurrentWidget(self.normal)
        vm = c.current_vm
        if vm is None or c.reject is not None:
            self._primary_action = None
            self.primary.setVisible(False)
            self.status.setText("")
            self.status_icon.setVisible(False)
            self.progress.setVisible(False)
            self.primary.set_caption(None)
            self._set_secondary([])
            return
        action = vm.primary()
        self._primary_action = action
        self.primary.setVisible(True)
        self.primary.set_text_key(action.key, **action.params)
        self.primary.set_hint_key(action.hint_key)
        success = action.variant == "success" and action.enabled
        self.primary.set_variant("success_filled" if success else "filled")
        self.primary.setEnabled(action.enabled)
        self.primary.setObjectName(f"primary_{action.name}")
        reason = ""
        if not action.enabled and action.reason_key:
            reason = t(action.reason_key, **action.reason_params)
            # the disabled reason is a small caption INSIDE the primary button (B1)
            self.primary.set_caption(action.reason_key, **action.reason_params)
        else:
            self.primary.set_caption(None)
        self.primary.setToolTip(reason)
        self.primary.setAccessibleDescription(reason)
        self._render_status(vm.status())
        self._set_secondary(vm.secondary())

    def _render_status(self, status: StatusLine | None) -> None:
        if status is None:
            self.status.setText("")
            self.status_icon.setVisible(False)
            self.progress.setVisible(False)
            return
        self.status.setText(render_status(status))
        icon, color, tone = _TONE_ICON.get(status.tone, _TONE_ICON["info"])
        self.status_icon.set_icon(icon, color, filled=status.tone != "pending")
        self.status_icon.setVisible(True)
        self.status.set_tone(tone)
        if status.progress is None:
            self.progress.setVisible(False)
            return
        done, total = status.progress
        self.progress.set_state(
            "success" if done >= total else "info", "status.checks_done", done=done, total=total
        )
        self.progress.setVisible(True)

    def _set_secondary(self, actions: list[Action]) -> None:
        while len(self._secondary_buttons) < len(actions):
            button = AppButton()
            index = len(self._secondary_buttons)
            button.clicked.connect(lambda _c=False, i=index: self._trigger_secondary(i))
            self.secondary_box.addWidget(button)
            self._secondary_buttons.append(button)
        self._secondary_actions = actions
        for index, button in enumerate(self._secondary_buttons):
            if index < len(actions):
                action = actions[index]
                button.set_text_key(action.key, **action.params)
                button.set_hint_key(action.hint_key)
                button.set_variant("danger_tonal" if action.variant == "danger" else "outlined")
                button.setEnabled(action.enabled)
                button.setObjectName(f"secondary_{action.name}")
                button.setVisible(True)
            else:
                button.setVisible(False)

    def _trigger_secondary(self, index: int) -> None:
        if index < len(self._secondary_actions):
            self._secondary_actions[index].trigger()

    def paintEvent(self, _event: QPaintEvent) -> None:
        _paint_bar(self, line_at_top=True)


# The tests and the docs call it the bottom bar.
BottomBar = ActionBar


def _resolve(params: dict[str, object]) -> dict[str, object]:
    resolved = dict(params)
    for name, value in params.items():
        if name.endswith("_key") and isinstance(value, str):
            resolved[name.removesuffix("_key")] = t(value)
    return resolved


# ============================================================================ drawer


class _Scrim(QWidget):
    """Dims the station behind the drawer; a click on it closes the drawer."""

    def __init__(self, controller: StationController, parent: QWidget) -> None:
        super().__init__(parent)
        self.c = controller
        self.setVisible(False)

    def mousePressEvent(self, _event: QMouseEvent) -> None:
        self.c.toggle_drawer(False)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), qcolor(COLORS.scrim, ALPHA.scrim))
        painter.end()


class SessionDrawer(QFrame):
    """Right-side sheet: counters, ambient + re-measure, devices this session, End session."""

    STATUS_ICONS: ClassVar[dict[DeviceStatus, tuple[str, str]]] = {
        DeviceStatus.COMPLETE: ("check_circle", COLORS.success),
        DeviceStatus.REJECTED: ("cancel", COLORS.danger),
        DeviceStatus.ABANDONED: ("do_not_disturb_on", COLORS.text_3),
        DeviceStatus.IN_PROGRESS: ("schedule", COLORS.info),
    }

    def __init__(self, controller: StationController, parent: QWidget) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("Drawer")
        self.setFixedWidth(SIZES.drawer)
        add_shadow(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.xl)
        layout.setSpacing(SPACE.l)
        header = QHBoxLayout()
        header.addWidget(TrText("drawer.title", "headline"), 1)
        self.close_button = AppButton(
            "action.close", variant="outlined", size="compact", hint_key="key.esc"
        )
        self.close_button.clicked.connect(self._close)
        header.addWidget(self.close_button)
        layout.addLayout(header)
        tiles = QGridLayout()
        tiles.setSpacing(SPACE.m)
        self.tile_ok = KpiTile("counter.uploads_ok", "check_circle", COLORS.success, compact=True)
        self.tile_fail = KpiTile("counter.uploads_fail", "cancel", COLORS.danger, compact=True)
        self.tile_done = KpiTile("counter.completed", "task_alt", COLORS.primary, compact=True)
        self.tile_rejected = KpiTile("counter.rejected", "block", COLORS.danger, compact=True)
        tiles_list = (self.tile_ok, self.tile_fail, self.tile_done, self.tile_rejected)
        for index, tile in enumerate(tiles_list):
            tiles.addWidget(tile, index // 2, index % 2)
        layout.addLayout(tiles)
        self.counters = Text("", "caption", "tertiary", wrap=True)
        layout.addWidget(self.counters)
        ambient_row = QHBoxLayout()
        ambient_row.setSpacing(SPACE.s)
        ambient_row.addWidget(Icon("device_thermostat", SIZES.icon_m, COLORS.text_2))
        self.ambient = Text("", "body_lg")
        ambient_row.addWidget(self.ambient, 1)
        layout.addLayout(ambient_row)
        self.remeasure = AppButton(
            "action.remeasure_ambient", variant="outlined", size="compact", hint_key="key.f9"
        )
        self.remeasure.clicked.connect(controller.remeasure_ambient)
        layout.addWidget(self.remeasure, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(Divider())
        layout.addWidget(TrText("drawer.devices", "title"))
        self.devices = QListWidget()
        self.devices.setFont(self.ambient.font())
        self.devices.setAccessibleName(t("drawer.devices"))
        layout.addWidget(self.devices, 1)
        self.end_button = AppButton("action.end_session", variant="danger_tonal", icon="logout")
        self.end_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.end_button.clicked.connect(controller.request_end_session)
        layout.addWidget(self.end_button)
        self.setVisible(False)
        parent.installEventFilter(self)
        language_notifier().changed.connect(self.refresh)

    def _close(self) -> None:
        self.c.toggle_drawer(False)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self.reposition()
        return False

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.width() - self.width(), 0, self.width(), parent.height())

    def refresh(self, *_args: object) -> None:
        c = self.c
        counters = c.counters
        if counters is not None:
            self.tile_ok.set_value(str(counters.upload_success))
            self.tile_fail.set_value(str(counters.net_upload_failure))
            self.tile_done.set_value(str(counters.completed))
            self.tile_rejected.set_value(str(counters.rejected))
            self.counters.set_key("drawer.adjusted_note", n=counters.failures_adjusted)
        self.ambient.setText(
            t("drawer.ambient", value=f"{c.ambient_c:.1f}")
            if c.ambient_c is not None
            else t("drawer.ambient_unknown")
        )
        self.devices.clear()
        for device in c.session_devices:
            icon, color = self.STATUS_ICONS[device.status]
            status = t(device.status.label_key)
            if device.reject_stage is not None:
                status = t("drawer.rejected_at", status=status, box=device.reject_stage.letter)
            label = f"{device.device_id or device.mac_address}  ·  {status}"
            self.devices.addItem(QListWidgetItem(qicon(icon, color), label))
        if not c.session_devices:
            self.devices.addItem(QListWidgetItem(t("drawer.no_devices")))

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(COLORS.surface))
        painter.end()


# ============================================================================ shell


class ProductionShell(QWidget):
    def __init__(self, controller: StationController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("Page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.band = SimulationBand()
        layout.addWidget(self.band)
        self.top = AppBar(controller)
        self.info = ContextBar()
        layout.addWidget(self.top)
        layout.addWidget(self.info)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(SIZES.page_margin, SPACE.l, SIZES.page_margin, SPACE.l)
        self.body.setSpacing(SPACE.l)
        self.banner = ErrorBanner()
        self.banner.retry_requested.connect(controller.retry_error)
        self.body.addWidget(self.banner)
        self.stack = QStackedWidget()
        self.views = {
            Stage.PROGRAMMING: ProgrammingView(controller),
            Stage.TESTING: TestingView(controller),
            Stage.LABELING: LabelingView(controller),
            Stage.PACKAGING: PackagingView(controller),
        }
        for view in self.views.values():
            self.stack.addWidget(view)
        self.body.addWidget(self.stack, 1)
        layout.addLayout(self.body, 1)
        self.bottom = ActionBar(controller)
        layout.addWidget(self.bottom)

        self.scrim = _Scrim(controller, self)
        self.drawer = SessionDrawer(controller, self)
        self.takeover = RejectTakeover(self)
        self.takeover.confirmed.connect(controller.reject_confirmed)
        self.toast = Toast(self)

        controller.stage_changed.connect(self._stage_changed)
        controller.bottom_bar_changed.connect(self.bottom.refresh)
        controller.error_changed.connect(self._error_changed)
        controller.confirm_changed.connect(self.bottom.refresh)
        controller.reject_shown.connect(self.takeover.show_instruction)
        controller.reject_cleared.connect(self.takeover.hide_takeover)
        controller.toast.connect(self._show_toast)
        for signal in (
            controller.device_changed,
            controller.counters_changed,
            controller.session_changed,
            controller.tick,
            controller.page_changed,
        ):
            signal.connect(self._refresh_bars)
        controller.drawer_changed.connect(self._drawer_changed)
        controller.counters_changed.connect(self.drawer.refresh)
        controller.ambient_changed.connect(self.drawer.refresh)
        controller.session_changed.connect(self.drawer.refresh)
        self._install_shortcuts()
        self._stage_changed()

    def _show_toast(self, device: str) -> None:
        self.toast.show_message(device, self.c.settings.ui.success_toast_s)

    # ------------------------------------------------------------------ keys
    def _install_shortcuts(self) -> None:
        def add(sequence: QKeySequence | Qt.Key, handler: Callable[[], object]) -> None:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

        add(QKeySequence(Qt.Key.Key_Return), self.press_enter)
        add(QKeySequence(Qt.Key.Key_Enter), self.press_enter)
        add(QKeySequence(Qt.Key.Key_Escape), self.c.escape)
        for number in range(1, 13):
            key = getattr(Qt.Key, f"Key_F{number}")
            add(QKeySequence(key), self._function_key_handler(number))

    def _function_key_handler(self, number: int) -> Callable[[], None]:
        def handler() -> None:
            self.c.function_key(number)

        return handler

    def press_enter(self) -> None:
        if self.c.reject is not None:
            self.c.reject_confirmed()
            return
        if self.c.confirm is not None:
            self.c.answer(True)
            return
        focus = self.focusWidget()
        if isinstance(focus, QLineEdit) and focus.property("enter_submits"):
            focus.returnPressed.emit()  # the field handles Enter itself (manual ID entry)
            return
        action = self.bottom.primary_action()
        if action is not None:
            action.trigger()

    # ------------------------------------------------------------------ refresh
    def _stage_changed(self) -> None:
        view = self.views.get(self.c.stage)
        if view is not None:
            self.stack.setCurrentWidget(view)
            view.update_view()
        self._refresh_bars()
        self.bottom.refresh()
        if self.c.reject is None and self.bottom.primary.isEnabled():
            self.bottom.primary.setFocus()

    def _refresh_bars(self, *_args: object) -> None:
        if self.c.page is not Page.PRODUCTION and self.c.page is not Page.ADMIN:
            return
        c = self.c
        self.top.refresh()
        self.band.setVisible(c.ctx.using_mocks)
        state = c.device
        if state is None:
            self.info.device.set_device(None, None)
        else:
            self.info.device.set_device(state.device_id or state.qr_id, state.mac_address)
        operator = c.operator
        self.info.set_operator(
            operator.full_name if operator else "", operator.operator_code if operator else ""
        )
        self.info.set_elapsed(format_duration(c.session_elapsed_s()))
        counters = c.counters
        if counters is not None:
            self.info.counters.set_counts(
                counters.upload_success,
                counters.net_upload_failure,
                counters.completed,
                counters.rejected,
            )

    def _error_changed(self) -> None:
        state = self.c.error
        if state is None:
            self.banner.clear()
        else:
            self.banner.show_error(
                state.error, has_retry=state.retry is not None, retry_key=state.retry_key
            )

    def _drawer_changed(self) -> None:
        if self.c.drawer_open:
            self.drawer.refresh()
            self.scrim.setGeometry(self.rect())
            self.scrim.setVisible(True)
            self.scrim.raise_()
            self.drawer.reposition()
            self.drawer.setVisible(True)
            self.drawer.raise_()
            self.drawer.close_button.setFocus()
        else:
            self.drawer.setVisible(False)
            self.scrim.setVisible(False)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        width = self.width()
        margin = page_margin(width)
        for bar in (self.top, self.info, self.bottom):
            layout = bar.layout()
            if layout is not None:
                current = layout.contentsMargins()
                layout.setContentsMargins(margin, current.top(), margin, current.bottom())
        self.body.setContentsMargins(margin, SPACE.l, margin, SPACE.l)
        self.top.set_wide(width >= SIZES.wide_breakpoint)
        self.drawer.reposition()
        self.scrim.setGeometry(self.rect())
        self.takeover.reposition()
