"""Login, starting, session summary and fatal-error (settings problem) pages."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QUrl
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QGuiApplication,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from parkomate.ui.components.icons import icon_pixmap, paint_icon
from parkomate.ui.theme.fonts import font_for
from parkomate.ui.theme.tokens import ALPHA, RADIUS, TYPE

from parkomate import __version__
from parkomate.core.enums import PRODUCTION_STAGES
from parkomate.core.errors import ErrorCode, ParkomateError, SettingsError
from parkomate.i18n import t, translator
from parkomate.ui.components.base import Divider
from parkomate.ui.components.buttons import AppButton
from parkomate.ui.components.cards import Banner, Card, IconBadge, KpiTile
from parkomate.ui.components.data import StackedBar
from parkomate.ui.components.inputs import FormField, PasswordField, TextField
from parkomate.ui.components.layout import ScrollArea
from parkomate.ui.components.progress import Spinner
from parkomate.ui.components.segmented import LanguageSwitch
from parkomate.ui.components.shellparts import ProductMark, SimulationBand
from parkomate.ui.components.text import SelectableText, Text, TrText
from parkomate.ui.qt_i18n import error_cause, error_steps, error_title, language_notifier
from parkomate.ui.theme.tokens import COLORS, SIZES, SPACE
from parkomate.ui.viewmodels.station import LoginPhase, SendState, StationController

CENTER = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
LOGIN_WIDTH = SIZES.drawer + SIZES.ring // 2  # the login card is always this wide
SUMMARY_WIDTH = SIZES.content_max * 2 // 3


def _centered(widget: QWidget, width: int) -> QWidget:
    """``widget`` centred on a page; scrolls instead of overlapping on small screens."""
    scroll = ScrollArea()
    outer = scroll.layout_
    margin = SIZES.page_margin
    outer.setContentsMargins(margin, margin, margin, margin)
    outer.addStretch(1)
    row = QHBoxLayout()
    row.addStretch(1)
    widget.setFixedWidth(width)
    row.addWidget(widget)
    row.addStretch(1)
    outer.addLayout(row)
    outer.addStretch(1)
    return scroll


def _show_error(banner: Banner, error: ParkomateError) -> None:
    banner.set_texts(error_title(error), error_cause(error), error_steps(error))
    banner.setVisible(True)


class StartingView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Page")
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(ProductMark(SIZES.mark_large), 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(SPACE.l)
        layout.addWidget(TrText("app.brand", "headline", align=CENTER))
        layout.addSpacing(SPACE.s)
        row = QHBoxLayout()
        row.setSpacing(SPACE.s)
        row.addStretch(1)
        row.addWidget(Spinner())
        row.addWidget(TrText("starting.text", "body_lg", "secondary"))
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)


class _ShowcaseCard(QWidget):
    """One of the 4 glassmorphic feature tiles in the showcase panel."""

    def __init__(self, icon_name: str, title_key: str, desc_key: str) -> None:
        super().__init__()
        self.icon_name = icon_name
        self.title_key = title_key
        self.desc_key = desc_key
        self.setFixedHeight(SIZES.action_bar)

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        card_bg1 = QColor(COLORS.hero_card_bg)
        card_bg1.setAlphaF(0.50)
        card_bg2 = QColor(COLORS.hero_card_bg)
        card_bg2.setAlphaF(0.25)
        grad.setColorAt(0.0, card_bg1)
        grad.setColorAt(1.0, card_bg2)
        p.setBrush(QBrush(grad))
        border = QColor(COLORS.hero_card_border)
        border.setAlphaF(0.55)
        p.setPen(QPen(border, SIZES.hairline))
        p.drawRoundedRect(r, RADIUS.control, RADIUS.control)

        icon_box_rect = QRectF(
            r.left() + SPACE.m,
            r.top() + (r.height() - SIZES.chip_hero) / 2,
            SIZES.chip_hero,
            SIZES.chip_hero,
        )
        icon_bg = QColor(COLORS.hero_bg_start)
        icon_bg.setAlphaF(0.65)
        p.setBrush(QBrush(icon_bg))
        p.setPen(QPen(border, SIZES.hairline))
        p.drawRoundedRect(icon_box_rect, RADIUS.chip, RADIUS.chip)

        icon_r = icon_box_rect.adjusted(SPACE.s, SPACE.s, -SPACE.s, -SPACE.s)
        paint_icon(p, self.icon_name, icon_r, COLORS.hero_gold)

        text_left = icon_box_rect.right() + SPACE.m
        text_w = r.right() - text_left - SPACE.m
        title_r = QRectF(text_left, r.top() + SPACE.m, text_w, SIZES.icon)
        p.setFont(font_for(TYPE.body_strong))
        p.setPen(QPen(QColor(COLORS.on_primary)))
        p.drawText(
            title_r,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            t(self.title_key),
        )

        desc_r = QRectF(text_left, title_r.bottom() + SPACE.xs, text_w, SIZES.chip_hero)
        p.setFont(font_for(TYPE.caption))
        desc_col = QColor(COLORS.primary_cont)
        desc_col.setAlphaF(0.90)
        p.setPen(QPen(desc_col))
        p.drawText(
            desc_r,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap,
            t(self.desc_key),
        )
        p.end()


class _ShowcasePanel(QWidget):
    """Left-hand hero showcase panel matching the Parkomate dashboard aesthetic."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xxl, SPACE.xl, SPACE.xxl, SPACE.xl)
        layout.setSpacing(SPACE.l)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(SPACE.m)
        self.logo_icon = QLabel()
        self.logo_icon.setPixmap(
            icon_pixmap("sensors", COLORS.hero_gold, SIZES.icon_hero)
        )
        logo_row.addWidget(self.logo_icon)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        self.brand_title = Text("Parkomate", "title", "on_primary")
        self.brand_tag = TrText("login.footer_tag", "caption", "hero_gold")
        self.brand_tag.setObjectName("BrandTag")
        brand_col.addWidget(self.brand_title)
        brand_col.addWidget(self.brand_tag)
        logo_row.addLayout(brand_col)
        logo_row.addStretch(1)
        layout.addLayout(logo_row)

        layout.addSpacing(SPACE.l)

        self.tag_label = TrText("login.showcase_tag", "mono_label", "hero_gold")
        self.tag_label.setObjectName("ShowcaseTag")
        layout.addWidget(self.tag_label)

        self.title_label = TrText("login.showcase_title", "headline", "on_primary")
        self.title_label.setObjectName("ShowcaseTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.desc_label = TrText("login.showcase_sub", "body_lg", "hero_sub")
        self.desc_label.setObjectName("ShowcaseDesc")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        layout.addSpacing(SPACE.m)

        grid1 = QHBoxLayout()
        grid1.setSpacing(SPACE.m)
        self.card1 = _ShowcaseCard("bolt", "login.card1_title", "login.card1_sub")
        self.card2 = _ShowcaseCard("bar_chart", "login.card2_title", "login.card2_sub")
        grid1.addWidget(self.card1, 1)
        grid1.addWidget(self.card2, 1)
        layout.addLayout(grid1)

        grid2 = QHBoxLayout()
        grid2.setSpacing(SPACE.m)
        self.card3 = _ShowcaseCard(
            "photo_camera", "login.card3_title", "login.card3_sub"
        )
        self.card4 = _ShowcaseCard(
            "description", "login.card4_title", "login.card4_sub"
        )
        grid2.addWidget(self.card3, 1)
        grid2.addWidget(self.card4, 1)
        layout.addLayout(grid2)

        layout.addStretch(1)

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        grad = QLinearGradient(0, 0, r.width(), r.height())
        grad.setColorAt(0.0, QColor(COLORS.hero_bg_start))
        grad.setColorAt(0.45, QColor(COLORS.hero_bg_mid))
        grad.setColorAt(1.0, QColor(COLORS.hero_bg_end))
        p.fillRect(r, grad)

        glow = QRadialGradient(r.width() * 0.9, r.height() * 0.95, r.width() * 0.6)
        glow_color = QColor(COLORS.hero_card_border)
        glow_color.setAlphaF(ALPHA.track)
        glow.setColorAt(0.0, glow_color)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(r, glow)
        p.end()


class LoginView(QWidget):
    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self.setObjectName("Page")
        panel = Card()
        pad = SPACE.xxl  # 32 px inside the login card (N1)
        panel.layout_.setContentsMargins(pad, pad, pad, pad)
        layout = panel.body
        layout.setSpacing(SPACE.l)

        # Header: Pill Badge + "Welcome back" + subtitle + station
        badge_row = QHBoxLayout()
        badge_row.setSpacing(0)
        self.badge_pill = QFrame()
        self.badge_pill.setObjectName("LoginBadge")
        badge_layout = QHBoxLayout(self.badge_pill)
        badge_layout.setContentsMargins(SPACE.m, SPACE.xs, SPACE.m, SPACE.xs)
        badge_layout.setSpacing(0)
        badge_text = TrText("login.badge", "caption", "on_primary_cont")
        badge_text.setObjectName("LoginBadgeText")
        badge_layout.addWidget(badge_text)
        badge_row.addWidget(self.badge_pill)
        badge_row.addStretch(1)
        layout.addLayout(badge_row)

        header = QVBoxLayout()
        header.setSpacing(SPACE.xs)
        self.welcome_back = TrText("login.welcome_back", "headline")
        header.addWidget(self.welcome_back)
        self.welcome_sub = TrText("login.welcome_sub", "body", "secondary")
        header.addWidget(self.welcome_sub)
        self.station = Text("", "caption", "secondary")
        header.addWidget(self.station)
        layout.addLayout(header)

        # the language switch sits in the top-right corner of the page
        self.language = LanguageSwitch()
        self.language.language_selected.connect(controller.set_language)
        self.notice = Banner("warning")
        self.notice.setVisible(False)
        layout.addWidget(self.notice)

        self.form = QWidget()
        form = QVBoxLayout(self.form)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(SPACE.l)
        self.code = TextField("login.operator_id_hint", max_width=None)
        self.code.setMaxLength(32)
        self.code.returnPressed.connect(self._submit)
        form.addWidget(FormField("login.operator_id", self.code))
        self.password = PasswordField("login.password_hint")
        self.password.setMaximumWidth(LOGIN_WIDTH)
        self.password.returnPressed.connect(self._submit)
        self.show_password = self.password.eye  # the eye is inside the field (N1)
        form.addWidget(FormField("login.password", self.password))
        self.error = Banner("error")
        self.error.setVisible(False)
        form.addWidget(self.error)
        self.login_button = AppButton("action.login", variant="filled", hint_key="key.enter")
        self.login_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.login_button.clicked.connect(self._submit)
        form.addWidget(self.login_button)
        layout.addWidget(self.form)

        self.ambient = QWidget()
        ambient = QVBoxLayout(self.ambient)
        ambient.setContentsMargins(0, SPACE.l, 0, SPACE.l)
        ambient.setSpacing(SPACE.m)
        self.ambient_badge = IconBadge("device_thermostat", "info")
        ambient.addWidget(self.ambient_badge, 0, Qt.AlignmentFlag.AlignHCenter)
        self.ambient_text = Text("", "title", align=CENTER, wrap=True)
        ambient.addWidget(self.ambient_text)
        layout.addWidget(self.ambient)

        layout.addWidget(Divider())
        self.footer = Text("", "caption", "tertiary", align=CENTER)
        layout.addWidget(self.footer)

        QWidget.setTabOrder(self.code, self.password)
        QWidget.setTabOrder(self.password, self.show_password)
        QWidget.setTabOrder(self.show_password, self.login_button)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.band = SimulationBand()
        outer.addWidget(self.band)

        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)

        self.showcase = _ShowcasePanel()
        split.addWidget(self.showcase, 11)

        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.xl)
        right_layout.setSpacing(0)
        right_layout.addStretch(1)

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.setSpacing(0)
        center_row.addStretch(1)
        panel.setFixedWidth(LOGIN_WIDTH)
        center_row.addWidget(panel)
        center_row.addStretch(1)

        right_layout.addLayout(center_row)
        right_layout.addStretch(1)
        split.addWidget(right_pane, 9)

        outer.addLayout(split, 1)
        # floats in the top-right corner, so the card keeps the full height
        self.language.setParent(self)
        self.language.raise_()
        controller.login_changed.connect(self.update_view)
        language_notifier().changed.connect(self.update_view)
        self.update_view()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        hint = self.language.sizeHint()
        self.language.setGeometry(
            self.width() - hint.width() - SIZES.page_margin,
            SIZES.sim_band + SPACE.l,
            hint.width(),
            hint.height(),
        )
        self.language.raise_()

    def _submit(self) -> None:
        if self.c.login_phase is LoginPhase.FORM:
            self.c.login(self.code.text(), self.password.text())

    def focus_first(self) -> None:
        (self.password if self.code.text() else self.code).setFocus()

    def update_view(self, *_args: object) -> None:
        c = self.c
        self.language.sync(c.language())
        self.station.setText(t("login.station", station=c.settings.station.station_id))
        self.code.setAccessibleName(t("login.operator_id"))
        self.password.setAccessibleName(t("login.password"))
        self._render_notice()
        phase = c.login_phase
        in_form = phase in (LoginPhase.FORM, LoginPhase.CHECKING)
        self.form.setVisible(in_form)
        self.ambient.setVisible(not in_form)
        checking = phase is LoginPhase.CHECKING
        self.code.setEnabled(not checking)
        self.password.setEnabled(not checking)
        self.login_button.setEnabled(not checking)
        self.login_button.set_loading(checking)
        self.login_button.set_text_key("login.checking" if checking else "action.login")
        error = c.login_error
        if error is None:
            self.error.setVisible(False)
        else:
            _show_error(self.error, error)
            if error.code is not ErrorCode.AUTH_LOCKED:
                self.password.clear()
        if phase is LoginPhase.AMBIENT:
            self.ambient_badge.set_icon("device_thermostat", "info")
            self.ambient_text.setText(t("login.measuring_ambient"))
        elif phase is LoginPhase.AMBIENT_DONE and c.ambient_c is not None:
            self.ambient_badge.set_icon("check_circle", "success")
            self.ambient_text.setText(t("login.ambient_result", value=f"{c.ambient_c:.1f}"))
        footer = t("app.version", version=__version__)
        if c.ctx.using_mocks:
            scenario = str(getattr(c.ctx.hardware, "scenario", ""))
            footer = f"{footer}  ·  {t('sim.chip')}  ·  {scenario}"
        self.footer.setText(footer)
        self.band.setVisible(c.ctx.using_mocks)

    def _render_notice(self) -> None:
        c = self.c
        startup = c.startup
        if c.startup_error is not None:
            self.notice.set_tone("error")
            _show_error(self.notice, c.startup_error)
        elif startup is not None and startup.recovery.abandoned_device_ids:
            self.notice.set_tone("warning")
            self.notice.set_texts(
                t("notice.abandoned_title"),
                t("notice.abandoned_body", n=len(startup.recovery.abandoned_device_ids)),
            )
            self.notice.setVisible(True)
        elif startup is not None and startup.recovery.recovered:
            self.notice.set_tone("info")
            self.notice.set_texts(t("notice.recovered_title"))
            self.notice.setVisible(True)
        else:
            self.notice.setVisible(False)


