from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QComboBox,
    QMessageBox, QFrame, QTextEdit, QDateEdit, QAbstractItemView,
    QScrollArea, QCheckBox, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor


JOB_TYPES  = ["Bug Fix", "New Development", "Meeting / Discussion",
               "Documentation", "Support / Maintenance"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES   = ["Open", "In Progress", "Pending / On Hold",
               "Completed", "Cancelled", "Closed"]

PRIORITY_COLORS = {
    "Low":      "#718096",
    "Medium":   "#2b6cb0",
    "High":     "#d97706",
    "Critical": "#c53030",
}
STATUS_COLORS = {
    "Open":             "#2b6cb0",
    "In Progress":      "#d97706",
    "Pending / On Hold":"#7c3aed",
    "Completed":        "#276749",
    "Cancelled":        "#c53030",
    "Closed":           "#4a5568",
}


# ──────────────────────────────────────────────────────────────────────────────
class OptionalDateEdit(QWidget):
    """Checkbox + QDateEdit for optional date fields."""

    def __init__(self, label="Set", parent=None):
        super().__init__(parent)
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
        return self._de.date().toString("yyyy-MM-dd") if self._cb.isChecked() else None

    def set_value(self, date_val):
        if date_val:
            qd = QDate.fromString(str(date_val)[:10], "yyyy-MM-dd")
            if qd.isValid():
                self._cb.setChecked(True)
                self._de.setDate(qd)


# ──────────────────────────────────────────────────────────────────────────────
class FollowersSelect(QWidget):
    """Multi-select checklist of people who handle / follow a task."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.setFixedHeight(120)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        lay.addWidget(self._list)
        self._load_people()

    def _load_people(self):
        self._list.clear()
        try:
            for p in self.db.get_people_list():
                item = QListWidgetItem(p["full_name"])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, p["person_id"])
                self._list.addItem(item)
        except Exception:
            pass
        if self._list.count() == 0:
            placeholder = QListWidgetItem("(No people — add them in People first)")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(placeholder)

    def get_selected_ids(self) -> list:
        ids = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def set_selected_ids(self, ids):
        wanted = set(ids or [])
        for i in range(self._list.count()):
            item = self._list.item(i)
            pid = item.data(Qt.ItemDataRole.UserRole)
            if pid is None:
                continue
            item.setCheckState(
                Qt.CheckState.Checked if pid in wanted else Qt.CheckState.Unchecked
            )


# ──────────────────────────────────────────────────────────────────────────────
class TaskDialog(QDialog):
    """Add / Edit task dialog.  Can be pre-filled for the email parser."""

    def __init__(self, db, task_data=None, prefill=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.task_data = task_data
        self.prefill   = prefill or {}
        self.setWindowTitle("Edit Task" if task_data else "Add New Task")
        self.setMinimumWidth(640)
        self.setMinimumHeight(680)
        self.setModal(True)
        self._people_map: dict[str, int] = {}   # name → id
        self._project_map: dict[str, int] = {}  # name → id
        self._build_ui()
        if task_data:
            self._populate(task_data)
        elif prefill:
            self._apply_prefill()

    # ── UI build ──────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        lay  = QVBoxLayout(body)
        lay.setContentsMargins(24, 20, 24, 12)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(16)

        # ── Basic fields ──────────────────────────────────────────────
        self.inp_title = QLineEdit(); self.inp_title.setPlaceholderText("Required")
        self.txt_desc  = QTextEdit(); self.txt_desc.setFixedHeight(80)

        self.cmb_job_type = QComboBox(); self.cmb_job_type.addItems(JOB_TYPES)
        self.cmb_priority = QComboBox(); self.cmb_priority.addItems(PRIORITIES)
        self.cmb_status   = QComboBox(); self.cmb_status.addItems(STATUSES)

        # People: single "requested by" + multi-select "followers"
        self.cmb_req_by    = QComboBox()
        self._load_people_into(self.cmb_req_by)
        self.sel_followers = FollowersSelect(self.db)

        # Dates
        self.de_requested = QDateEdit()
        self.de_requested.setCalendarPopup(True)
        self.de_requested.setDisplayFormat("dd/MM/yyyy")
        self.de_requested.setDate(QDate.currentDate())

        self.ode_due = OptionalDateEdit("Set due date")

        # Linked project
        self.cmb_project = QComboBox()
        self._load_projects_into(self.cmb_project)

        form.addRow("Task Title *:",    self.inp_title)
        form.addRow("Description:",     self.txt_desc)
        form.addRow("Job Type:",        self.cmb_job_type)
        form.addRow("Priority:",        self.cmb_priority)
        form.addRow("Status:",          self.cmb_status)
        form.addRow("Requested By:",    self.cmb_req_by)
        form.addRow("Followers:",       self.sel_followers)
        form.addRow("Requested Date:",  self.de_requested)
        form.addRow("Due Date:",        self.ode_due)
        form.addRow("Linked Project:",  self.cmb_project)

        lay.addLayout(form)

        # Progress & Remarks
        lay.addWidget(QLabel("Current Progress:"))
        self.txt_progress = QTextEdit(); self.txt_progress.setFixedHeight(80)
        lay.addWidget(self.txt_progress)

        lay.addWidget(QLabel("Remarks:"))
        self.txt_remarks = QTextEdit(); self.txt_remarks.setFixedHeight(60)
        lay.addWidget(self.txt_remarks)

        scroll.setWidget(body)
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

    # ── Helpers ───────────────────────────────────────────────────────
    def _load_people_into(self, combo: QComboBox):
        combo.clear()
        combo.addItem("(None)", None)
        try:
            people = self.db.get_people_list()
            for p in people:
                combo.addItem(p["full_name"], p["person_id"])
                self._people_map[p["full_name"].lower()] = p["person_id"]
        except Exception:
            pass

    def _load_projects_into(self, combo: QComboBox):
        combo.clear()
        combo.addItem("(None)", None)
        try:
            projects = self.db.get_projects_list()
            for p in projects:
                combo.addItem(p["project_name"], p["project_id"])
                self._project_map[p["project_name"].lower()] = p["project_id"]
        except Exception:
            pass

    @staticmethod
    def _set_combo_by_text(combo: QComboBox, text: str):
        idx = combo.findText(text, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _set_combo_by_data(combo: QComboBox, data):
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return

    # ── Populate (edit mode) ──────────────────────────────────────────
    def _populate(self, d: dict):
        self.inp_title.setText(d.get("task_title", ""))
        self.txt_desc.setPlainText(d.get("task_description") or "")
        self._set_combo_by_text(self.cmb_job_type, d.get("job_type") or "")
        self._set_combo_by_text(self.cmb_priority, d.get("priority") or "Medium")
        self._set_combo_by_text(self.cmb_status,   d.get("status")   or "Open")
        self._set_combo_by_data(self.cmb_req_by,    d.get("requested_by"))
        self._set_combo_by_data(self.cmb_project,   d.get("linked_project"))
        if d.get("task_id") is not None:
            self.sel_followers.set_selected_ids(
                self.db.get_task_follower_ids(d["task_id"])
            )

        if d.get("requested_date"):
            qd = QDate.fromString(str(d["requested_date"])[:10], "yyyy-MM-dd")
            if qd.isValid():
                self.de_requested.setDate(qd)

        self.ode_due.set_value(d.get("due_date"))
        self.txt_progress.setPlainText(d.get("current_progress") or "")
        self.txt_remarks.setPlainText(d.get("remarks") or "")

    # ── Pre-fill (email-parser mode) ───────────────────────────────────
    def _apply_prefill(self):
        pf = self.prefill
        if pf.get("task_title"):
            self.inp_title.setText(pf["task_title"])
        if pf.get("task_description"):
            self.txt_desc.setPlainText(pf["task_description"])
        if pf.get("job_type"):
            self._set_combo_by_text(self.cmb_job_type, pf["job_type"])
        if pf.get("priority"):
            self._set_combo_by_text(self.cmb_priority, pf["priority"])
        if pf.get("requested_date"):
            qd = QDate.fromString(pf["requested_date"][:10], "yyyy-MM-dd")
            if qd.isValid():
                self.de_requested.setDate(qd)
        # Try to match person name
        if pf.get("requested_by_name"):
            name_lower = pf["requested_by_name"].lower()
            # exact match first
            found_id = self._people_map.get(name_lower)
            if not found_id:
                # partial match
                for k, v in self._people_map.items():
                    if name_lower in k or k in name_lower:
                        found_id = v
                        break
            if found_id:
                self._set_combo_by_data(self.cmb_req_by, found_id)

    # ── Save ──────────────────────────────────────────────────────────
    def _save(self):
        title = self.inp_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Task Title is required.")
            return

        follower_ids = self.sel_followers.get_selected_ids()
        # Keep the legacy single-person column in sync with the first follower
        primary_follower = follower_ids[0] if follower_ids else None

        vals = (
            title,
            self.txt_desc.toPlainText().strip(),
            self.cmb_job_type.currentText(),
            self.cmb_priority.currentText(),
            self.cmb_status.currentText(),
            self.cmb_req_by.currentData(),
            primary_follower,
            self.de_requested.date().toString("yyyy-MM-dd"),
            self.ode_due.get_value(),
            self.cmb_project.currentData(),
            self.txt_progress.toPlainText().strip(),
            self.txt_remarks.toPlainText().strip(),
        )
        try:
            if self.task_data:
                task_id = self.task_data["task_id"]
                self.db.execute(
                    "UPDATE tasks SET task_title=%s, task_description=%s, "
                    "job_type=%s, priority=%s, status=%s, requested_by=%s, "
                    "follow_up_by=%s, requested_date=%s, due_date=%s, "
                    "linked_project=%s, current_progress=%s, remarks=%s "
                    "WHERE task_id=%s",
                    (*vals, task_id),
                )
            else:
                task_id = self.db.execute(
                    "INSERT INTO tasks (task_title, task_description, job_type, "
                    "priority, status, requested_by, follow_up_by, requested_date, "
                    "due_date, linked_project, current_progress, remarks) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    vals,
                )
            self.db.set_task_followers(task_id, follower_ids)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Save failed:\n{exc}")


# ──────────────────────────────────────────────────────────────────────────────
class TaskUpdateDialog(QDialog):
    """Add or edit a dated progress update linked to a task."""

    def __init__(self, db, task_id, task_title, update_data=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.task_id = task_id
        self.update_data = update_data
        self.setWindowTitle("Edit Task Update" if update_data else "Add Task Update")
        self.setMinimumWidth(520)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)

        lbl_task = QLabel(f"Task #{task_id}:  {task_title}")
        lbl_task.setWordWrap(True)
        lbl_task.setStyleSheet("font-weight: bold; font-size: 14px; color: #2d3748;")
        lay.addWidget(lbl_task)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.de_date = QDateEdit()
        self.de_date.setCalendarPopup(True)
        self.de_date.setDisplayFormat("dd/MM/yyyy")
        self.de_date.setDate(QDate.currentDate())
        form.addRow("Update Date:", self.de_date)
        lay.addLayout(form)

        lay.addWidget(QLabel("Update Details:"))
        self.txt_details = QTextEdit()
        self.txt_details.setMinimumHeight(140)
        self.txt_details.setPlaceholderText("What happened / what was done…")
        lay.addWidget(self.txt_details)

        # Pre-fill in edit mode
        if update_data:
            if update_data.get("update_date"):
                qd = QDate.fromString(str(update_data["update_date"])[:10], "yyyy-MM-dd")
                if qd.isValid():
                    self.de_date.setDate(qd)
            self.txt_details.setPlainText(update_data.get("update_details") or "")

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel"); btn_cancel.setObjectName("secondaryButton")
        btn_save   = QPushButton("Save");   btn_save.setObjectName("successButton")
        btn_cancel.clicked.connect(self.reject)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        lay.addLayout(btn_row)

    def _save(self):
        details = self.txt_details.toPlainText().strip()
        if not details:
            QMessageBox.warning(self, "Validation", "Update Details cannot be empty.")
            return
        date_str = self.de_date.date().toString("yyyy-MM-dd")
        try:
            if self.update_data:
                self.db.execute(
                    "UPDATE task_updates SET update_date=%s, update_details=%s "
                    "WHERE update_id=%s",
                    (date_str, details, self.update_data["update_id"]),
                )
            else:
                self.db.execute(
                    "INSERT INTO task_updates (task_id, update_date, update_details) "
                    "VALUES (%s, %s, %s)",
                    (self.task_id, date_str, details),
                )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Save failed:\n{exc}")


# ──────────────────────────────────────────────────────────────────────────────
class TasksModule(QWidget):
    """Task Log – full CRUD list view with filters."""

    COLUMNS = ["ID", "Title", "Job Type", "Priority", "Status",
               "Requested By", "Followers", "Requested Date", "Due Date", "Project"]
    COL_WIDTHS = [50, 230, 120, 80, 120, 140, 170, 105, 105, 150]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)

        title = QLabel("Task Log")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        line = QFrame(); line.setObjectName("hLine"); line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        # ── Filter toolbar ────────────────────────────────────────────
        filter_row1 = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setObjectName("searchBar")
        self.inp_search.setPlaceholderText("Search title / description…")
        self.inp_search.textChanged.connect(self.load_data)

        self.cmb_f_status   = QComboBox(); self.cmb_f_status.addItem("All Statuses"); self.cmb_f_status.addItems(STATUSES)
        self.cmb_f_priority = QComboBox(); self.cmb_f_priority.addItem("All Priorities"); self.cmb_f_priority.addItems(PRIORITIES)
        self.cmb_f_jobtype  = QComboBox(); self.cmb_f_jobtype.addItem("All Job Types"); self.cmb_f_jobtype.addItems(JOB_TYPES)
        self.cmb_f_project  = QComboBox(); self.cmb_f_project.addItem("All Projects")

        for cmb in (self.cmb_f_status, self.cmb_f_priority,
                    self.cmb_f_jobtype, self.cmb_f_project):
            cmb.currentIndexChanged.connect(self.load_data)

        self._refresh_project_filter()

        filter_row1.addWidget(self.inp_search)
        filter_row1.addWidget(self.cmb_f_status)
        filter_row1.addWidget(self.cmb_f_priority)
        filter_row1.addWidget(self.cmb_f_jobtype)
        filter_row1.addWidget(self.cmb_f_project)
        root.addLayout(filter_row1)

        # ── Action toolbar ────────────────────────────────────────────
        action_row = QHBoxLayout()
        btn_add    = QPushButton("+ Add Task"); btn_add.setObjectName("successButton")
        btn_import = QPushButton("Import"); btn_import.setObjectName("flatButton")
        btn_edit   = QPushButton("Edit")
        btn_update = QPushButton("Update")
        btn_delete = QPushButton("Delete"); btn_delete.setObjectName("dangerButton")
        btn_refresh = QPushButton("Refresh"); btn_refresh.setObjectName("flatButton")

        btn_add.clicked.connect(self._add)
        btn_import.clicked.connect(self._import)
        btn_edit.clicked.connect(self._edit)
        btn_update.clicked.connect(self._update_task)
        btn_delete.clicked.connect(self._delete)
        btn_refresh.clicked.connect(self.load_data)

        action_row.addStretch()
        action_row.addWidget(btn_refresh)
        action_row.addWidget(btn_add)
        action_row.addWidget(btn_import)
        action_row.addWidget(btn_edit)
        action_row.addWidget(btn_update)
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
        # Click a column header to sort; click again to reverse
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.doubleClicked.connect(self._edit)

        for col, w in enumerate(self.COL_WIDTHS):
            self.table.setColumnWidth(col, w)

        root.addWidget(self.table)

        self.lbl_count = QLabel()
        self.lbl_count.setObjectName("footerLabel")
        root.addWidget(self.lbl_count)

    # ── Helpers ───────────────────────────────────────────────────────
    def _refresh_project_filter(self):
        current = self.cmb_f_project.currentText()
        self.cmb_f_project.blockSignals(True)
        self.cmb_f_project.clear()
        self.cmb_f_project.addItem("All Projects")
        try:
            projects = self.db.get_projects_list()
            for p in projects:
                self.cmb_f_project.addItem(p["project_name"], p["project_id"])
        except Exception:
            pass
        # Restore selection
        idx = self.cmb_f_project.findText(current)
        if idx >= 0:
            self.cmb_f_project.setCurrentIndex(idx)
        self.cmb_f_project.blockSignals(False)

    # ── Data ──────────────────────────────────────────────────────────
    def load_data(self):
        term     = self.inp_search.text().strip()
        status   = self.cmb_f_status.currentText()
        priority = self.cmb_f_priority.currentText()
        jobtype  = self.cmb_f_jobtype.currentText()
        proj_id  = self.cmb_f_project.currentData()

        q = (
            "SELECT t.task_id, t.task_title, t.job_type, t.priority, t.status, "
            "p1.full_name AS req_by_name, t.requested_date, t.due_date, "
            "pr.project_name, "
            "(SELECT GROUP_CONCAT(pe.full_name ORDER BY pe.full_name SEPARATOR ', ') "
            " FROM task_followers tf JOIN people pe ON pe.person_id = tf.person_id "
            " WHERE tf.task_id = t.task_id) AS followers "
            "FROM tasks t "
            "LEFT JOIN people  p1 ON t.requested_by   = p1.person_id "
            "LEFT JOIN projects pr ON t.linked_project = pr.project_id "
            "WHERE 1=1"
        )
        params: list = []

        if term:
            q += " AND (t.task_title LIKE %s OR t.task_description LIKE %s)"
            params += [f"%{term}%", f"%{term}%"]
        if status != "All Statuses":
            q += " AND t.status=%s"; params.append(status)
        if priority != "All Priorities":
            q += " AND t.priority=%s"; params.append(priority)
        if jobtype != "All Job Types":
            q += " AND t.job_type=%s"; params.append(jobtype)
        if proj_id is not None:
            q += " AND t.linked_project=%s"; params.append(proj_id)

        q += " ORDER BY t.task_id DESC"

        try:
            rows = self.db.execute(q, params, fetch=True)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc)); return

        # Disable sorting while we repopulate, then restore it so the
        # current sort indicator is re-applied to the fresh data.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, t in enumerate(rows):
            prio = t.get("priority") or ""
            stat = t.get("status") or ""
            cells = [
                str(t["task_id"]),
                t["task_title"],
                t.get("job_type") or "",
                prio,
                stat,
                t.get("req_by_name") or "",
                t.get("followers") or "",
                str(t["requested_date"])[:10] if t.get("requested_date") else "",
                str(t["due_date"])[:10]       if t.get("due_date")       else "",
                t.get("project_name") or "",
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c == 0:
                    # Store the ID as a number so the column sorts numerically
                    item.setData(Qt.ItemDataRole.DisplayRole, int(t["task_id"]))
                elif c == 3:
                    item.setForeground(QColor(PRIORITY_COLORS.get(prio, "#2d3748")))
                elif c == 4:
                    item.setForeground(QColor(STATUS_COLORS.get(stat, "#2d3748")))
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)

        self.lbl_count.setText(f"{len(rows)} record(s)")

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    # ── Actions ───────────────────────────────────────────────────────
    def _add(self):
        dlg = TaskDialog(self.db, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def open_prefilled_task(self, prefill: dict):
        """Called by Email Parser module to open a pre-filled new task."""
        dlg = TaskDialog(self.db, prefill=prefill, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def _edit(self):
        tid = self._selected_id()
        if not tid:
            QMessageBox.information(self, "Select", "Please select a task to edit.")
            return
        task = self.db.execute(
            "SELECT * FROM tasks WHERE task_id=%s", (tid,), fetch_one=True
        )
        if task:
            dlg = TaskDialog(self.db, task_data=task, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.load_data()

    def _update_task(self):
        tid = self._selected_id()
        if not tid:
            QMessageBox.information(self, "Select", "Please select a task to update.")
            return
        title = self.table.item(self.table.currentRow(), 1).text()
        dlg = TaskUpdateDialog(self.db, tid, title, parent=self)
        dlg.exec()

    def _import(self):
        # Lazy import to avoid a circular import at module load time
        from modules.task_import import ImportTasksDialog, OPENPYXL_OK
        if not OPENPYXL_OK:
            QMessageBox.warning(
                self, "openpyxl missing",
                "openpyxl is not installed.\nRun:  pip install openpyxl",
            )
            return
        dlg = ImportTasksDialog(self.db, parent=self)
        dlg.exec()
        if dlg.imported_any:
            self.load_data()

    def _delete(self):
        tid = self._selected_id()
        if not tid:
            QMessageBox.information(self, "Select", "Please select a task to delete.")
            return
        title = self.table.item(self.table.currentRow(), 1).text()
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete task:\n\"{title}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.execute("DELETE FROM tasks WHERE task_id=%s", (tid,))
                self.load_data()
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Delete failed:\n{exc}")
