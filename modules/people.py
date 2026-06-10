from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QComboBox,
    QMessageBox, QFrame, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


# ──────────────────────────────────────────────────────────────────────────────
class PersonDialog(QDialog):
    """Add / Edit person dialog."""

    def __init__(self, db, person_data=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.person_data = person_data
        self.setWindowTitle("Edit Person" if person_data else "Add New Person")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._build_ui()
        if person_data:
            self._populate()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        form.setHorizontalSpacing(16)

        self.inp_name  = QLineEdit(); self.inp_name.setPlaceholderText("Required")
        self.inp_dept  = QLineEdit()
        self.inp_title = QLineEdit()
        self.inp_email = QLineEdit()
        self.inp_phone = QLineEdit()
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Active", "Inactive"])

        form.addRow("Full Name *:", self.inp_name)
        form.addRow("Department:",  self.inp_dept)
        form.addRow("Job Title:",   self.inp_title)
        form.addRow("Email:",       self.inp_email)
        form.addRow("Phone:",       self.inp_phone)
        form.addRow("Status:",      self.cmb_status)
        root.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel"); btn_cancel.setObjectName("secondaryButton")
        btn_save   = QPushButton("Save");   btn_save.setObjectName("successButton")
        btn_cancel.clicked.connect(self.reject)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def _populate(self):
        d = self.person_data
        self.inp_name.setText(d.get("full_name", ""))
        self.inp_dept.setText(d.get("department", "") or "")
        self.inp_title.setText(d.get("job_title", "") or "")
        self.inp_email.setText(d.get("email", "") or "")
        self.inp_phone.setText(d.get("phone", "") or "")
        self.cmb_status.setCurrentIndex(0 if d.get("is_active", 1) else 1)

    # ── Save ──────────────────────────────────────────────────────────
    def _save(self):
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Full Name is required.")
            return
        vals = (
            name,
            self.inp_dept.text().strip(),
            self.inp_title.text().strip(),
            self.inp_email.text().strip(),
            self.inp_phone.text().strip(),
            1 if self.cmb_status.currentIndex() == 0 else 0,
        )
        try:
            if self.person_data:
                self.db.execute(
                    "UPDATE people SET full_name=%s, department=%s, job_title=%s, "
                    "email=%s, phone=%s, is_active=%s WHERE person_id=%s",
                    (*vals, self.person_data["person_id"]),
                )
            else:
                self.db.execute(
                    "INSERT INTO people (full_name,department,job_title,email,phone,is_active) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    vals,
                )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Save failed:\n{exc}")


# ──────────────────────────────────────────────────────────────────────────────
class PeopleModule(QWidget):
    """People Master – full CRUD list view."""

    COLUMNS = ["ID", "Full Name", "Department", "Job Title", "Email", "Phone", "Status"]
    COL_WIDTHS = [50, 190, 140, 150, 210, 120, 80]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.load_data()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)

        # Title
        title = QLabel("People Master")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        line = QFrame(); line.setObjectName("hLine"); line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        # Toolbar
        toolbar = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setObjectName("searchBar")
        self.inp_search.setPlaceholderText("Search by name, department, email…")
        self.inp_search.textChanged.connect(self.load_data)

        btn_add    = QPushButton("+ Add Person");  btn_add.setObjectName("successButton")
        btn_edit   = QPushButton("Edit")
        btn_delete = QPushButton("Delete");        btn_delete.setObjectName("dangerButton")

        btn_add.clicked.connect(self._add)
        btn_edit.clicked.connect(self._edit)
        btn_delete.clicked.connect(self._delete)

        toolbar.addWidget(self.inp_search)
        toolbar.addStretch()
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

    # ── Data ──────────────────────────────────────────────────────────
    def load_data(self):
        term = self.inp_search.text().strip()
        try:
            if term:
                rows = self.db.execute(
                    "SELECT * FROM people "
                    "WHERE full_name LIKE %s OR department LIKE %s OR email LIKE %s "
                    "ORDER BY full_name",
                    (f"%{term}%", f"%{term}%", f"%{term}%"),
                    fetch=True,
                )
            else:
                rows = self.db.execute(
                    "SELECT * FROM people ORDER BY full_name", fetch=True
                )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            active = bool(p.get("is_active", 1))
            cells = [
                str(p["person_id"]),
                p["full_name"],
                p.get("department") or "",
                p.get("job_title") or "",
                p.get("email") or "",
                p.get("phone") or "",
                "Active" if active else "Inactive",
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c == 6:
                    item.setForeground(
                        QColor("#276749") if active else QColor("#c53030")
                    )
                self.table.setItem(r, c, item)

        self.lbl_count.setText(f"{len(rows)} record(s)")

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    # ── Actions ───────────────────────────────────────────────────────
    def _add(self):
        dlg = PersonDialog(self.db, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def _edit(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Select", "Please select a person to edit.")
            return
        person = self.db.execute(
            "SELECT * FROM people WHERE person_id=%s", (pid,), fetch_one=True
        )
        if person:
            dlg = PersonDialog(self.db, person_data=person, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.load_data()

    def _delete(self):
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "Select", "Please select a person to delete.")
            return
        name = self.table.item(self.table.currentRow(), 1).text()
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{name}'?\n\nNote: person will be unlinked from any tasks.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.execute("DELETE FROM people WHERE person_id=%s", (pid,))
                self.load_data()
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Delete failed:\n{exc}")
