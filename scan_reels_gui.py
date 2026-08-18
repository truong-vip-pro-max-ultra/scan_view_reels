"""
Reels View Scanner — quét view · mô tả · thumbnail của reels từng Facebook Page.

Chạy:  python scan_reels_gui.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime

import requests
from PySide6.QtCore import QObject, QRunnable, Qt, QThread, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fb_reels import REELS_PER_REQUEST, PageResult, Reel, scan_page

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
# Số reel lấy mỗi Page — FB trả tối đa 10 reel/request nên số lớn hơn sẽ được
# phân trang bằng cursor (mỗi 10 reel = thêm 1 request).
DEFAULT_MAX_REELS = 10
MAX_REELS_CAP = 300

# ---------------------------------------------------------------------------
# Palette — nhẹ, không dùng nền tối nặng cho label
# ---------------------------------------------------------------------------
BG = "#0f131c"
PANEL = "#151b28"
CARD = "#1a2130"
CARD_HOVER = "#212a3d"
LINE = "#242f45"
TEXT = "#eef2f9"
SUB = "#8b97ad"
FAINT = "#5b6579"
ACCENT = "#6d8bff"
ACCENT_SOFT = "rgba(109,139,255,0.14)"
GREEN = "#3ad6a6"

STYLE = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', 'Inter', system-ui, sans-serif;
    font-size: 13px;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QPushButton {{
    background: transparent;
    color: {TEXT};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 8px 15px;
    font-weight: 600;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: white; }}
QPushButton:disabled {{ color: {FAINT}; border-color: {LINE}; }}
QPushButton#primary {{ background: {ACCENT}; border: none; color: white; padding: 9px 20px; }}
QPushButton#primary:hover {{ background: #5c7bf7; }}
QPushButton#primary:disabled {{ background: #2b3654; color: {FAINT}; }}

QPlainTextEdit {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 10px;
    selection-background-color: {ACCENT};
}}
QComboBox {{
    background: transparent; border: 1px solid {LINE};
    border-radius: 8px; padding: 6px 10px;
}}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {LINE};
    selection-background-color: {ACCENT}; outline: none;
}}
QProgressBar {{ background: {PANEL}; border: none; border-radius: 3px; height: 6px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QDialog {{ background: {BG}; }}
QLabel {{ background: transparent; }}

/* Stepper luồng */
QFrame#stepper {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 9px; }}
QFrame#stepper QPushButton {{
    background: transparent; border: none; color: {SUB};
    font-size: 17px; font-weight: 700; padding: 0;
}}
QFrame#stepper QPushButton:hover {{ color: white; }}
QFrame#stepper QPushButton:disabled {{ color: {FAINT}; }}

/* Segmented — chọn kiểu sắp xếp */
QFrame#seg {{ background: {BG}; border: 1px solid {LINE}; border-radius: 9px; }}
QFrame#seg QPushButton {{
    background: transparent; border: none; border-radius: 7px;
    color: {SUB}; font-size: 11.5px; font-weight: 600; padding: 0;
}}
QFrame#seg QPushButton:hover {{ color: {TEXT}; }}
QFrame#seg QPushButton:checked {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}
"""


# ===========================================================================
# Workers
# ===========================================================================
class ScanWorker(QThread):
    """Quét nhiều Page song song bằng thread pool."""
    page_done = Signal(object)
    progress = Signal(int, int)
    finished_all = Signal()

    def __init__(self, page_ids, limit=10, workers=8):
        super().__init__()
        self.page_ids = page_ids
        self.limit = limit
        self.workers = workers
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(self.page_ids)
        done = 0
        n = max(1, min(self.workers, total))
        with ThreadPoolExecutor(max_workers=n) as ex:
            futures = {ex.submit(self._scan_one, pid): pid for pid in self.page_ids}
            for fut in as_completed(futures):
                if self._stop:
                    break
                self.page_done.emit(fut.result())
                done += 1
                self.progress.emit(done, total)
        self.finished_all.emit()

    def _scan_one(self, pid):
        if self._stop:
            return PageResult(page_id=pid, ok=False, error="Đã dừng.")
        try:
            # should_stop: bấm Dừng thì thôi phân trang tiếp, giữ phần đã lấy
            return scan_page(pid, limit=self.limit, should_stop=lambda: self._stop)
        except Exception as e:  # noqa: BLE001
            return PageResult(page_id=pid, ok=False, error=f"Lỗi: {e}")


class ImageSignals(QObject):
    done = Signal(str, bytes)


