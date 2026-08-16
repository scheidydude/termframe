"""Non-activating, click-through border overlay for a managed Terminal.

A single frameless translucent window is used rather than four separate
strip windows: since the whole window is WS_EX_TRANSPARENT, clicks pass
through it everywhere regardless of what's painted, so a single window
painting only the border region (leaving the center transparent) is
simpler and just as robust.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from . import win32

MIN_THICKNESS = 2
MAX_THICKNESS = 12


class BorderOverlay(QWidget):
    def __init__(self, color: str = "#3B82F6", thickness: int = 6, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self._color = QColor(color)
        self._thickness = max(MIN_THICKNESS, min(MAX_THICKNESS, thickness))
        self._styles_applied = False

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def set_thickness(self, px: int) -> None:
        self._thickness = max(MIN_THICKNESS, min(MAX_THICKNESS, px))
        self.update()

    def align_to(self, hwnd: int) -> None:
        """Position the overlay as a frame just outside the target window's bounds."""
        rect = win32.get_frame_rect(hwnd)
        t = self._thickness
        outer_w = rect.width + 2 * t
        outer_h = rect.height + 2 * t

        self.resize(outer_w, outer_h)
        # Qt's own geometry calls can be affected by DPI scaling; positioning
        # is re-asserted directly against the physical-pixel rect so the
        # overlay lines up exactly with the terminal frame on every monitor.
        win32.set_window_pos(int(self.winId()), rect.left - t, rect.top - t, outer_w, outer_h, topmost=True)

    def show(self) -> None:  # noqa: A003 - matches QWidget.show
        super().show()
        if not self._styles_applied:
            win32.apply_non_activating_overlay_styles(int(self.winId()))
            self._styles_applied = True

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)

        w, h, t = self.width(), self.height(), self._thickness
        painter.drawRect(0, 0, w, t)  # top
        painter.drawRect(0, h - t, w, t)  # bottom
        painter.drawRect(0, 0, t, h)  # left
        painter.drawRect(w - t, 0, t, h)  # right


class OverlayManager:
    """Owns the single shared BorderOverlay and tracks which HWND it's on.

    Only one window can be OS-foreground at a time, so one overlay that
    moves between managed sessions is sufficient — see the brief's "reusable
    overlay if simpler" note and the "unfocused = no overlay" default.
    """

    def __init__(self, thickness: int = 6) -> None:
        self._overlay = BorderOverlay(thickness=thickness)
        self._current_hwnd: int | None = None

    @property
    def current_hwnd(self) -> int | None:
        return self._current_hwnd

    def highlight(self, hwnd: int, color: str) -> None:
        self._current_hwnd = hwnd
        self._overlay.set_color(color)
        self._overlay.align_to(hwnd)
        self._overlay.show()

    def hide(self) -> None:
        self._current_hwnd = None
        self._overlay.hide()

    def update_bounds(self, hwnd: int) -> None:
        """Re-align after a move/resize, if this hwnd is the highlighted one."""
        if hwnd != self._current_hwnd or not self._overlay.isVisible():
            return
        if win32.is_iconic(hwnd):
            self._overlay.hide()
        else:
            self._overlay.align_to(hwnd)

    def set_thickness(self, px: int) -> None:
        self._overlay.set_thickness(px)
        if self._current_hwnd is not None and self._overlay.isVisible():
            self._overlay.align_to(self._current_hwnd)
