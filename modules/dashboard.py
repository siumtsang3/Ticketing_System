import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


# ──────────────────────────────────────────────────────────────────────────────
class StatCard(QFrame):
    """A coloured summary card showing a number + label."""

    def __init__(self, title: str, value: int, hex_color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self._hex_color = hex_color
        self._apply_bg()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(115)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Large numeric value
        self._val_label = QLabel(str(value))
        val_font = QFont("Segoe UI", 32, QFont.Weight.Bold)
        self._val_label.setFont(val_font)
        self._val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val_label.setStyleSheet("color: #ffffff; background: transparent;")

        # Title text
        self._title_label = QLabel(title)
        title_font = QFont("Segoe UI", 12)
        self._title_label.setFont(title_font)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet("color: rgba(255,255,255,0.88); background: transparent;")
        self._title_label.setWordWrap(True)

        layout.addStretch()
        layout.addWidget(self._val_label)
        layout.addWidget(self._title_label)
        layout.addStretch()

    def _apply_bg(self):
        self.setStyleSheet(
            f"QFrame#statCard {{ background-color: {self._hex_color};"
            " border-radius: 10px; }"
        )

    def update_value(self, value: int):
        self._val_label.setText(str(value))


# ──────────────────────────────────────────────────────────────────────────────
class DashboardModule(QWidget):
    """Dashboard page with summary statistics."""

    CARDS = [
        ("Open Tasks",         "status = 'Open'",
         "#e53e3e"),
        ("In Progress",        "status = 'In Progress'",
         "#d97706"),
        ("Pending / On Hold",  "status = 'Pending / On Hold'",
         "#7c3aed"),
        ("Completed Today",    "status = 'Completed' AND DATE(updated_at) = CURDATE()",
         "#38a169"),
        ("Total Tasks",        "1=1",
         "#2b6cb0"),
        ("Critical (Active)",  "priority = 'Critical' AND status NOT IN "
                               "('Completed','Cancelled','Closed')",
         "#c53030"),
    ]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # ── Header ────────────────────────────────────────────────────
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self._date_label = QLabel()
        self._date_label.setStyleSheet("color: #718096; font-size: 13px;")
        layout.addWidget(self._date_label)

        # Horizontal rule
        line = QFrame()
        line.setObjectName("hLine")
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        # ── Stat cards grid ──────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(14)

        self._cards: list[StatCard] = []
        for idx, (title_txt, _, color) in enumerate(self.CARDS):
            card = StatCard(title_txt, 0, color)
            self._cards.append(card)
            grid.addWidget(card, idx // 3, idx % 3)

        layout.addLayout(grid)

        # ── Tip label ─────────────────────────────────────────────────
        tip = QLabel(
            "Use the left sidebar to navigate between People, Projects, Tasks, "
            "Export, and Email Parser."
        )
        tip.setStyleSheet("color: #a0aec0; font-size: 12px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        layout.addStretch()

    # ------------------------------------------------------------------
    def refresh(self):
        today_str = datetime.date.today().strftime("%A, %B %d, %Y")
        self._date_label.setText(f"Today:  {today_str}")

        for card, (_, where_clause, _) in zip(self._cards, self.CARDS):
            try:
                row = self.db.execute(
                    f"SELECT COUNT(*) AS cnt FROM tasks WHERE {where_clause}",
                    fetch_one=True,
                )
                card.update_value(row["cnt"] if row else 0)
            except Exception:
                card.update_value(0)