class ImageTask(QRunnable):
    _cache: dict[str, bytes] = {}

    def __init__(self, url, signals):
        super().__init__()
        self.url = url
        self.signals = signals

    def run(self):
        if self.url in ImageTask._cache:
            self._emit(ImageTask._cache[self.url])
            return
        try:
            r = requests.get(self.url, headers={"User-Agent": UA}, timeout=20)
            r.raise_for_status()
            ImageTask._cache[self.url] = r.content
            self._emit(r.content)
        except Exception:  # noqa: BLE001
            self._emit(b"")

    def _emit(self, data):
        try:
            self.signals.done.emit(self.url, data)
        except RuntimeError:
            pass  # card đã bị xoá (đổi Page / đổi bộ lọc) — bỏ qua


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n/1_000:.1f}K".replace(".0K", "K")
    return str(n)


class Stepper(QFrame):
    """Ô chỉnh số dạng pill:  [ −  8  + ]."""
    valueChanged = Signal(int)

    def __init__(self, value=8, lo=1, hi=100, step=1, parent=None):
        super().__init__(parent)
        self.setObjectName("stepper")
        self._v, self.lo, self.hi, self.step = value, lo, hi, step
        self.setFixedHeight(34)
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(0)
        self.minus = QPushButton("–")
        self.plus = QPushButton("+")
        for b in (self.minus, self.plus):
            b.setFixedSize(28, 30)
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoRepeat(True)
            b.setAutoRepeatDelay(320)
            b.setAutoRepeatInterval(45)
        self.lbl = QLabel(str(value))
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setFixedWidth(max(34, 10 + 10 * len(str(hi))))
        self.lbl.setStyleSheet(f"color:{TEXT}; font-size:14px; font-weight:700;")
        h.addWidget(self.minus)
        h.addWidget(self.lbl)
        h.addWidget(self.plus)
        self.minus.clicked.connect(lambda: self._set(self._v - self.step))
        self.plus.clicked.connect(lambda: self._set(self._v + self.step))

    def value(self):
        return self._v

    def configure(self, lo, hi, value):
        """Đổi khoảng + giá trị mà không phát tín hiệu (dùng khi đổi chế độ lọc)."""
        self.lo, self.hi = lo, hi
        self._v = max(lo, min(hi, value))
        self.lbl.setText(str(self._v))
        self.minus.setEnabled(self._v > self.lo)
        self.plus.setEnabled(self._v < self.hi)

    def _set(self, v):
        v = max(self.lo, min(self.hi, v))
        if v != self._v:
            self._v = v
            self.lbl.setText(str(v))
            self.valueChanged.emit(v)
        self.minus.setEnabled(self._v > self.lo)
        self.plus.setEnabled(self._v < self.hi)

    def wheelEvent(self, e):
        self._set(self._v + (self.step if e.angleDelta().y() > 0 else -self.step))

    def setEnabled(self, on):  # noqa: N802
        super().setEnabled(on)


