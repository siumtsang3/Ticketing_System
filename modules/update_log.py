from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QFrame,
    QAbstractItemView, QDialog,
)
from PyQt6.QtCore import Qt

from modules.tasks import TaskUpdateDialog


# ──────────────────────────────────────────────────────────────────────────────
class UpdateLogModule(QWidget):
    """Master log of every task update, filterable by task."""

    COLUMNS = ["Update ID", "Date", "Task ID", "Task", "Details"]
    COL_WIDTHS = [90, 110, 70, 240, 460]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.refresh()

    # ── UI ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)

        title = QLabel("Update Log")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        line = QFrame(); line.setObjectName("hLine"); line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        # ── Filter toolbar ────────────────────────────────────────────
        filter_row = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setObjectName("searchBar")
        self.inp_search.setPlaceholderText("Search update details…")
        self.inp_search.textChanged.connect(self.load_data)

        self.cmb_task = QComboBox()
        self.cmb_task.setMinimumWidth(260)
        self.cmb_task.currentIndexChanged.connect(self.load_data)

        filter_row.addWidget(self.inp_search)
        filter_row.addWidget(QLabel("Task:"))
        filter_row.addWidget(self.cmb_task)
        root.addLayout(filter_row)

        # ── Action toolbar ────────────────────────────────────────────
        action_row = QHBoxLayout()
        btn_edit    = QPushButton("Edit")
        btn_delete  = QPushButton("Delete"); btn_delete.setObjectName("dangerButton")
        btn_refresh = QPushButton("Refresh"); btn_refresh.setObjectName("flatButton")
        btn_edit.clicked.connect(self._edit)
        btn_delete.clicked.connect(self._delete)
        btn_refresh.clicked.connect(self.refresh)

        action_row.addStretch()
        action_row.addWidget(btn_refresh)
        action_row.addWidget(btn_edit)
        action_row.addWidget(btn_delete)
        root.addLayout(action_row)

        # ── Table ─────────────────────────────────────────────────────
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._edit)
        for col, w in enumerate(self.COL_WIDTHS):
            self.table.setColumnWidth(col, w)
        root.addWidget(self.table)

        self.lbl_count = QLabel()
        self.lbl_count.setObjectName("footerLabel")
        root.addWidget(self.lbl_count)

    # ── Data ───────────────────────────────────────────────────────────
    def refresh(self):
        """Reload the task filter dropdown, then the data."""
        self._refresh_task_filter()
        self.load_data()

    def _refresh_task_filter(self):
        current = self.cmb_task.currentData()
        self.cmb_task.blockSignals(True)
        self.cmb_task.clear()
        self.cmb_task.addItem("All Tasks", None)
        try:
            for t in self.db.get_tasks_list():
                self.cmb_task.addItem(f"#{t['task_id']}  {t['task_title']}", t["task_id"])
        except Exception:
            pass
        # Restore previous selection if still present
        if current is not None:
            idx = self.cmb_task.findData(current)
            if idx >= 0:
                self.cmb_task.setCurrentIndex(idx)
        self.cmb_task.blockSignals(False)

    def load_data(self):
        term    = self.inp_search.text().strip()
        task_id = self.cmb_task.currentData()

        q = (
            "SELECT u.update_id, u.update_date, u.task_id, t.task_title, "
            "u.update_details "
            "FROM task_updates u "
            "JOIN tasks t ON t.task_id = u.task_id "
            "WHERE 1=1"
        )
        params: list = []
        if task_id is not None:
            q += " AND u.task_id=%s"; params.append(task_id)
        if term:
            q += " AND u.update_details LIKE %s"; params.append(f"%{term}%")
        q += " ORDER BY u.update_date DESC, u.update_id DESC"

        try:
            rows = self.db.execute(q, params, fetch=True)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc)); return

        self.table.setRowCount(len(rows))
        for r, u in enumerate(rows):
            details = (u.get("update_details") or "").replace("\n", " ")
            cells = [
                str(u["update_id"]),
                str(u["update_date"])[:10] if u.get("update_date") else "",
                str(u["task_id"]),
                u.get("task_title") or "",
                details,
            ]
            for c, text in enumerate(cells):
                self.table.setItem(r, c, QTableWidgetItem(text))

        self.lbl_count.setText(f"{len(rows)} update(s)")

    # ── Helpers / actions ──────────────────────────────────────────────
    def _selected_update_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _edit(self):
        uid = self._selected_update_id()
        if not uid:
            QMessageBox.information(self, "Select", "Please select an update to edit.")
            return
        rec = self.db.execute(
            "SELECT u.update_id, u.task_id, u.update_date, u.update_details, "
            "t.task_title "
            "FROM task_updates u JOIN tasks t ON t.task_id = u.task_id "
            "WHERE u.update_id=%s",
            (uid,), fetch_one=True,
        )
        if not rec:
            return
        dlg = TaskUpdateDialog(
            self.db, rec["task_id"], rec["task_title"],
            update_data=rec, parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def _delete(self):
        uid = self._selected_update_id()
        if not uid:
            QMessageBox.information(self, "Select", "Please select an update to delete.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete update #{uid}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.execute("DELETE FROM task_updates WHERE update_id=%s", (uid,))
                self.load_data()
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Delete failed:\n{exc}")
