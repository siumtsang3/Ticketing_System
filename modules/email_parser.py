import os
import json
import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QFrame, QScrollArea, QFormLayout,
    QLineEdit, QComboBox, QDateEdit, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from dotenv import load_dotenv

load_dotenv()

JOB_TYPES  = ["Bug Fix", "New Development", "Meeting / Discussion",
               "Documentation", "Support / Maintenance"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250514")


# ──────────────────────────────────────────────────────────────────────────────
PARSE_PROMPT = """\
You are a task-tracking assistant. Parse the email below and extract task fields.
Return ONLY a valid JSON object — no markdown, no explanation, just the JSON.

Required JSON fields:
{
  "task_title":        "<concise action title, max 100 chars>",
  "task_description":  "<full description of what is needed>",
  "requested_by_name": "<sender's full name if identifiable, else empty string>",
  "requested_date":    "<date in YYYY-MM-DD format if mentioned, else today's date>",
  "priority":          "<one of: Low, Medium, High, Critical — infer from urgency>",
  "job_type":          "<one of: Bug Fix, New Development, Meeting / Discussion, Documentation, Support / Maintenance>"
}

EMAIL:
{email_text}
"""


# ──────────────────────────────────────────────────────────────────────────────
class ParseWorker(QThread):
    """Background thread to call Claude API without blocking the UI."""
    finished = pyqtSignal(dict)
    errored  = pyqtSignal(str)

    def __init__(self, email_text: str):
        super().__init__()
        self.email_text = email_text

    def run(self):
        try:
            import anthropic
        except ImportError:
            self.errored.emit(
                "anthropic package not installed.\nRun: pip install anthropic"
            )
            return

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            self.errored.emit(
                "ANTHROPIC_API_KEY is not set in your .env file."
            )
            return

        try:
            client = anthropic.Anthropic(api_key=api_key)
            prompt = PARSE_PROMPT.replace("{email_text}", self.email_text)
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()

            # Strip any accidental markdown code fences
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

            data = json.loads(raw)
            self.finished.emit(data)
        except json.JSONDecodeError:
            self.errored.emit(
                f"Claude returned non-JSON output:\n\n{raw}"
            )
        except Exception as exc:
            self.errored.emit(str(exc))


# ──────────────────────────────────────────────────────────────────────────────
class EmailParserModule(QWidget):
    """Email-to-Task parser powered by Claude AI."""

    # Signal emitted when user confirms a task; main window connects this
    # to TasksModule.open_prefilled_task(prefill_dict).
    task_confirmed = pyqtSignal(dict)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._worker: ParseWorker | None = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("Email-to-Task Parser")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Paste an email below, click Parse, review the extracted fields, "
            "then click Create Task to save it."
        )
        subtitle.setStyleSheet("color: #718096; font-size: 13px;")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        line = QFrame(); line.setObjectName("hLine"); line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        # ── Email input area ─────────────────────────────────────────
        root.addWidget(QLabel("Paste email content here:"))
        self.txt_email = QTextEdit()
        self.txt_email.setPlaceholderText(
            "Paste the full email text here (headers + body)…"
        )
        self.txt_email.setMinimumHeight(180)
        root.addWidget(self.txt_email)

        # Parse button + status
        parse_row = QHBoxLayout()
        self.btn_parse = QPushButton("Parse with AI")
        self.btn_parse.setObjectName("warningButton")
        self.btn_parse.setFixedWidth(160)
        self.btn_parse.clicked.connect(self._parse)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #718096; font-size: 12px;")

        parse_row.addWidget(self.btn_parse)
        parse_row.addWidget(self.lbl_status)
        parse_row.addStretch()
        root.addLayout(parse_row)

        # ── Result panel (hidden until parse completes) ───────────────
        self._result_frame = QFrame()
        self._result_frame.setObjectName("resultFrame")
        self._result_frame.setStyleSheet(
            "QFrame#resultFrame { background: #ffffff; border: 1px solid #e2e8f0; "
            "border-radius: 8px; }"
        )
        self._result_frame.setVisible(False)

        result_lay = QVBoxLayout(self._result_frame)
        result_lay.setContentsMargins(20, 16, 20, 16)
        result_lay.setSpacing(10)

        res_title = QLabel("Parsed Fields  (edit before saving)")
        res_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #2d3748;")
        result_lay.addWidget(res_title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(16)

        self.inp_title    = QLineEdit()
        self.txt_desc     = QTextEdit(); self.txt_desc.setFixedHeight(72)
        self.inp_req_by   = QLineEdit(); self.inp_req_by.setPlaceholderText("Person name as mentioned in email")
        self.de_req_date  = QDateEdit(); self.de_req_date.setCalendarPopup(True); self.de_req_date.setDisplayFormat("dd/MM/yyyy")
        self.cmb_priority = QComboBox(); self.cmb_priority.addItems(PRIORITIES)
        self.cmb_job_type = QComboBox(); self.cmb_job_type.addItems(JOB_TYPES)

        form.addRow("Task Title:",     self.inp_title)
        form.addRow("Description:",    self.txt_desc)
        form.addRow("Requested By:",   self.inp_req_by)
        form.addRow("Requested Date:", self.de_req_date)
        form.addRow("Priority:",       self.cmb_priority)
        form.addRow("Job Type:",       self.cmb_job_type)

        result_lay.addLayout(form)

        # Confirmation buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_clear  = QPushButton("Clear");       btn_clear.setObjectName("secondaryButton")
        btn_create = QPushButton("Create Task →"); btn_create.setObjectName("successButton")
        btn_clear.clicked.connect(self._clear)
        btn_create.clicked.connect(self._create_task)
        btn_row.addWidget(btn_clear)
        btn_row.addWidget(btn_create)
        result_lay.addLayout(btn_row)

        root.addWidget(self._result_frame)
        root.addStretch()

    # ── Parse ─────────────────────────────────────────────────────────
    def _parse(self):
        email_text = self.txt_email.toPlainText().strip()
        if not email_text:
            QMessageBox.warning(self, "Empty", "Please paste an email first.")
            return

        self.btn_parse.setEnabled(False)
        self.lbl_status.setText("Analysing with Claude AI…")
        self._result_frame.setVisible(False)

        self._worker = ParseWorker(email_text)
        self._worker.finished.connect(self._on_parse_done)
        self._worker.errored.connect(self._on_parse_error)
        self._worker.start()

    def _on_parse_done(self, data: dict):
        self.btn_parse.setEnabled(True)
        self.lbl_status.setText("Done — review the fields below.")

        self.inp_title.setText(data.get("task_title", ""))
        self.txt_desc.setPlainText(data.get("task_description", ""))
        self.inp_req_by.setText(data.get("requested_by_name", ""))

        req_date = data.get("requested_date", "")
        if req_date:
            qd = QDate.fromString(req_date[:10], "yyyy-MM-dd")
            self.de_req_date.setDate(qd if qd.isValid() else QDate.currentDate())
        else:
            self.de_req_date.setDate(QDate.currentDate())

        priority = data.get("priority", "Medium")
        idx = self.cmb_priority.findText(priority, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.cmb_priority.setCurrentIndex(idx)

        job_type = data.get("job_type", "")
        idx = self.cmb_job_type.findText(job_type, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.cmb_job_type.setCurrentIndex(idx)

        self._result_frame.setVisible(True)

    def _on_parse_error(self, msg: str):
        self.btn_parse.setEnabled(True)
        self.lbl_status.setText("Parse failed.")
        QMessageBox.critical(self, "Parse Error", msg)

    # ── Create Task ───────────────────────────────────────────────────
    def _create_task(self):
        if not self.inp_title.text().strip():
            QMessageBox.warning(self, "Validation", "Task Title is required.")
            return

        prefill = {
            "task_title":        self.inp_title.text().strip(),
            "task_description":  self.txt_desc.toPlainText().strip(),
            "requested_by_name": self.inp_req_by.text().strip(),
            "requested_date":    self.de_req_date.date().toString("yyyy-MM-dd"),
            "priority":          self.cmb_priority.currentText(),
            "job_type":          self.cmb_job_type.currentText(),
        }
        self.task_confirmed.emit(prefill)

    def _clear(self):
        self.txt_email.clear()
        self.inp_title.clear()
        self.txt_desc.clear()
        self.inp_req_by.clear()
        self.de_req_date.setDate(QDate.currentDate())
        self._result_frame.setVisible(False)
        self.lbl_status.setText("")
