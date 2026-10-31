"""Production shell: top bar, error banner, current stage, bottom bar, drawer, overlays."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import (
    QKeyEvent,
    QKeySequence,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from parkomate.core.enums import DeviceStatus, Stage
from parkomate.i18n import t
from parkomate.ui.components.icons import Icon
from parkomate.ui.components.overlays import ErrorBanner, RejectTakeover, SuccessToast
from parkomate.ui.components.widgets import (
    BigButton,
    InlineConfirm,
    LanguageSwitch,
    StageStepper,
    TrLabel,
    set_prop,
)
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme.fonts import font
from parkomate.ui.theme.tokens import COLORS, SIZES
from parkomate.ui.viewmodels.base import Action, StatusLine
from parkomate.ui.viewmodels.station import Page, StationController
from parkomate.ui.views.stages import LabelingView, PackagingView, ProgrammingView, TestingView

TONE_ICON = {
    "pass": ("check", COLORS.pass_fg),
    "fail": ("cross", COLORS.fail_fg),
    "warn": ("warn", COLORS.warn_fg),
    "pending": ("clock", COLORS.text_muted),
    "info": ("info", COLORS.info_fg),
}


class ModeBanner(QFrame):
    """28 px amber band showing simulation mode. Visible only in mock mode."""

    HEIGHT = 28

    def __init__(self, controller: StationController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("ModeBanner")
        self.setFixedHeight(self.HEIGHT)
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.space_l, SIZES.space_s, SIZES.space_l, SIZES.space_s)
        layout.setSpacing(SIZES.space_m)
        self.label = TrLabel("", role="small")
        self.label.set_tracked(True)
        layout.addWidget(self.label, 1, Qt.AlignmentFlag.AlignCenter)
        # Connect to existing signals that trigger when context might change
        controller.page_changed.connect(self.refresh)
        controller.tick.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        if self.c.ctx.using_mocks:
            scenario = getattr(self.c.ctx.hardware, "scenario", "")
            if scenario:
                self.label.set_key("mock.badge", scenario=scenario)
            else:
                self.label.set_key("mock.badge", scenario="")
            self.setVisible(True)
        else:
            self.setVisible(False)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), COLORS.yellow_soft)


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
    text = t(status.key, **params)
    if more:
        text = f"{text} {t('status.and_more', n=more)}"
    return text


class TopBar(QFrame):
    """76 px bar with brand, stepper, language switch, Session, Admin."""

    HEIGHT = 76

    def __init__(self, controller: StationController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("TopBar")
        self.setFixedHeight(self.HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.space_l, 8, SIZES.space_l, 8)
        layout.setSpacing(SIZES.space_m)

        # Brand: Parkomate Station (Station in olive accent via QSS)
        self.brand = TrLabel("app.brand")
        self.brand.setProperty("role", "h1")
        layout.addWidget(self.brand)
        layout.addStretch(1)

        # StageStepper centered
        self.stepper = StageStepper()
        layout.addWidget(self.stepper)
        layout.addStretch(1)

        # Right side: Language switch, Session, Admin
        self.language = LanguageSwitch()
        self.language.language_selected.connect(controller.set_language)
        layout.addWidget(self.language)

        self.session_button = BigButton("action.session", variant="secondary")
        self.session_button.setObjectName("TopButton")
        self.session_button.clicked.connect(lambda: controller.toggle_drawer())
        layout.addWidget(self.session_button)

        self.admin_button = BigButton("action.admin", variant="secondary")
        self.admin_button.setObjectName("TopButton")
        self.admin_button.clicked.connect(controller.open_admin)
        layout.addWidget(self.admin_button)

    def refresh(self) -> None:
        c = self.c
        state = c.device
        rejected = c.reject is not None or (
            state is not None and state.status is DeviceStatus.REJECTED
        )
        stage = c.stage
        if state is not None and state.status is DeviceStatus.COMPLETE:
            stage = Stage.COMPLETE
        self.stepper.set_state(stage, rejected=rejected, active=state is not None)
        self.language.sync(c.language())
        self.admin_button.setVisible(c.is_admin)
        self.admin_button.setEnabled(c.can_open_admin())
        self.admin_button.setToolTip("" if c.can_open_admin() else t("gate.admin_device_busy"))

    def paintEvent(self, event: QPaintEvent) -> None:
        # Top-right radial glow for non-real hardware sessions
        if not self.c.ctx.using_mocks:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            gradient = QLinearGradient(
                QPointF(self.width() - 100, 0),
                QPointF(self.width(), self.height()),
            )
            gradient.setColorAt(0, COLORS.glow)
            gradient.setColorAt(1, COLORS.bg)
            painter.fillRect(self.rect(), gradient)
        super().paintEvent(event)


class InfoStrip(QFrame):
    """40 px compact info strip: device · operator · session time · counters."""

    HEIGHT = 40

    def __init__(self, controller: StationController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("InfoStrip")
        self.setFixedHeight(self.HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIZES.space_l, SIZES.space_xs, SIZES.space_l, SIZES.space_xs)
        layout.setSpacing(SIZES.space_s)

        layout.addWidget(Icon("chip", 24, COLORS.text_muted))
        self.device = TrLabel("", role="muted")
        layout.addWidget(self.device)

        layout.addSpacing(SIZES.space_l)
        layout.addWidget(Icon("user", 24, COLORS.text_muted))
        self.operator = TrLabel("", role="muted")
        layout.addWidget(self.operator)

        layout.addStretch(1)
        self.counters = TrLabel("", role="muted")
        layout.addWidget(self.counters)

        language_notifier().changed.connect(self.refresh)

    def refresh(self, *_args: object) -> None:
        c = self.c
        state = c.device
        if state is None:
            self.device.set_key("info.device_none")
        elif state.device_id or state.qr_id:
            self.device.set_key(
                "info.device_id", id=state.device_id or state.qr_id, mac=state.mac_address
            )
        else:
            self.device.set_key("info.device_mac", mac=state.mac_address)

        operator = c.operator
        self.operator.set_key(
            "info.operator_time",
            name=operator.full_name,
            code=operator.operator_code,
            time=format_duration(c.session_elapsed_s()),
        ) if operator else ""

        counters = c.counters
        if counters is not None:
            self.counters.set_key(
                "info.counters",
                ok=counters.upload_success,
                fail=counters.net_upload_failure,
                done=counters.completed,
                rejected=counters.rejected,
            )
            self.counters.set_tracked(True)


class BottomBar(QFrame):
    """80 px bar: status (left) - secondary (center) - primary 60px (right)."""

    HEIGHT = 80

    def __init__(self, controller: StationController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("BottomBar")
        self.setFixedHeight(self.HEIGHT)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SIZES.space_l, 6, SIZES.space_l, 6)
        outer.setSpacing(4)

        self.confirm = InlineConfirm()
        self.confirm.answered.connect(controller.answer)
        self.confirm.setVisible(False)
        outer.addWidget(self.confirm)

        self.normal = QWidget()
        row = QHBoxLayout(self.normal)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SIZES.space_m)

        self.status_icon = Icon("info", 28, COLORS.info_fg)
        self.status = TrLabel("", role="muted")
        self.status.setFont(font(SIZES.font_base, bold=True))
        row.addWidget(self.status_icon)
        row.addWidget(self.status, 3)

        self.reason = TrLabel("", role="muted")
        self.reason.setWordWrap(True)
        self.reason.setFont(font(SIZES.font_small))
        self.reason.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.reason.setMaximumWidth(360)
        row.addWidget(self.reason, 2)

        self.secondary_box = QHBoxLayout()
        self.secondary_box.setSpacing(SIZES.space_s)
        row.addLayout(self.secondary_box)

        self.primary = BigButton(variant="primary", hint_key="key.enter")
        self.primary.setMinimumWidth(60)
        self.primary.clicked.connect(self._trigger_primary)
        row.addWidget(self.primary)

        outer.addWidget(self.normal)
        self._primary_action: Action | None = None
        self._secondary_buttons: list[BigButton] = []
        language_notifier().changed.connect(self.refresh)

    def primary_action(self) -> Action | None:
        return self._primary_action

    def secondary_buttons(self) -> list[BigButton]:
        return list(self._secondary_buttons)

    def _trigger_primary(self) -> None:
        if self._primary_action is not None:
            self._primary_action.trigger()

    def refresh(self, *_args: object) -> None:
        c = self.c
        confirm = c.confirm
        if confirm is not None:
            self.normal.setVisible(False)
            self.confirm.show_confirm(
                t(confirm.message_key, **_resolve(confirm.params)),
                confirm.yes_key,
                confirm.no_key,
                confirm.danger,
            )
            self.confirm.yes_button.setFocus()
            return
        self.confirm.setVisible(False)
        self.normal.setVisible(True)

        vm = c.current_vm
        if vm is None or c.reject is not None:
            self._primary_action = None
            self.primary.setVisible(False)
            self.status.setText("")
            self.reason.setText("")
            self._set_secondary([])
            return

        action = vm.primary()
        self._primary_action = action
        self.primary.setVisible(True)
        self.primary.set_text_key(action.key, **action.params)
        self.primary.set_hint_key(action.hint_key)
        self.primary.setEnabled(action.enabled)
        reason = ""
        if not action.enabled and action.reason_key:
            reason = t(action.reason_key, **action.reason_params)
        self.reason.setText(reason)
        self.reason.setVisible(bool(reason))
        self.primary.setToolTip(reason)
        self.primary.setAccessibleDescription(reason)

        status = vm.status()
        if status is None:
            self.status.setText("")
            self.status_icon.setVisible(False)
        else:
            self.status.setText(render_status(status))
            icon, color = TONE_ICON.get(status.tone, TONE_ICON["info"])
            self.status_icon.set_icon(icon, color)
            self.status_icon.setVisible(True)
            set_prop(self.status, "status", status.tone)

        self._set_secondary(vm.secondary())

    def _set_secondary(self, actions: list[Action]) -> None:
        while len(self._secondary_buttons) < len(actions):
            button = BigButton()
            index = len(self._secondary_buttons)
            button.clicked.connect(lambda _c=False, i=index: self._trigger_secondary(i))
            self.secondary_box.addWidget(button)
            self._secondary_buttons.append(button)
        self._secondary_actions = actions
        for index, button in enumerate(self._secondary_buttons):
            if index < len(actions):
                action = actions[index]
                button.setObjectName(f"secondary_{action.name}")
                button.set_text_key(action.key, **action.params)
                button.set_hint_key(action.hint_key)
                button.set_variant(action.variant)
                button.setEnabled(action.enabled)
                button.setVisible(True)
            else:
                button.setVisible(False)

    def _trigger_secondary(self, index: int) -> None:
        actions = getattr(self, "_secondary_actions", [])
        if index < len(actions):
            actions[index].trigger()


def _resolve(params: dict[str, object]) -> dict[str, object]:
    resolved = dict(params)
    for name, value in params.items():
        if name.endswith("_key") and isinstance(value, str):
            resolved[name.removesuffix("_key")] = t(value)
    return resolved


class SessionDrawer(QFrame):
    """480 px right-side drawer with scrim (rgba 17,24,40,0.35)."""

    WIDTH = 480

    def __init__(self, controller: StationController, parent: QWidget) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("Drawer")
        self.setFixedWidth(self.WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SIZES.space_l, SIZES.space_l, SIZES.space_l, SIZES.space_l)
        layout.setSpacing(SIZES.space_m)

        header = QHBoxLayout()
        title = TrLabel("drawer.title", role="h1")
        header.addWidget(title, 1)
        self.close_button = BigButton("action.close", variant="secondary", hint_key="key.esc")
        self.close_button.clicked.connect(lambda: controller.toggle_drawer(False))
        header.addWidget(self.close_button)
        layout.addLayout(header)

        self.counters = TrLabel("", role="muted")
        layout.addWidget(self.counters)

        ambient_row = QHBoxLayout()
        ambient_row.addWidget(Icon("thermo", 28, COLORS.text_muted))
        self.ambient = TrLabel("", role="h2")
        ambient_row.addWidget(self.ambient, 1)
        layout.addLayout(ambient_row)

        self.remeasure = BigButton("action.remeasure_ambient", hint_key="key.f9")
        self.remeasure.clicked.connect(controller.remeasure_ambient)
        layout.addWidget(self.remeasure)

        layout.addWidget(TrLabel("drawer.devices", role="h2"))
        self.devices = QListWidget()
        self.devices.setAccessibleName(t("drawer.devices"))
        layout.addWidget(self.devices, 1)

        self.end_button = BigButton("action.end_session", variant="pass")
        self.end_button.clicked.connect(controller.request_end_session)
        layout.addWidget(self.end_button)

        self.setVisible(False)
        parent.installEventFilter(self)
        language_notifier().changed.connect(self.refresh)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self.reposition()
        elif watched is self and event.type() == QEvent.Type.KeyPress:
            ke = self._cast_key_event(event)
            if ke is not None and ke.key() == Qt.Key.Key_Escape:
                self.c.toggle_drawer(False)
                return True
        return False

    def _cast_key_event(self, event: QEvent) -> QKeyEvent | None:
        """Safely cast QEvent to QKeyEvent if KeyPress."""

        if event.type() == QEvent.Type.KeyPress:
            return event  # type: ignore[return-value]
        return None

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.width() - self.width(), 0, self.width(), parent.height())

    def refresh(self, *_args: object) -> None:
        c = self.c
        counters = c.counters
        if counters is not None:
            self.counters.set_key(
                "drawer.counters",
                ok=counters.upload_success,
                fail=counters.net_upload_failure,
                done=counters.completed,
                rejected=counters.rejected,
            )
        self.ambient.set_key(
            "drawer.ambient", value=f"{c.ambient_c:.1f}"
        ) if c.ambient_c is not None else self.ambient.set_key("drawer.ambient_unknown")

        self.devices.clear()
        for device in c.session_devices:
            mark = {
                DeviceStatus.COMPLETE: "✓",
                DeviceStatus.REJECTED: "✕",
                DeviceStatus.ABANDONED: "–",
                DeviceStatus.IN_PROGRESS: "…",
            }[device.status]
            status = t(device.status.label_key)
            if device.reject_stage is not None:
                status = t("drawer.rejected_at", status=status, box=device.reject_stage.letter)
            item = QListWidgetItem(f"{mark}  {device.device_id or device.mac_address}  ·  {status}")
            self.devices.addItem(item)
        if not c.session_devices:
            self.devices.addItem(QListWidgetItem(t("drawer.no_devices")))


class Scrim(QFrame):
    """Semi-transparent backdrop behind drawer."""

    def __init__(self, on_click: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Scrim")
        self._on_click = on_click
        self.setVisible(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._on_click()
        event.accept()


class ProductionShell(QWidget):
    """Main shell with TopBar, InfoStrip, ModeBanner, stage panes, BottomBar, overlays."""

    def __init__(self, controller: StationController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.setObjectName("Page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.top = TopBar(controller)
        self.info = InfoStrip(controller)
        self.mode_banner = ModeBanner(controller)
        layout.addWidget(self.top)
        layout.addWidget(self.info)
        layout.addWidget(self.mode_banner)

        body = QVBoxLayout()
        body.setContentsMargins(SIZES.space_l, SIZES.space_s + 4, SIZES.space_l, SIZES.space_s + 4)
        body.setSpacing(SIZES.space_s)

        self.banner = ErrorBanner()
        self.banner.retry_requested.connect(controller.retry_error)
        body.addWidget(self.banner)

        self.stack = QStackedWidget()
        self.views = {
            Stage.PROGRAMMING: ProgrammingView(controller),
            Stage.TESTING: TestingView(controller),
            Stage.LABELING: LabelingView(controller),
            Stage.PACKAGING: PackagingView(controller),
        }
        for view in self.views.values():
            self.stack.addWidget(view)
        body.addWidget(self.stack, 1)
        layout.addLayout(body, 1)

        self.bottom = BottomBar(controller)
        layout.addWidget(self.bottom)

        self.scrim = Scrim(lambda: controller.toggle_drawer(False), self)
        self.scrim.setAccessibleName(t("drawer.title"))

        self.drawer = SessionDrawer(controller, self)
        self.takeover = RejectTakeover(self)
        self.takeover.confirmed.connect(controller.reject_confirmed)
        self.toast = SuccessToast(self)

        controller.stage_changed.connect(self._stage_changed)
        controller.bottom_bar_changed.connect(self.bottom.refresh)
        controller.error_changed.connect(self._error_changed)
        controller.confirm_changed.connect(self.bottom.refresh)
        controller.reject_shown.connect(self.takeover.show_instruction)
        controller.reject_cleared.connect(self.takeover.hide_takeover)
        controller.toast.connect(
            lambda device: self.toast.show_message(device, controller.settings.ui.success_toast_s)
        )
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
            focus.returnPressed.emit()
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
        self.top.refresh()
        self.info.refresh()
        self.scrim.setAccessibleName(t("drawer.title"))

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
            self.scrim.setGeometry(0, 0, self.width(), self.height())
            self.scrim.setVisible(True)
            self.scrim.raise_()
            self.drawer.refresh()
            self.drawer.reposition()
            self.drawer.setVisible(True)
            self.drawer.raise_()
            self.drawer.close_button.setFocus()
        else:
            self.scrim.setVisible(False)
            self.drawer.setVisible(False)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.scrim.isVisible():
            self.scrim.setGeometry(0, 0, self.width(), self.height())
        self.drawer.reposition()
        self.takeover.reposition()