class SessionEndView(QWidget):
    """Session summary dashboard (M1): KPI tiles, rejects by stage, uploads, report status."""

    TILES = (
        ("end.devices", "memory", COLORS.text_2),
        ("end.complete", "task_alt", COLORS.success),
        ("end.rejected", "block", COLORS.danger),
        ("end.yield", "monitoring", COLORS.primary),
    )
    UPLOADS = ("end.uploads_ok", "end.uploads_fail", "end.failures_adjusted", "end.abandoned")

    def __init__(self, controller: StationController) -> None:
        super().__init__()
        self.c = controller
        self.setObjectName("Page")
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.l)
        layout.addWidget(TrText("end.title", "headline"))
        self.subtitle = Text("", "body", "secondary")
        layout.addWidget(self.subtitle)
        self._values: dict[str, Text] = {}
        tiles = QHBoxLayout()
        tiles.setSpacing(SPACE.l)
        for key, icon, color in self.TILES:
            tile = KpiTile(key, icon, color)
            tiles.addWidget(tile, 1)
            self._values[key] = tile.value
        layout.addLayout(tiles)
        details = QHBoxLayout()
        details.setSpacing(SPACE.l)
        rejects = Card("end.rejected_by_stage", compact=True)
        self.rejects_bar = StackedBar()
        rejects.body.addWidget(self.rejects_bar)
        rejects.body.addStretch(1)
        details.addWidget(rejects, 1)
        uploads = Card("end.uploads_title", compact=True)
        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACE.xl)
        grid.setVerticalSpacing(SPACE.s)
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for row, key in enumerate(self.UPLOADS):
            grid.addWidget(TrText(key, "body", "secondary"), row, 0)
            value = Text("-", "body_lg_strong", align=right)
            grid.addWidget(value, row, 1)
            self._values[key] = value
        uploads.body.addLayout(grid)
        details.addWidget(uploads, 1)
        layout.addLayout(details)
        self.send = Banner("info")
        self.send_text = self.send.title
        self.report_path = Text("", "mono_label", "secondary")
        self.send.text_column.addWidget(self.report_path)
        report_buttons = QHBoxLayout()
        report_buttons.setSpacing(SPACE.s)
        self.open_folder = AppButton(
            "end.open_folder", variant="outlined", size="compact", icon="folder_open"
        )
        self.copy_path = AppButton(
            "end.copy_path", variant="text", size="compact", icon="content_copy"
        )
        self.open_folder.clicked.connect(self._open_folder)
        self.copy_path.clicked.connect(self._copy_path)
        report_buttons.addWidget(self.open_folder)
        report_buttons.addWidget(self.copy_path)
        report_buttons.addStretch(1)
        self.send.text_column.addLayout(report_buttons)
        layout.addWidget(self.send)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.logout = AppButton(
            "action.logout", variant="filled", hint_key="key.enter", icon="logout"
        )
        self.logout.clicked.connect(self._logout)
        footer.addWidget(self.logout)
        layout.addLayout(footer)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_centered(panel, SUMMARY_WIDTH))
        for qt_key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            shortcut = QShortcut(QKeySequence(qt_key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self._logout)
        controller.session_end_changed.connect(self.update_view)
        language_notifier().changed.connect(self.update_view)
        self.update_view()

    def _logout(self) -> None:
        if self.logout.isEnabled():
            self.c.finish_logout()

    def _paths(self) -> list[Path]:
        result = self.c.logout_result
        return [Path(p) for p in result.queued.report_paths] if result and result.queued else []

    def _open_folder(self) -> None:
        paths = self._paths()
        if paths:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths[0].parent)))

    def _copy_path(self) -> None:
        paths = self._paths()
        if paths:
            QGuiApplication.clipboard().setText("\n".join(str(p) for p in paths))
            self.copy_path.set_text_key("end.copied")

    def update_view(self, *_args: object) -> None:
        summary = self.c.summary
        if summary is not None:
            fpy = summary.first_pass_yield
            values = {
                "end.devices": summary.total_devices,
                "end.complete": summary.complete,
                "end.rejected": summary.rejected_total,
                "end.abandoned": summary.abandoned,
                "end.uploads_ok": summary.upload_success,
                "end.uploads_fail": summary.upload_failure,
                "end.failures_adjusted": summary.failures_adjusted,
                "end.yield": t("end.yield_value", value=f"{fpy:.1f}")
                if fpy is not None
                else t("end.yield_none"),
            }
            for key, value in values.items():
                self._values[key].setText(str(value))
            colors = (COLORS.reject_a, COLORS.reject_b, COLORS.reject_c, COLORS.reject_d)
            self.rejects_bar.set_segments(
                [
                    (
                        f"{stage.letter} · {t(stage.label_key)}",
                        summary.rejected_by_stage.get(stage, 0),
                        color,
                    )
                    for stage, color in zip(PRODUCTION_STAGES, colors, strict=True)
                ]
            )
            self.subtitle.setText(
                t(
                    "end.subtitle",
                    operator=summary.operator_name,
                    session=summary.session.id,
                    station=summary.session.station_id,
                )
            )
        state = self.c.send_state
        tones = {
            SendState.CLOSING: ("info", "end.closing"),
            SendState.SENDING: ("info", "end.sending"),
            SendState.SENT: ("success", "end.sent"),
            SendState.SAVED: ("warning", "end.saved_retry"),
            SendState.DISABLED: ("info", "end.saved_local"),
            SendState.REPORT_ERROR: ("error", "end.report_error"),
        }
        tone, text_key = (
            tones.get(state, ("info", "end.closing")) if state else ("info", "end.closing")
        )
        self.send.set_tone(tone)
        self.send.set_texts(t(text_key))
        paths = self._paths()
        self.report_path.setText(
            t("end.report_files", files=", ".join(p.name for p in paths)) if paths else ""
        )
        self.report_path.setToolTip("\n".join(str(p) for p in paths))
        for widget in (self.report_path, self.open_folder, self.copy_path):
            widget.setVisible(bool(paths))
        self.copy_path.set_text_key("end.copy_path")
        self.logout.setEnabled(state not in (None, SendState.CLOSING))


