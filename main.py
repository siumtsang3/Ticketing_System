"""
IT Ticketing System – Entry Point
Run with:  python main.py
"""
import sys
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QStackedWidget, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon

from dotenv import load_dotenv
load_dotenv()

# ── Internal imports ──────────────────────────────────────────────────────────
from database.db_manager import DatabaseManager
from modules.dashboard    import DashboardModule
from modules.people       import PeopleModule
from modules.projects     import ProjectsModule
from modules.tasks        import TasksModule
from modules.update_log   import UpdateLogModule
from modules.export       import ExportModule
from modules.email_parser import EmailParserModule


# ──────────────────────────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("Dashboard",     "dashboard"),
    ("People",        "people"),
    ("Projects",      "projects"),
    ("Tasks",         "tasks"),
    ("Update Log",    "update_log"),
    ("Export",        "export"),
    ("Email Parser",  "email_parser"),
]


class MainWindow(QMainWindow):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.setWindowTitle("IT Ticketing System")
        self.setMinimumSize(1280, 780)
        self._build_ui()
        self._navigate(0)   # Start on Dashboard

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_content(), stretch=1)

    # ── Sidebar ───────────────────────────────────────────────────────
    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # App title block
        title_lbl = QLabel("IT Ticketing")
        title_lbl.setObjectName("sidebarTitle")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        sub_lbl = QLabel("Work Progress Tracker")
        sub_lbl.setObjectName("sidebarSubtitle")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(title_lbl)
        lay.addWidget(sub_lbl)

        # Navigation buttons
        self._nav_buttons: list[QPushButton] = []
        for label, _ in NAV_ITEMS:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setMinimumHeight(44)
            self._nav_buttons.append(btn)
            lay.addWidget(btn)

        # Wire buttons (after list is complete so indices are stable)
        for idx, btn in enumerate(self._nav_buttons):
            btn.clicked.connect(lambda _, i=idx: self._navigate(i))

        lay.addStretch()

        # Version footer
        ver = QLabel("v1.1")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color: #4a5568; font-size: 11px; padding: 8px;")
        lay.addWidget(ver)

        return sidebar

    # ── Content stack ─────────────────────────────────────────────────
    def _build_content(self) -> QStackedWidget:
        self.stack = QStackedWidget()

        self.mod_dashboard    = DashboardModule(self.db)
        self.mod_people       = PeopleModule(self.db)
        self.mod_projects     = ProjectsModule(self.db)
        self.mod_tasks        = TasksModule(self.db)
        self.mod_update_log   = UpdateLogModule(self.db)
        self.mod_export       = ExportModule(self.db)
        self.mod_email_parser = EmailParserModule(self.db)

        for mod in (
            self.mod_dashboard,
            self.mod_people,
            self.mod_projects,
            self.mod_tasks,
            self.mod_update_log,
            self.mod_export,
            self.mod_email_parser,
        ):
            self.stack.addWidget(mod)

        # When Email Parser emits task_confirmed, navigate to Tasks and
        # open the pre-filled dialog.
        self.mod_email_parser.task_confirmed.connect(self._on_email_task_confirmed)

        return self.stack

    # ── Navigation ────────────────────────────────────────────────────
    def _navigate(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

        # Refresh modules that need live data when shown
        if index == 0:
            self.mod_dashboard.refresh()
        elif index == 3:
            self.mod_tasks._refresh_project_filter()
        elif index == 4:
            self.mod_update_log.refresh()

    # ── Email → Task hand-off ─────────────────────────────────────────
    def _on_email_task_confirmed(self, prefill: dict):
        """Navigate to Tasks module and open a pre-filled new-task dialog."""
        self._navigate(3)   # Tasks page
        self.mod_tasks.open_prefilled_task(prefill)


# ──────────────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IT Ticketing System")

    # Load stylesheet
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "styles.qss")
    if os.path.isfile(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # Connect to MySQL and initialise tables
    try:
        db = DatabaseManager()
        db.initialize_tables()
    except ConnectionError as exc:
        err_app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Database Connection Error",
            str(exc) + "\n\nPlease check your .env file and restart the application.",
        )
        sys.exit(1)

    window = MainWindow(db)
    window.show()

    exit_code = app.exec()
    db.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
