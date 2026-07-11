"""Premium dialogs for selecting apps and websites (PySide6)."""

import os
import psutil
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QPushButton, QFileDialog,
                               QWidget, QFrame, QListWidgetItem, QScrollArea)
from PySide6.QtCore import Qt

from .widgets import button, label
from ..constants import SUGGESTED_APPS, SUGGESTED_SITES
from ..blocking.website_blocker import is_valid_domain, normalize_domain


class CustomDialog(QDialog):
    def __init__(self, parent, theme, title):
        super().__init__(parent)
        self.theme = theme
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)

        c = theme.c
        self.setStyleSheet(f"""
            QDialog {{ background-color: {c['bg']}; color: {c['text']}; }}
            QListWidget {{
                background-color: {c['card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
                outline: none;
            }}
            QListWidget::item {{ padding: 8px; border-bottom: 1px solid {c['border']}; }}
            QListWidget::item:selected {{ background-color: {c['accent']}; color: white; }}
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 24, 24, 24)
        self.layout.setSpacing(16)

        title_lbl = label(title, "title", theme)
        self.layout.addWidget(title_lbl)


class AppPickerDialog(CustomDialog):
    def __init__(self, parent, theme, callback):
        super().__init__(parent, theme, "Add Application")
        self.callback = callback

        # Search
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("Search running apps...")
        self.search_in.textChanged.connect(self._filter_list)
        self.layout.addWidget(self.search_in)

        # List of running apps
        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)

        self.running_apps = {}
        self._load_running_apps()

        # Quick-add category buttons
        cats_frame = QWidget()
        cats_layout = QHBoxLayout(cats_frame)
        cats_layout.setContentsMargins(0, 0, 0, 0)
        cats_layout.setSpacing(8)

        cats_layout.addWidget(label("Quick Add:", "subtext", theme))
        for cat, items in SUGGESTED_APPS.items():
            btn = button(cat, variant="secondary", theme=theme)
            btn.clicked.connect(
                lambda checked=False, items=items: self._add_multiple(items)
            )
            cats_layout.addWidget(btn)
        cats_layout.addStretch()
        self.layout.addWidget(cats_frame)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        browse_btn = button("Browse .exe", self._browse, variant="secondary", theme=theme)
        bottom_layout.addWidget(browse_btn)
        bottom_layout.addStretch()
        cancel_btn = button("Cancel", self.reject, variant="ghost", theme=theme)
        bottom_layout.addWidget(cancel_btn)
        add_btn = button("Add Selected", self._submit, variant="primary", theme=theme)
        bottom_layout.addWidget(add_btn)
        self.layout.addLayout(bottom_layout)

    def _load_running_apps(self):
        for p in psutil.process_iter(["name"]):
            try:
                name = p.info["name"]
                if name and name.endswith(".exe"):
                    if name.lower() not in (
                        "svchost.exe", "explorer.exe", "taskmgr.exe",
                        "python.exe", "pythonw.exe", "focuslock.exe",
                    ):
                        self.running_apps[name] = name
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        for name in sorted(self.running_apps.keys()):
            self.list_widget.addItem(QListWidgetItem(name))

    def _filter_list(self, text):
        query = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(query not in item.text().lower())

    def _browse(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "", "Executables (*.exe)"
        )
        if file_path:
            exe = os.path.basename(file_path)
            self.callback(exe, exe)
            self.accept()

    def _add_multiple(self, items):
        """Add a category's worth of apps.  *items* is a list of (name, exe) tuples."""
        for name, exe in items:
            self.callback(name, exe)
        self.accept()

    def _submit(self):
        selected = self.list_widget.selectedItems()
        if selected:
            for item in selected:
                exe = item.text()
                self.callback(exe, exe)
            self.accept()


class SitePickerDialog(CustomDialog):
    def __init__(self, parent, theme, callback):
        super().__init__(parent, theme, "Add Website")
        self.callback = callback

        # Manual entry
        self.layout.addWidget(label("Enter website URL or domain:", "text", theme))

        input_layout = QHBoxLayout()
        self.site_in = QLineEdit()
        self.site_in.setPlaceholderText("e.g. facebook.com, youtube.com")
        self.site_in.returnPressed.connect(self._submit)
        input_layout.addWidget(self.site_in)
        add_btn = button("Add", self._submit, variant="primary", theme=theme)
        input_layout.addWidget(add_btn)
        self.layout.addLayout(input_layout)

        # Suggested sites
        self.layout.addSpacing(16)
        self.layout.addWidget(
            label("Or choose from common distractions:", "subtext", theme)
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_inner = QWidget()
        scroll_layout = QVBoxLayout(scroll_inner)

        for cat, domains in SUGGESTED_SITES.items():
            scroll_layout.addWidget(label(cat, "heading", theme))

            row = QHBoxLayout()
            count = 0
            for domain in domains:
                btn = button(
                    domain,
                    lambda checked=False, d=domain: self._add_domain(d),
                    variant="secondary", theme=theme,
                )
                row.addWidget(btn)
                count += 1
                if count >= 3:
                    row.addStretch()
                    scroll_layout.addLayout(row)
                    row = QHBoxLayout()
                    count = 0
            if count > 0:
                row.addStretch()
                scroll_layout.addLayout(row)
            scroll_layout.addSpacing(12)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_inner)
        self.layout.addWidget(scroll)

        # Bottom
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        cancel_btn = button("Close", self.reject, variant="ghost", theme=theme)
        bottom_layout.addWidget(cancel_btn)
        self.layout.addLayout(bottom_layout)

    def _clean_domain(self, text):
        return normalize_domain(text)

    def _add_domain(self, domain):
        if is_valid_domain(domain):
            self.callback(domain, domain)
            self.site_in.clear()
        else:
            self.site_in.setStyleSheet("border: 1px solid red;")
            self.site_in.setPlaceholderText("Invalid domain – try again")
            self.site_in.clear()

    def _submit(self):
        raw = self.site_in.text()
        if raw:
            domain = self._clean_domain(raw)
            if is_valid_domain(domain):
                self._add_domain(domain)
