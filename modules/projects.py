import os
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QComboBox,
    QMessageBox, QFrame, QTextEdit, QDateEdit, QFileDialog,
    QAbstractItemView, QScrollArea,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor


STATUSES = ["Planning", "Active", "On Hold", "Completed", "Cancelled"]

STATUS_COLORS = {
    "Planning":  "#2b6cb0",
    "Active":    "#276749",
    "On Hold":   "#7c3aed",
    "Completed": "#4a5568",
    "Cancelled": "#c53030",
}


# ──────────────────────────────────────────────────────────────────────────────
class OptionalDateEdit(QWidget):
    """A checkbox + QDateEdit for optional date fields."""

    def __init__(self, label="Set date", parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QCheckBox
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._cb = QCheckBox(label)
        self._de = QDateEdit()
        self._de.setCalendarPopup(True)
        self._de.setDisplayFormat("dd/MM/yyyy")
        self._de.setDate(QDate.currentDate())
        self._de.setEnabled(False)

        self._cb.toggled.connect(self._de.setEnabled)
        lay.addWidget(self._cb)
        lay.addWidget(self._de)
        lay.addStretch()

    def get_value(self):
        if self._cb.isChecked():
            return self._de.date().toString("yyyy-MM-dd")
        return None

    def set_value(self, date_val):
        if date_val:
            date_str = str(date_val)[:10]
            qdate = QDate.fromString(date_str, "yyyy-MM-dd")
            if qdate.isValid():
                self._cb.setChecked(True)
                self._de.setDate(qdate)


# ──────────────────────────────────────────────────────────────────────────────
class ProjectDialog(QDialog):
    """Add / Edit project dialog."""

    def __init__(self, db, project_data=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.project_data = project_data
        self.setWindowTitle("Edit Project" if project_data else "Add New Project")
        self.setMinimumWidth(580)
        self.setMinimumHeight(600)
        self.setModal(True)
        self._build_ui()
        if project_data:
            self._populate()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scrollable form area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner_widget = QWidget()
        form_lay = QFormLayout(inner_widget)
        form_lay.setContentsMargins(24, 20, 24, 12)
        form_lay.setSpacing(12)
        form_lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_lay.setHorizontalSpacing(16)

        self.inp_name  = QLineEdit(); self.inp_name.setPlaceholderText("Required")
        self.txt_desc  = QTextEdit(); self.txt_desc.setFixedHeight(72)
        self.txt_reqs  = QTextEdit(); self.txt_reqs.setFixedHeight(90)

        self.de_start    = QDateEdit(); self._configure_de(self.de_start)
        self.de_expected = OptionalDateEdit("Set expected end date")
        self.de_actual   = OptionalDateEdit("Set actual end date")

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(STATUSES)

        # Folder path row
        path_widget = QWidget()
        path_lay = QHBoxLayout(path_widget)
        path_lay.setContentsMargins(0, 0, 0, 0)
        path_lay.setSpacing(6)
        self.inp_folder = QLineEdit()
        self.inp_folder.setPlaceholderText("Optional – click Browse to select")
        btn_browse = QPushButton("Browse…")
        btn_browse.setFixedWidth(80)
        btn_browse.setObjectName("flatButton")
        btn_browse.clicked.connect(self._browse_folder)
        path_lay.addWidget(self.inp_folder)
        path_lay.addWidget(btn_browse)

        self.txt_remarks = QTextEdit(); self.txt_remarks.setFixedHeight(60)

        form_lay.addRow("Project Name *:", self.inp_name)
        form_lay.addRow("Description:",    self.txt_desc)
        form_lay.addRow("Scope / Req.:",   self.txt_reqs)
        form_lay.addRow("Start Date:",     self.de_start)
        form_lay.addRow("Expected End:",   self.de_expected)
        form_lay.addRow("Actual End:",     self.de_actual)
        form_lay.addRow("Status:",         self.cmb_status)
        form_lay.addRow("Folder Path:",    path_widget)
        form_lay.addRow("Remarks:",        self.txt_remarks)

        scroll.setWidget(inner_widget)
        outer.addWidget(scroll)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(24, 8, 24, 16)
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel"); btn_cancel.setObjectName("secondaryButton")
        btn_save   = QPushButton("Save");   btn_save.setObjectName("successButton")
        btn_cancel.clicked.connect(self.reject)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        outer.addLayout(btn_row)

    @staticmethod
    def _configure_de(de: QDateEdit):
        de.setCalendarPopup(True)
        de.setDisplayFormat("dd/MM/yyyy")
        de.setDate(QDate.currentDate())

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if path:
            self.inp_folder.setText(path)

    def _populate(self):
        d = self.project_data
        self.inp_name.setText(d.get("project_name", ""))
        self.txt_desc.setPlainText(d.get("project_description") or "")
        self.txt_reqs.setPlainText(d.get("business_requirements") or "")

        if d.get("start_date"):
            qd = QDate.fromString(str(d["start_date"])[:10], "yyyy-MM-dd")
            if qd.isValid():
                self.de_start.setDate(qd)

        self.de_expected.set_value(d.get("expected_end_date"))
        self.de_actual.set_value(d.get("actual_end_date"))

        idx = STATUSES.index(d["status"]) if d.get("status") in STATUSES else 0
        self.cmb_status.setCurrentIndex(idx)
        self.inp_folder.setText(d.get("folder_path") or "")
        self.txt_remarks.setPlainText(d.get("remarks") or "")

    def _save(self):
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Project Name is required.")
            return
        vals = (
            name,
            self.txt_desc.toPlainText().strip(),
            self.txt_reqs.toPlainText().strip(),
            self.de_start.date().toString("yyyy-MM-dd"),
            self.de_expected.get_value(),
            self.de_actual.get_value(),
            self.cmb_status.currentText(),
            self.inp_folder.text().strip(),
            self.txt_remarks.toPlainText().strip(),
        )
        try:
            if self.project_data:
                self.db.execute(
                    "UPDATE projects SET project_name=%s, project_description=%s, "
                    "business_requirements=%s, start_date=%s, expected_end_date=%s, "
                    "actual_end_date=%s, status=%s, folder_path=%s, remarks=%s "
                    "WHERE project_id=%s",
                    (*vals, self.project_data["project_id"]),
                )
            else:
                self.db.execute(
                    "INSERT INTO projects (project_name, project_description, "
                    "business_requirements, start_date, expected_end_date, "
                    "actual_end_date, status, folder_path, remarks) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    vals,
                )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Save failed:\n{exc}")


# ──────────────────────────────────────────────────────────────────────────────
class ProjectsModule(QWidget):
    """Project Master – full CRUD list view."""

    COLUMNS = ["ID", "Project Name", "Status", "Start Date",
               "Expected End", "Actual End", "Remarks"]
    COL_WIDTHS = [50, 260, 100, 110, 110, 110, 200]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)

        title = QLabel("Project Master")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        line = QFrame(); line.setObjectName("hLine"); line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        # Toolbar
        toolbar = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setObjectName("searchBar")
        self.inp_search.setPlaceholderText("Search by project name…")
        self.inp_search.textChanged.connect(self.load_data)

        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.addItem("All Statuses")
        self.cmb_filter_status.addItems(STATUSES)
        self.cmb_filter_status.currentIndexChanged.connect(self.load_data)

        btn_add        = QPushButton("+ Add Project"); btn_add.setObjectName("successButton")
        btn_edit       = QPushButton("Edit")
        btn_delete     = QPushButton("Delete");        btn_delete.setObjectName("dangerButton")
        btn_open_folder = QPushButton("Open Folder"); btn_open_folder.setObjectName("flatButton")

        btn_add.clicked.connect(self._add)
        btn_edit.clicked.connect(self._edit)
        btn_delete.clicked.connect(self._delete)
        btn_open_folder.clicked.connect(self._open_folder)

        toolbar.addWidget(self.inp_search)
        toolbar.addWidget(self.cmb_filter_status)
        toolbar.addStretch()
        toolbar.addWidget(btn_open_folder)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_delete)
        root.addLayout(toolbar)

        # Table
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

    def load_data(self):
        term   = self.inp_search.text().strip()
        status = self.cmb_filter_status.currentText()

        base_q = (
            "SELECT project_id, project_name, status, start_date, "
            "expected_end_date, actual_end_date, remarks "
            "FROM projects WHERE 1=1"
        )
        params: list = []

        if term:
            base_q += " AND project_name LIKE %s"
            params.append(f"%{term}%")
        if status != "All Statuses":
            base_q += " AND status = %s"
            params.append(status)

        base_q += " ORDER BY project_id DESC"

        try:
            rows = self.db.execute(base_q, params, fetch=True)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc)); return

        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            st = p.get("status", "")
            cells = [
                str(p["project_id"]),
                p["project_name"],
                st,
                str(p["start_date"])[:10]       if p.get("start_date")       else "",
                str(p["expected_end_date"])[:10] if p.get("expected_end_date") else "",
                str(p["actual_end_date"])[:10]   if p.get("actual_end_date")   else "",
                (p.get("remarks") or "")[:80],
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c == 2:
                    item.setForeground(QColor(STATUS_COLORS.get(st, "#2d3748")))
                self.table.setItem(r, c, item)

        self.lbl_count.setText(f"{len(rows)} record(s)")

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _add(self):
        dlg = ProjectDialog(self.db, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def _edit(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Select", "Please select a project to edit.")
            return
        proj = self.db.execute(
            "SELECT * FROM projects WHERE project_id=%s", (pid,), fetch_one=True
        )
        if proj:
            dlg = ProjectDialog(self.db, project_data=proj, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.load_data()

    def _delete(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Select", "Please select a project to delete.")
            return
        name = self.table.item(self.table.currentRow(), 1).text()
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete project '{name}'?\nLinked tasks will have their project unset.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.execute("DELETE FROM projects WHERE project_id=%s", (pid,))
                self.load_data()
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Delete failed:\n{exc}")

    def _open_folder(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Select", "Please select a project first.")
            return
        row = self.db.execute(
            "SELECT folder_path FROM projects WHERE project_id=%s", (pid,), fetch_one=True
        )
        path = (row.get("folder_path") or "").strip() if row else ""
        if not path:
            QMessageBox.information(self, "No Folder", "No folder path set for this project.")
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Not Found", f"Folder does not exist:\n{path}")
            return
        try:
            os.startfile(path)          # Windows Explorer
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