class FatalView(QWidget):
    """Shown instead of the station when it cannot start: invalid settings (human field name
    first, the key small and monospace - E1) or another instance already running."""

    def __init__(self, error: ParkomateError, location: str) -> None:
        super().__init__()
        from parkomate.ui.views.admin import settings_issue_text

        self.setObjectName("Page")
        self.setWindowTitle(t("app.brand"))
        panel = Card()
        layout = panel.body
        banner = Banner("error")
        banner.set_texts(error_title(error), error_cause(error))
        layout.addWidget(banner)
        if isinstance(error, SettingsError):
            issues = QVBoxLayout()
            issues.setSpacing(SPACE.m)
            if error.issues:
                rows = [(issue.key, settings_issue_text(issue)) for issue in error.issues]
            else:
                rows = list(error.problems)
            for key, problem in rows:
                issues.addLayout(self._issue_row(key, problem))
            layout.addLayout(issues)
            layout.addWidget(Divider())
        steps = error_steps(error)
        numbered = "\n".join(f"{n}.  {s}" for n, s in enumerate(steps, start=1))
        layout.addWidget(Text(numbered, "body_lg", wrap=True))
        layout.addWidget(SelectableText(t("fatal.location", path=location), "caption", "secondary"))
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_button = AppButton("action.close_app", variant="filled")
        self.close_button.clicked.connect(self.close)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_centered(panel, SUMMARY_WIDTH))

    @staticmethod
    def _issue_row(key: str, problem: str) -> QVBoxLayout:
        row = QVBoxLayout()
        row.setSpacing(0)
        label_key = f"settings.f.{key}"
        line = QHBoxLayout()
        line.setSpacing(SPACE.s)
        if translator().has(label_key, "en"):
            line.addWidget(Text(t(label_key), "body_lg_strong"))
            line.addWidget(Text(key, "mono_label", "tertiary"))
        else:  # an unknown key has no friendly name: show the key once
            line.addWidget(Text(key, "mono_title"))
        line.addStretch(1)
        row.addLayout(line)
        row.addWidget(Text(problem, "body", "danger", wrap=True))
        return row
