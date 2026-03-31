#!/usr/bin/env python3
"""
Helix Launcher — PyQt6 desktop control panel.

Detects how Helix is managed and presents Start / Stop / Restart
controls with a live-streaming log terminal and a system tray icon.

Modes (auto-detected at startup):
  systemd-user    systemctl --user ... helix   (no sudo needed)
  systemd-system  pkexec systemctl ... helix   (polkit dialog)
  manual          spawns python main.py directly
"""
import html
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QPoint, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QPlainTextEdit, QPushButton, QSizePolicy,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

# ── Paths & constants ──────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
ICON_SVG   = BASE_DIR / "icons" / "helix.svg"
SERVER_URL = "http://localhost:8000"
SERVICE    = "helix"

# Status polls every 10 s — unhurried; logs are streaming (zero polling).
STATUS_INTERVAL_MS = 10_000

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mK]')

# ── Stylesheet ─────────────────────────────────────────────────────────────────

STYLE = """
QWidget {
    background: #0a0a0f;
    color: #e2e2e8;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 12px;
}
QLabel#title-lbl {
    font-size: 18px;
    font-weight: 700;
    color: #44ff77;
    letter-spacing: 2px;
}
QLabel#mode-badge {
    background: #1a1a22;
    border: 1px solid #2a2a36;
    border-radius: 4px;
    color: #6e6e7e;
    font-size: 10px;
    padding: 2px 8px;
}
QLabel#url-lbl {
    color: #4d9cff;
    font-size: 11px;
    text-decoration: underline;
}
QLabel#status-lbl { font-size: 12px; font-weight: 600; }
QPlainTextEdit#log {
    background: #07070b;
    color: #b8b8c8;
    border: 1px solid #1e1e24;
    border-radius: 6px;
    font-family: 'Cascadia Code', 'Fira Code', 'Courier New', monospace;
    font-size: 11px;
    padding: 6px;
    selection-background-color: #1e3a50;
}
QPushButton {
    background: #1a1a22;
    color: #c8c8d0;
    border: 1px solid #2a2a36;
    border-radius: 5px;
    padding: 6px 16px;
    font-size: 11px;
    font-weight: 500;
}
QPushButton:hover   { background: #22222e; border-color: #3a3a4e; }
QPushButton:pressed { background: #14141c; }
QPushButton#btn-start   { background:#0f2a18; color:#44ff77; border-color:#1a3a20; }
QPushButton#btn-start:hover   { background:#143520; }
QPushButton#btn-stop    { background:#2a0f0f; color:#ff5555; border-color:#3a1a1a; }
QPushButton#btn-stop:hover    { background:#351414; }
QPushButton#btn-restart { background:#0f1a2a; color:#4d9cff; border-color:#1a2a3a; }
QPushButton#btn-restart:hover { background:#14243a; }
QScrollBar:vertical {
    background:#111116; width:6px; border-radius:3px;
}
QScrollBar::handle:vertical {
    background:#2a2a36; border-radius:3px; min-height:20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QMenu {
    background:#111116; border:1px solid #1e1e24; color:#e2e2e8;
}
QMenu::item:selected { background:#1e1e2e; }
QMenu::separator { background:#1e1e24; height:1px; margin:3px 8px; }
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)


def dot_pixmap(color: str, size: int = 12) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return pix


def make_icon() -> QIcon:
    """Load SVG icon if available, otherwise draw one with QPainter."""
    if ICON_SVG.exists():
        icon = QIcon(str(ICON_SVG))
        if not icon.isNull():
            return icon
    # Programmatic fallback: crosshair on dark square
    size = 64
    pix  = QPixmap(size, size)
    pix.fill(QColor("#0f1012"))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    green = QColor("#44ff77")
    cx = cy = size // 2
    r, arm, gap = 18, 11, 5
    p.setPen(QPen(green, 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setOpacity(0.2)
    p.drawEllipse(QPoint(cx, cy), r + 8, r + 8)
    p.setOpacity(1.0)
    p.drawEllipse(QPoint(cx, cy), r, r)
    for x1, y1, x2, y2 in [
        (cx,      cy-(r+arm), cx,      cy-(r+gap)),
        (cx,      cy+(r+gap), cx,      cy+(r+arm)),
        (cx-(r+arm), cy,      cx-(r+gap), cy),
        (cx+(r+gap), cy,      cx+(r+arm), cy),
    ]:
        p.drawLine(x1, y1, x2, y2)
    p.setBrush(green)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPoint(cx, cy), 4, 4)
    p.end()
    return QIcon(pix)


# ── Mode detection & systemctl ─────────────────────────────────────────────────

def detect_mode() -> str:
    for args in [
        ['systemctl', '--user', 'is-enabled', SERVICE],
        ['systemctl',           'is-enabled', SERVICE],
    ]:
        if subprocess.run(args, capture_output=True).returncode == 0:
            return 'systemd-user' if '--user' in args else 'systemd-system'
    return 'manual'


def systemd_status(mode: str) -> str:
    args = (['systemctl', '--user', 'is-active', SERVICE]
            if mode == 'systemd-user'
            else ['systemctl', 'is-active', SERVICE])
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout.strip() or 'unknown'


def run_systemctl(mode: str, action: str):
    if mode == 'systemd-user':
        subprocess.Popen(['systemctl', '--user', action, SERVICE])
    else:
        subprocess.Popen(['/usr/bin/pkexec', 'systemctl', action, SERVICE])


def journal_cmd(mode: str) -> list:
    base = ['journalctl', '-u', SERVICE, '-f', '-n', '100', '--no-pager']
    if mode == 'systemd-user':
        base.insert(1, '--user')
    return base


# ── Log streaming thread ───────────────────────────────────────────────────────

class LogThread(QThread):
    """
    Streams stdout of an already-started subprocess line by line.
    Uses a blocking read — zero CPU polling.
    The caller owns the Popen object and passes it in.
    """
    line_ready = pyqtSignal(str)

    def __init__(self, proc: subprocess.Popen, parent=None):
        super().__init__(parent)
        self._proc = proc
        self._stop = False

    def run(self):
        try:
            for raw in self._proc.stdout:
                if self._stop:
                    break
                self.line_ready.emit(strip_ansi(raw.rstrip()))
        except Exception as exc:
            self.line_ready.emit(f"[launcher] log error: {exc}")

    def stop(self):
        self._stop = True
        # We do NOT terminate the proc here — the caller manages it.
        # For journalctl tails we do terminate since we own that proc.

    def stop_and_kill(self):
        """Use this when we own the subprocess (journalctl tail)."""
        self._stop = True
        if self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass


# ── Main window ────────────────────────────────────────────────────────────────

class HelixLauncher(QMainWindow):

    def __init__(self):
        super().__init__()
        self._mode      = detect_mode()
        self._proc      = None            # manual-mode Helix process
        self._tail_proc = None            # journalctl tail process (systemd modes)
        self._log_thread: LogThread | None = None

        self._build_ui()
        self._build_tray()

        # Stagger initial status so the window paints first
        QTimer.singleShot(600, self._refresh_status)

        # Periodic status — 10 s, no more
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(STATUS_INTERVAL_MS)

        # Start log tail
        self._start_log_tail()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("Helix Launcher")
        self.setWindowIcon(make_icon())
        self.setFixedWidth(580)
        self.setMinimumHeight(520)

        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(14, 14, 14, 12)
        vbox.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        self._dot = QLabel()
        self._dot.setPixmap(dot_pixmap("#6e6e7e"))
        self._dot.setFixedSize(14, 14)
        hdr.addWidget(self._dot)

        title = QLabel("HELIX")
        title.setObjectName("title-lbl")
        hdr.addWidget(title)
        hdr.addStretch()

        self._status_lbl = QLabel("—")
        self._status_lbl.setObjectName("status-lbl")
        hdr.addWidget(self._status_lbl)
        hdr.addSpacing(8)

        mode_text = {
            'systemd-user':   'systemd · user',
            'systemd-system': 'systemd · system',
            'manual':         'manual',
        }.get(self._mode, self._mode)
        badge = QLabel(mode_text)
        badge.setObjectName("mode-badge")
        hdr.addWidget(badge)
        vbox.addLayout(hdr)

        # URL bar
        url_row = QHBoxLayout()
        url_lbl = QLabel(SERVER_URL)
        url_lbl.setObjectName("url-lbl")
        url_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        url_lbl.mousePressEvent = lambda _: webbrowser.open(SERVER_URL)
        url_row.addWidget(url_lbl)
        url_row.addStretch()
        open_btn = QPushButton("Open ↗")
        open_btn.setFixedWidth(76)
        open_btn.clicked.connect(lambda: webbrowser.open(SERVER_URL))
        url_row.addWidget(open_btn)
        vbox.addLayout(url_row)

        # Log terminal
        self._log = QPlainTextEdit()
        self._log.setObjectName("log")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vbox.addWidget(self._log, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_start   = QPushButton("▶  Start")
        self._btn_stop    = QPushButton("■  Stop")
        self._btn_restart = QPushButton("↺  Restart")
        btn_clear         = QPushButton("Clear Log")
        self._btn_start.setObjectName("btn-start")
        self._btn_stop.setObjectName("btn-stop")
        self._btn_restart.setObjectName("btn-restart")
        for b in (self._btn_start, self._btn_stop, self._btn_restart, btn_clear):
            b.setFixedHeight(32)
            btn_row.addWidget(b)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_restart.clicked.connect(self._on_restart)
        btn_clear.clicked.connect(self._log.clear)
        vbox.addLayout(btn_row)

        # Footer note
        notes = {
            'systemd-user':   "User-level service — no sudo required.",
            'systemd-system': "Start / Stop / Restart require polkit authentication.",
            'manual':         "Manual mode — Helix runs as a subprocess of this launcher.",
        }
        note = QLabel(notes.get(self._mode, ''))
        note.setStyleSheet("color:#3e3e50; font-size:10px;")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(note)

    def _build_tray(self):
        self._tray = QSystemTrayIcon(make_icon(), self)
        self._tray.setToolTip("Helix")

        menu = QMenu()
        menu.setStyleSheet(STYLE)

        acts = {
            'show':    QAction("Show Window",     self),
            'start':   QAction("▶  Start",        self),
            'stop':    QAction("■  Stop",         self),
            'restart': QAction("↺  Restart",      self),
            'open':    QAction("Open in Browser", self),
            'quit':    QAction("Quit",            self),
        }
        acts['show'].triggered.connect(self._show_win)
        acts['start'].triggered.connect(self._on_start)
        acts['stop'].triggered.connect(self._on_stop)
        acts['restart'].triggered.connect(self._on_restart)
        acts['open'].triggered.connect(lambda: webbrowser.open(SERVER_URL))
        acts['quit'].triggered.connect(self._on_quit)

        menu.addAction(acts['show'])
        menu.addSeparator()
        menu.addActions([acts['start'], acts['stop'], acts['restart']])
        menu.addSeparator()
        menu.addAction(acts['open'])
        menu.addSeparator()
        menu.addAction(acts['quit'])

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_clicked)
        self._tray.show()

    # ── Status ─────────────────────────────────────────────────────────────────

    def _refresh_status(self):
        if self._mode in ('systemd-user', 'systemd-system'):
            status = systemd_status(self._mode)
        else:
            if self._proc and self._proc.poll() is None:
                status = 'active'
            else:
                status = 'inactive'
        self._apply_status(status)

    def _apply_status(self, status: str):
        DOT   = {'active': '#44ff77', 'inactive': '#6e6e7e', 'failed': '#ff5555'}
        LABEL = {'active': '#44ff77', 'inactive': '#8e8e9e', 'failed': '#ff5555'}
        c = DOT.get(status, '#6e6e7e')
        self._dot.setPixmap(dot_pixmap(c, 12))
        self._status_lbl.setText(status.upper())
        self._status_lbl.setStyleSheet(
            f"color:{LABEL.get(status,'#8e8e9e')};font-weight:600;font-size:12px;"
        )
        self._tray.setToolTip(f"Helix — {status.upper()}")

    # ── Actions ────────────────────────────────────────────────────────────────

    def _on_start(self):
        if self._mode in ('systemd-user', 'systemd-system'):
            run_systemctl(self._mode, 'start')
            self._log_line("[launcher] start requested", color=None)
            # Reconnect log tail after service starts
            QTimer.singleShot(2000, self._reconnect_tail)
        else:
            if self._proc and self._proc.poll() is None:
                self._log_line("[launcher] already running", color=None)
                return
            self._proc = subprocess.Popen(
                [sys.executable, str(BASE_DIR / 'main.py')],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(BASE_DIR),
            )
            self._attach_thread(self._proc)
            self._log_line("[launcher] started", color=None)
        QTimer.singleShot(1500, self._refresh_status)

    def _on_stop(self):
        if self._mode in ('systemd-user', 'systemd-system'):
            run_systemctl(self._mode, 'stop')
            self._log_line("[launcher] stop requested", color=None)
        else:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                self._proc = None
                self._kill_thread()
                self._log_line("[launcher] stopped", color=None)
        QTimer.singleShot(1500, self._refresh_status)

    def _on_restart(self):
        if self._mode in ('systemd-user', 'systemd-system'):
            run_systemctl(self._mode, 'restart')
            self._log_line("[launcher] restart requested", color=None)
            QTimer.singleShot(2500, self._reconnect_tail)
        else:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                self._kill_thread()
                self._log_line("[launcher] stopping for restart…", color=None)
                self._wait_and_start()
            else:
                self._proc = None
                self._on_start()
        QTimer.singleShot(2500, self._refresh_status)

    def _wait_and_start(self):
        """Poll until the old process exits, then start a new one."""
        if self._proc and self._proc.poll() is None:
            QTimer.singleShot(500, self._wait_and_start)
            return
        self._proc = None
        self._on_start()

    # ── Log tail ───────────────────────────────────────────────────────────────

    def _start_log_tail(self):
        if self._mode in ('systemd-user', 'systemd-system'):
            cmd = journal_cmd(self._mode)
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            self._tail_proc = proc
            self._attach_thread(proc)
        # Manual mode: no tail until _on_start spawns the process

    def _reconnect_tail(self):
        """Kill old journalctl tail and spawn a fresh one (used after restart)."""
        self._kill_thread()
        if self._tail_proc and self._tail_proc.poll() is None:
            self._tail_proc.terminate()
        self._start_log_tail()

    def _attach_thread(self, proc: subprocess.Popen):
        self._kill_thread()
        t = LogThread(proc, self)
        t.line_ready.connect(self._on_log_line)
        t.start()
        self._log_thread = t

    def _kill_thread(self):
        if self._log_thread and self._log_thread.isRunning():
            self._log_thread.line_ready.disconnect()
            self._log_thread.stop()
            self._log_thread.wait(1500)
        self._log_thread = None

    def _on_log_line(self, line: str):
        esc = html.escape(line)
        if any(k in line for k in ('ERROR', 'CRITICAL', 'Traceback', 'Exception')):
            frag = f'<span style="color:#ff5555">{esc}</span>'
        elif any(k in line for k in ('WARNING', 'WARN')):
            frag = f'<span style="color:#ffcc44">{esc}</span>'
        elif any(k in line for k in ('[MAKCU] Connected', 'Uvicorn running', '[Helix]')):
            frag = f'<span style="color:#44ff77">{esc}</span>'
        else:
            frag = f'<span>{esc}</span>'
        self._log.appendHtml(frag)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _log_line(self, msg: str, color=None):
        if color:
            self._log.appendHtml(f'<span style="color:{color}">{html.escape(msg)}</span>')
        else:
            self._log.appendHtml(f'<span style="color:#4a4a5a">{html.escape(msg)}</span>')
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── Window / tray ──────────────────────────────────────────────────────────

    def _show_win(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.hide() if self.isVisible() else self._show_win()

    def closeEvent(self, event):
        """Hide to tray rather than quitting."""
        event.ignore()
        self.hide()

    def _on_quit(self):
        self._kill_thread()
        if self._tail_proc and self._tail_proc.poll() is None:
            self._tail_proc.terminate()
        self._tray.hide()
        QApplication.quit()


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Helix Launcher")
    app.setWindowIcon(make_icon())
    app.setQuitOnLastWindowClosed(False)   # keep tray alive when window is hidden
    app.setStyleSheet(STYLE)

    win = HelixLauncher()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