class ElideLabel(QLabel):
    """Label 1 dòng, tự cắt chữ bằng “…” khi hẹp — không đẩy rộng layout."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def setText(self, text):  # noqa: N802
        self._full = text
        self._apply_elide()

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        self._apply_elide()

    def _apply_elide(self):
        w = max(0, self.width() - 2)
        super().setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight, w))


class Segmented(QFrame):
    """Dải nút chọn 1-trong-N dạng pill:  [ Mặc định | View đỉnh | Tổng view ]."""
    changed = Signal(str)

    def __init__(self, options, value=None, parent=None):
        super().__init__(parent)
        self.setObjectName("seg")
        self.setFixedHeight(30)
        self._keys = [k for k, _ in options]
        self._value = value if value in self._keys else self._keys[0]
        self.buttons: dict[str, QPushButton] = {}
        h = QHBoxLayout(self)
        h.setContentsMargins(3, 3, 3, 3)
        h.setSpacing(2)
        for key, label in options:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(key == self._value)
            b.clicked.connect(lambda _=False, k=key: self.set_value(k))
            self.buttons[key] = b
            h.addWidget(b, 1)

    def value(self):
        return self._value

    def set_value(self, key):
        if key not in self._keys:
            return
        changed = key != self._value
        self._value = key
        for k, b in self.buttons.items():
            b.setChecked(k == key)
        if changed:
            self.changed.emit(key)


# ===========================================================================
# Reel card (trong lưới)
# ===========================================================================
class Thumb(QLabel):
    def __init__(self, url, link, pool, w, h, parent=None):
        super().__init__(parent)
        self.link = link
        self.W, self.H = w, h
        self.setFixedSize(w, h)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"background:{PANEL}; border-radius:12px; color:{FAINT}; font-size:20px;")
        if link:
            self.setCursor(Qt.PointingHandCursor)
        if url:
            self._sig = ImageSignals()
            self._sig.done.connect(self._loaded)
            pool.start(ImageTask(url, self._sig))
        else:
            self.setText("—")

    def _loaded(self, _u, data):
        if not data:
            self.setText("×")
            return
        pix = QPixmap()
        if pix.loadFromData(data):
            sc = pix.scaled(self.W, self.H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (sc.width() - self.W) // 2
            y = (sc.height() - self.H) // 2
            rounded = self._round(sc.copy(x, y, self.W, self.H))
            self.setPixmap(rounded)
        else:
            self.setText("×")

    def _round(self, pix):
        from PySide6.QtGui import QPainter, QPainterPath
        from PySide6.QtCore import QRectF
        out = QPixmap(pix.size())
        out.fill(Qt.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, pix.width(), pix.height()), 12, 12)
        p.setClipPath(path)
        p.drawPixmap(0, 0, pix)
        p.end()
        return out

    def mousePressEvent(self, e):
        if self.link and e.button() == Qt.LeftButton:
            QDesktopServices.openUrl(QUrl(self.link))


class ReelCard(QFrame):
    TW, TH = 150, 267

    def __init__(self, rank, reel: Reel, pool, parent=None):
        super().__init__(parent)
        self.setFixedWidth(self.TW)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        lay.addWidget(Thumb(reel.thumbnail, reel.url, pool, self.TW, self.TH))

        v = QLabel(reel.views_text or "—")
        v.setStyleSheet(f"color:{ACCENT}; font-size:16px; font-weight:800;")
        lay.addWidget(v)
        vl = QLabel("lượt xem")
        vl.setStyleSheet(f"color:{FAINT}; font-size:11px;")
        lay.addWidget(vl)

        desc = QLabel(reel.description or "(không có mô tả)")
        desc.setWordWrap(True)
        desc.setFixedWidth(self.TW)
        desc.setStyleSheet(f"color:{TEXT}; font-size:12px;")
        desc.setMaximumHeight(48)
        lay.addWidget(desc)

        meta = []
        if reel.created:
            meta.append(datetime.fromtimestamp(reel.created).strftime("%d/%m/%Y"))
        if reel.duration_s:
            m, s = divmod(int(reel.duration_s), 60)
            meta.append(f"{m}:{s:02d}")
        if meta:
            ml = QLabel("  ·  ".join(meta))
            ml.setStyleSheet(f"color:{FAINT}; font-size:11px;")
            lay.addWidget(ml)
        lay.addStretch()


# ===========================================================================
# Lưới reels tự dàn theo bề rộng
# ===========================================================================
class ReelsGrid(QWidget):
    GAP = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: list[ReelCard] = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setHorizontalSpacing(self.GAP)
        self.grid.setVerticalSpacing(self.GAP + 6)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._cols = 1

    def set_cards(self, cards):
        for c in self.cards:
            c.setParent(None)
            c.deleteLater()
        self.cards = cards
        self._relayout(force=True)

    def _columns(self):
        w = self.width()
        return max(1, (w + self.GAP) // (ReelCard.TW + self.GAP))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self, force=False):
        cols = self._columns()
        if not force and cols == self._cols:
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        for i, card in enumerate(self.cards):
            self.grid.addWidget(card, i // cols, i % cols)


# ===========================================================================
# Item Page trong sidebar
# ===========================================================================
class PageItem(QFrame):
    def __init__(self, res: PageResult, order: int, reels: list[Reel], on_click, parent=None):
        super().__init__(parent)
        self.res = res
        self.order = order
        self.reels: list[Reel] = []
        self.total = 0
        self.peak = 0
        self.on_click = on_click
        self.selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("pitem")
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 11, 12, 11)
        row.setSpacing(8)
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        row.addLayout(lay, 1)

        name = ElideLabel(res.author or f"Page {res.page_id}")
        name.setStyleSheet("font-size:13.5px; font-weight:700;")
        lay.addWidget(name)

        self.sub = ElideLabel("")
        lay.addWidget(self.sub)

        # View của reel cao nhất — tiêu chí sắp xếp mặc định
        pk = QVBoxLayout()
        pk.setContentsMargins(0, 0, 0, 0)
        pk.setSpacing(0)
        self.peak_val = QLabel("")
        self.peak_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.peak_val.setStyleSheet(f"color:{ACCENT}; font-size:14px; font-weight:800;")
        pk.addWidget(self.peak_val)
        pl = QLabel("đỉnh")
        pl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        pl.setStyleSheet(f"color:{FAINT}; font-size:10px;")
        pk.addWidget(pl)
        self.peak_box = QWidget()
        self.peak_box.setFixedWidth(58)
        self.peak_box.setLayout(pk)
        row.addWidget(self.peak_box, 0, Qt.AlignVCenter)

        self.set_reels(reels)
        self._apply()

    def set_reels(self, reels: list[Reel]):
        """Gán tập reel sau khi lọc rồi tính lại view đỉnh / tổng view."""
        self.reels = reels
        self.total = sum(r.views_num for r in reels)
        self.peak = max((r.views_num for r in reels), default=0)
        if self.res.ok:
            self.sub.setText(f"{len(reels)} reels  ·  {human(self.total)} views")
            self.sub.setStyleSheet(f"color:{SUB}; font-size:11.5px;")
        else:
            self.sub.setText("không lấy được")
            self.sub.setStyleSheet("color:#e8896b; font-size:11.5px;")
        self.peak_val.setText(human(self.peak))
        self.peak_box.setVisible(bool(self.res.ok and self.peak))
        self.setToolTip(f"Reel cao nhất: {human(self.peak)} view  ·  Tổng: {human(self.total)} view")

    def _apply(self):
        if self.selected:
            self.setStyleSheet(
                f"#pitem {{ background:{ACCENT_SOFT}; border:none; border-left:3px solid {ACCENT};"
                f" border-radius:9px; }}")
        else:
            self.setStyleSheet(
                f"#pitem {{ background:transparent; border:none; border-left:3px solid transparent;"
                f" border-radius:9px; }} #pitem:hover {{ background:{CARD}; }}")

    def set_selected(self, v):
        self.selected = v
        self._apply()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.on_click(self)


# ===========================================================================
# Dialog nhập ID
# ===========================================================================
class IdInputDialog(QDialog):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Danh sách ID Page")
        self.setMinimumSize(440, 430)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 22)
        lay.setSpacing(12)
        t = QLabel("Danh sách ID Page")
        t.setStyleSheet("font-size:17px; font-weight:800;")
        lay.addWidget(t)
        s = QLabel("Mỗi dòng 1 ID Page (số) hoặc username.\nVí dụ: 100051080350208 hoặc HungVlogOfficial")
        s.setStyleSheet(f"color:{SUB};")
        lay.addWidget(s)
        self.edit = QPlainTextEdit()
        self.edit.setPlainText(text)
        self.edit.setPlaceholderText("100051080350208\nHungVlogOfficial")
        lay.addWidget(self.edit, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Xong")
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText("Huỷ")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def ids(self):
        return [ln.strip() for ln in self.edit.toPlainText().splitlines() if ln.strip()]


# ===========================================================================
# Main Window
# ===========================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reels View Scanner")
        self.resize(1080, 760)
        self.pool = QThreadPool.globalInstance()
        self.page_ids: list[str] = []
        self.threads: int = 8
        self.max_reels: int = DEFAULT_MAX_REELS
        self.sort_mode: str = "peak"
        self.filter_mode: str = "all"     # all | count | days
        self.filter_count: int = 5        # N video gần nhất
        self.filter_days: int = 30        # trong N ngày gần nhất
        self.results: list[PageResult] = []
        self.items: list[PageItem] = []
        self.current: PageItem | None = None
        self.worker: ScanWorker | None = None
        self._load_config()
        self._build()

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
                self.page_ids = cfg.get("page_ids", [])
                self.threads = int(cfg.get("threads", 8))
                self.max_reels = max(REELS_PER_REQUEST, min(
                    MAX_REELS_CAP, int(cfg.get("max_reels", DEFAULT_MAX_REELS))))
                self.sort_mode = cfg.get("sort_mode", "peak")
                self.filter_mode = cfg.get("filter_mode", "all")
                self.filter_count = int(cfg.get("filter_count", 5))
                self.filter_days = int(cfg.get("filter_days", 30))
            except Exception:  # noqa: BLE001
                pass

    def _save_config(self):
        try:
            json.dump({"page_ids": self.page_ids, "threads": self.threads,
                       "max_reels": self.max_reels,
                       "sort_mode": self.sort_mode, "filter_mode": self.filter_mode,
                       "filter_count": self.filter_count, "filter_days": self.filter_days},
                      open(CONFIG_PATH, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        except Exception:  # noqa: BLE001
            pass

    def _on_threads_changed(self, v):
        self.threads = v
        self._save_config()

    def _on_max_reels_changed(self, v):
        self.max_reels = v
        self._save_config()
        self._sync_filter_widgets()   # chế độ "N video gần nhất" theo trần mới
        self.filter_seg.setToolTip(self._filter_tip())

    def _on_sort_changed(self, mode):
        self.sort_mode = mode
        self._save_config()
        self._reorder_sidebar()

    # ---- lọc reel ----
    def _on_filter_mode_changed(self, mode):
        self.filter_mode = mode
        self._sync_filter_widgets()
        self._save_config()
        self._apply_filter()

    def _on_filter_value_changed(self, v):
        if self.filter_mode == "count":
            self.filter_count = v
        elif self.filter_mode == "days":
            self.filter_days = v
        self._save_config()
        self._apply_filter()

    def _sync_filter_widgets(self):
        """Đổi khoảng giá trị + nhãn của ô số theo chế độ lọc đang chọn."""
        show = self.filter_mode != "all"
        self.filter_step.setVisible(show)
        self.filter_unit.setVisible(show)
        if self.filter_mode == "count":
            self.filter_step.configure(1, self.max_reels, self.filter_count)
            self.filter_count = self.filter_step.value()
            self.filter_unit.setText("video gần nhất")
        elif self.filter_mode == "days":
            self.filter_step.configure(1, 365, self.filter_days)
            self.filter_unit.setText("ngày gần nhất")

    def _filtered(self, res: PageResult) -> list[Reel]:
        """Tập reel được tính vào thống kê theo bộ lọc đang bật."""
        if not res.ok:
            return []
        reels = res.reels
        # FB trả sẵn mới → cũ, nhưng vẫn sắp lại cho chắc khi có mốc thời gian
        if all(r.created for r in reels):
            reels = sorted(reels, key=lambda r: r.created, reverse=True)
        if self.filter_mode == "count":
            return reels[: self.filter_count]
        if self.filter_mode == "days":
            if not any(r.created for r in reels):
                return reels  # không có mốc thời gian thì không lọc được
            cutoff = time.time() - self.filter_days * 86400
            return [r for r in reels if r.created and r.created >= cutoff]
        return reels

    def _filter_tip(self) -> str:
        return (f"Tất cả: dùng toàn bộ reel quét được (tối đa {self.max_reels}/Page)\n"
                "Video gần nhất: chỉ N reel mới nhất\n"
                "Theo ngày: chỉ reel đăng trong N ngày trở lại")

    def _filter_note(self) -> str:
        if self.filter_mode == "count":
            return f"{self.filter_count} video gần nhất"
        if self.filter_mode == "days":
            return f"{self.filter_days} ngày gần nhất"
        return ""

    def _apply_filter(self):
        """Tính lại số liệu mọi Page, sắp xếp lại sidebar và vẽ lại phần chi tiết."""
        for it in self.items:
            it.set_reels(self._filtered(it.res))
        self._reorder_sidebar()
        if self.current:
            self._show_detail(self.current)

    # ---- build ----
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 18, 20, 14)
        root.setSpacing(16)

        # header row: title + toolbar cùng hàng
        top = QHBoxLayout()
        top.setSpacing(14)
        tbox = QVBoxLayout()
        tbox.setSpacing(1)
        title = QLabel("Reels View Scanner")
        title.setStyleSheet("font-size:20px; font-weight:800;")
        tbox.addWidget(title)
        sub = QLabel("Thống kê view · mô tả · thumbnail reels theo Page")
        sub.setStyleSheet(f"color:{SUB};")
        tbox.addWidget(sub)
        top.addLayout(tbox)
        top.addStretch()

        self.id_btn = QPushButton("Nhập ID Page")
        self.id_btn.clicked.connect(self.open_ids)
        top.addWidget(self.id_btn)

        lbl_reels = self._muted("Reel/Page")
        lbl_reels.setToolTip("Số reel quét tối đa mỗi Page")
        top.addWidget(lbl_reels)
        self.reels_box = Stepper(self.max_reels, REELS_PER_REQUEST, MAX_REELS_CAP,
                                 step=REELS_PER_REQUEST)
        self.reels_box.setToolTip(
            f"Số reel lấy tối đa mỗi Page. Facebook trả {REELS_PER_REQUEST} reel/request "
            f"nên mỗi {REELS_PER_REQUEST} reel là thêm 1 lượt gọi — đặt cao thì lâu hơn.\n"
            "Page ít reel hơn thì tự dừng khi hết.")
        self.reels_box.valueChanged.connect(self._on_max_reels_changed)
        top.addWidget(self.reels_box)

        lbl_thread = self._muted("Luồng")
        lbl_thread.setToolTip("Số Page quét song song")
        top.addWidget(lbl_thread)
        self.threads_box = Stepper(self.threads, 1, 100)
        self.threads_box.setToolTip("Số Page quét song song. Nhiều luồng = nhanh hơn "
                                    "nhưng dễ bị Facebook chặn nếu quá cao.")
        self.threads_box.valueChanged.connect(self._on_threads_changed)
        top.addWidget(self.threads_box)

        self.export_btn = QPushButton("Xuất CSV")
        self.export_btn.setToolTip("Xuất 2 file: chi tiết từng reel và "
                                   "<tên>_rank.csv — bảng xếp hạng Page (view đỉnh, tổng view…)")
        self.export_btn.clicked.connect(self.export_csv)
        self.export_btn.setEnabled(False)
        top.addWidget(self.export_btn)

        self.scan_btn = QPushButton("Quét")
        self.scan_btn.setObjectName("primary")
        self.scan_btn.clicked.connect(self.start_scan)
        top.addWidget(self.scan_btn)
        root.addLayout(top)

        # hàng lọc — chọn tập reel được tính vào thống kê
        flt = QHBoxLayout()
        flt.setSpacing(9)
        flt.addStretch()
        lbl_filter = self._muted("Lọc")
        lbl_filter.setToolTip("Chọn tập reel được tính vào view đỉnh / tổng view")
        flt.addWidget(lbl_filter)

        self.filter_seg = Segmented(
            [("all", "Tất cả"), ("count", "Video gần nhất"), ("days", "Theo ngày")],
            self.filter_mode)
        self.filter_seg.setFixedWidth(310)
        self.filter_seg.setToolTip(self._filter_tip())
        self.filter_seg.changed.connect(self._on_filter_mode_changed)
        flt.addWidget(self.filter_seg)

        self.filter_step = Stepper(self.filter_days, 1, 365)
        self.filter_step.valueChanged.connect(self._on_filter_value_changed)
        flt.addWidget(self.filter_step)
        self.filter_unit = self._muted("ngày gần nhất")
        self.filter_unit.setFixedWidth(92)   # cố định để không nhảy layout khi đổi chế độ
        flt.addWidget(self.filter_unit)
        root.addLayout(flt)
        self._sync_filter_widgets()

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # body: sidebar | detail
        body = QHBoxLayout()
        body.setSpacing(16)

        # sidebar
        side = QFrame()
        side.setFixedWidth(260)
        side.setStyleSheet(f"background:{PANEL}; border-radius:14px;")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 12, 10, 10)
        sl.setSpacing(8)
        shdr = QLabel("PAGES")
        shdr.setStyleSheet(f"color:{FAINT}; font-size:11px; font-weight:700; letter-spacing:1px; padding-left:6px;")
        sl.addWidget(shdr)

        self.sort_seg = Segmented(
            [("peak", "View đỉnh"), ("total", "Tổng view"), ("input", "Mặc định")],
            self.sort_mode)
        self.sort_seg.setToolTip(
            "View đỉnh: Page có reel nhiều view nhất lên đầu\n"
            "Tổng view: cộng view toàn bộ reel của Page\n"
            "Mặc định: theo thứ tự ID đã nhập")
        self.sort_seg.changed.connect(self._on_sort_changed)
        sl.addWidget(self.sort_seg)
        self.side_scroll = QScrollArea()
        self.side_scroll.setWidgetResizable(True)
        self.side_holder = QWidget()
        self.side_vbox = QVBoxLayout(self.side_holder)
        self.side_vbox.setContentsMargins(0, 0, 0, 0)
        self.side_vbox.setSpacing(4)
        self.side_vbox.addStretch()
        self.side_scroll.setWidget(self.side_holder)
        sl.addWidget(self.side_scroll, 1)
        body.addWidget(side)

        # detail
        detail = QFrame()
        detail.setStyleSheet(f"background:{PANEL}; border-radius:14px;")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(0, 0, 0, 0)
        self.detail_stack = QStackedWidget()
        dl.addWidget(self.detail_stack)

        # trang 1: rỗng — căn giữa hoàn toàn
        self.empty_page = QWidget()
        el = QVBoxLayout(self.empty_page)
        el.setContentsMargins(20, 20, 20, 20)
        el.addStretch()
        self.empty_title = QLabel("Chưa có dữ liệu")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_title.setStyleSheet(f"color:{SUB}; font-size:17px; font-weight:700;")
        el.addWidget(self.empty_title)
        self.empty_hint = QLabel("Nhập ID Page rồi bấm Quét để bắt đầu.")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setStyleSheet(f"color:{FAINT}; font-size:13px; margin-top:6px;")
        el.addWidget(self.empty_hint)
        el.addStretch()
        self.detail_stack.addWidget(self.empty_page)

        # trang 2: nội dung — tiêu đề + lưới reels
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(22, 18, 12, 12)
        cl.setSpacing(12)
        self.detail_title = QLabel("")
        self.detail_title.setStyleSheet("font-size:16px; font-weight:800;")
        cl.addWidget(self.detail_title)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.grid = ReelsGrid()
        self.detail_scroll.setWidget(self.grid)
        cl.addWidget(self.detail_scroll, 1)
        self.detail_stack.addWidget(content)

        body.addWidget(detail, 1)
        root.addLayout(body, 1)

        self.status = QLabel("Nhập danh sách ID Page rồi bấm Quét.")
        self.status.setStyleSheet(f"color:{SUB};")
        root.addWidget(self.status)

        self._update_count()
        self._show_placeholder()

    def _muted(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color:{SUB};")
        return l

    def _update_count(self):
        self.id_btn.setText(f"Nhập ID Page  ({len(self.page_ids)})" if self.page_ids else "Nhập ID Page")

    def _show_placeholder(self, title="Chưa có dữ liệu",
                          hint="Nhập ID Page rồi bấm Quét để bắt đầu.", error=False):
        self.empty_title.setText(title)
        self.empty_hint.setText(hint)
        self.empty_hint.setStyleSheet(
            f"color:{'#e8896b' if error else FAINT}; font-size:13px; margin-top:6px;")
        self.detail_stack.setCurrentWidget(self.empty_page)

    # ---- sidebar ----
    def _clear_sidebar(self):
        for it in self.items:
            it.setParent(None)
            it.deleteLater()
        self.items = []
        self.current = None

    def _add_page_item(self, res: PageResult):
        order = self.page_ids.index(res.page_id) if res.page_id in self.page_ids else len(self.items)
        item = PageItem(res, order, self._filtered(res), self._on_item_click)
        self.items.append(item)
        self.side_vbox.insertWidget(self.side_vbox.count() - 1, item)
        self._reorder_sidebar()
        if self.current is None:
            self._on_item_click(item)

    def _sort_key(self, it: PageItem):
        """Page lỗi luôn xuống cuối; còn lại xếp theo tiêu chí đang chọn."""
        if self.sort_mode == "peak":
            return (0 if it.res.ok else 1, -it.peak, it.order)
        if self.sort_mode == "total":
            return (0 if it.res.ok else 1, -it.total, it.order)
        return (0, 0, it.order)

    def _reorder_sidebar(self):
        for it in self.items:
            self.side_vbox.removeWidget(it)
        for i, it in enumerate(sorted(self.items, key=self._sort_key)):
            self.side_vbox.insertWidget(i, it)

    def _on_item_click(self, item: PageItem):
        if self.current:
            self.current.set_selected(False)
        item.set_selected(True)
        self.current = item
        self._show_detail(item)

    def _show_detail(self, item: PageItem):
        res = item.res
        if not res.ok:
            self._show_placeholder(res.author or f"Page {res.page_id}", res.error, error=True)
            return
        if not item.reels:
            self._show_placeholder(
                res.author or f"Page {res.page_id}",
                f"Không có reel nào trong {self._filter_note()} "
                f"(Page có {len(res.reels)} reel đã quét).")
            return
        self.detail_stack.setCurrentIndex(1)
        note = self._filter_note()
        self.detail_title.setText(
            f"{res.author or res.page_id}    "
            f"<span style='color:{SUB}; font-weight:500; font-size:13px;'>"
            f"{len(item.reels)} reels · {human(item.total)} views · ID {res.page_id}"
            f"{f' · lọc {note}' if note else ''}</span>")
        cards = [ReelCard(i, r, self.pool) for i, r in enumerate(item.reels, 1)]
        self.grid.set_cards(cards)

    # ---- dialogs ----
    def open_ids(self):
        dlg = IdInputDialog("\n".join(self.page_ids), self)
        if dlg.exec() == QDialog.Accepted:
            self.page_ids = dlg.ids()
            self._update_count()
            self._save_config()
            self.status.setText(f"Đã nhập {len(self.page_ids)} ID.")

    # ---- scan ----
    def start_scan(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.scan_btn.setText("Quét")
            return
        if not self.page_ids:
            QMessageBox.information(self, "Thiếu ID", "Hãy bấm “Nhập ID Page” trước.")
            return
        self.results = []
        self._clear_sidebar()
        self._show_placeholder()
        self.progress.setVisible(True)
        self.progress.setRange(0, len(self.page_ids))
        self.progress.setValue(0)
        self.scan_btn.setText("Dừng")
        self.id_btn.setEnabled(False)
        self.threads_box.setEnabled(False)
        self.reels_box.setEnabled(False)
        self.export_btn.setEnabled(False)

        self.worker = ScanWorker(self.page_ids, limit=self.max_reels, workers=self.threads)
        self.worker.page_done.connect(self._on_page)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_all.connect(self._on_finished)
        self.worker.start()

    def _on_page(self, res: PageResult):
        self.results.append(res)
        self._add_page_item(res)

    def _on_progress(self, done, total):
        self.progress.setValue(done)
        self.status.setText(f"Đang quét… {done}/{total} Page")

    def _on_finished(self):
        self.progress.setVisible(False)
        self.scan_btn.setText("Quét")
        self.id_btn.setEnabled(True)
        self.threads_box.setEnabled(True)
        self.reels_box.setEnabled(True)
        ok = sum(1 for r in self.results if r.ok)
        self.export_btn.setEnabled(bool(self.results))
        note = self._filter_note()
        self.status.setText(f"Xong. {ok}/{len(self.results)} Page có dữ liệu."
                            + (f"  Đang lọc: {note}." if note else ""))

    # ---- export ----
    @staticmethod
    def _as_text(v) -> str:
        """Bọc mọi giá trị thành text cho Excel — không ô nào bị ép kiểu (ID dài
        thành 1.23E+14, view thành số, ngày thành date, mô tả thành công thức…)."""
        s = str(v if v is not None else "")
        s = s.replace("\r", " ").replace("\n", " ").strip()   # formula 1 dòng cho an toàn
        return '="{}"'.format(s.replace('"', '""')) if s else ""

    def _write_row(self, w, values):
        w.writerow([self._as_text(v) for v in values])

    def _rank_key(self, it: PageItem):
        """Xếp hạng theo tiêu chí đang chọn; chế độ 'Mặc định' thì xếp theo view đỉnh."""
        by_total = self.sort_mode == "total"
        return (0 if it.res.ok else 1,
                -(it.total if by_total else it.peak),
                -(it.peak if by_total else it.total),
                it.order)

    def export_csv(self):
        if not self.results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu CSV", f"reels_{datetime.now():%Y%m%d_%H%M}.csv", "CSV (*.csv)")
        if not path:
            return
        base, ext = os.path.splitext(path)
        ext = ext or ".csv"
        detail_path, rank_path = base + ext, f"{base}_rank{ext}"

        # file 1 — chi tiết từng reel
        with open(detail_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Page ID", "Author", "Rank", "Views", "Views(num)",
                        "Description", "URL", "Video ID", "Thumbnail"])
            # xuất đúng thứ tự đang hiển thị ở sidebar, chỉ các reel qua bộ lọc
            for it in sorted(self.items, key=self._sort_key):
                res = it.res
                if not res.ok:
                    self._write_row(w, [res.page_id, "", "", "", "", res.error, "", "", ""])
                    continue
                for i, r in enumerate(it.reels, 1):
                    self._write_row(w, [res.page_id, res.author, i,
                                        r.views_text, r.views_num, r.description,
                                        r.url, r.video_id, r.thumbnail])

        # file 2 — bảng xếp hạng Page, mỗi Page 1 dòng
        with open(rank_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Hạng", "Page ID", "Tên Page", "Số reel",
                        "View đỉnh", "View đỉnh (số)", "Tổng view", "Tổng view (số)",
                        "View TB/reel", "Reel mới nhất", "Link reel đỉnh",
                        "Mô tả reel đỉnh", "Trạng thái"])
            for i, it in enumerate(sorted(self.items, key=self._rank_key), 1):
                res = it.res
                if not res.ok:
                    self._write_row(w, ["", res.page_id, res.author, 0,
                                        "", 0, "", 0, 0, "", "", "", res.error])
                    continue
                top = max(it.reels, key=lambda r: r.views_num, default=None)
                newest = max((r.created for r in it.reels), default=0)
                avg = round(it.total / len(it.reels)) if it.reels else 0
                self._write_row(w, [i, res.page_id, res.author, len(it.reels),
                                    human(it.peak), it.peak, human(it.total), it.total, avg,
                                    f"{datetime.fromtimestamp(newest):%Y-%m-%d}" if newest else "",
                                    top.url if top else "", top.description if top else "", "OK"])

        note = self._filter_note()
        rank_by = "tổng view" if self.sort_mode == "total" else "view đỉnh"
        self.status.setText(
            f"Đã xuất{f' ({note})' if note else ''}: "
            f"{os.path.basename(detail_path)} (chi tiết reel) + "
            f"{os.path.basename(rank_path)} (xếp hạng theo {rank_by}) → {os.path.dirname(path)}")


def _resource(name):
    """Đường dẫn tài nguyên (chạy .py hoặc đã đóng gói Nuitka one-file)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    ico = _resource("icon.ico")
    if os.path.exists(ico):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(ico))
    win = MainWindow()
    if os.path.exists(ico):
        from PySide6.QtGui import QIcon
        win.setWindowIcon(QIcon(ico))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
