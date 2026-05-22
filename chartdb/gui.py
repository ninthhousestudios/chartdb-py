"""PySide6 GUI for chartdb — browse, search, filter, and find similar charts."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTableView, QLabel, QFileDialog,
    QHeaderView, QSplitter, QGroupBox, QTextEdit, QStatusBar,
    QComboBox, QScrollArea, QFrame,
)

from .db import ChartDB
from .properties import GRAHAS


SUBJECTS = ["Lagna"] + GRAHAS

PROPERTIES = [
    ("sign_name", "Sign"),
    ("house", "House"),
    ("nakshatra", "Nakshatra"),
    ("dignity", "Dignity"),
    ("lajjitaadi", "Lajjitaadi"),
    ("baladi_avastha", "Baladi"),
    ("jagradadi_avastha", "Jagradadi"),
    ("deeptadi_avastha", "Deeptadi"),
    ("shayanadi_avastha", "Shayanadi"),
    ("retrograde", "Retrograde"),
    ("trimsamsa_being", "Trimsamsa Being"),
    ("trimsamsa_lord", "Trimsamsa Lord"),
]


class FilterRow(QFrame):

    def __init__(self, db: ChartDB, parent=None):
        super().__init__(parent)
        self.db = db
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.subject_combo = QComboBox()
        self.subject_combo.addItem("", "")
        for s in SUBJECTS:
            self.subject_combo.addItem(s, s)
        self.subject_combo.currentIndexChanged.connect(self._on_subject_changed)
        layout.addWidget(self.subject_combo)

        self.property_combo = QComboBox()
        self.property_combo.addItem("", "")
        for db_name, display in PROPERTIES:
            self.property_combo.addItem(display, db_name)
        self.property_combo.currentIndexChanged.connect(self._on_property_changed)
        layout.addWidget(self.property_combo)

        self.value_combo = QComboBox()
        self.value_combo.addItem("", "")
        self.value_combo.currentIndexChanged.connect(self._on_value_changed)
        layout.addWidget(self.value_combo)

        self.source_combo = QComboBox()
        self.source_combo.addItem("(any)", "")
        self.source_combo.hide()
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        layout.addWidget(self.source_combo)

        self.mechanism_combo = QComboBox()
        self.mechanism_combo.addItem("(any)", "")
        self.mechanism_combo.hide()
        layout.addWidget(self.mechanism_combo)

        self.remove_btn = QPushButton("x")
        self.remove_btn.setMaximumWidth(30)
        layout.addWidget(self.remove_btn)

    def _on_subject_changed(self, index):
        self._populate_values()

    def _on_property_changed(self, index):
        self._populate_values()

    def _on_value_changed(self, index):
        self._populate_sources()

    def _populate_values(self):
        self.value_combo.clear()
        self.value_combo.addItem("", "")
        self.source_combo.hide()
        subject = self.subject_combo.currentData()
        prop = self.property_combo.currentData()
        if subject and prop:
            values = self.db.list_property_values(prop, subject)
            for v in values:
                self.value_combo.addItem(v, v)

    def _populate_sources(self):
        self.source_combo.clear()
        self.source_combo.addItem("(any)", "")
        self.mechanism_combo.hide()
        prop = self.property_combo.currentData()
        if prop != "lajjitaadi":
            self.source_combo.hide()
            return
        subject = self.subject_combo.currentData()
        avastha = self.value_combo.currentData()
        if not subject or not avastha:
            self.source_combo.hide()
            return
        by_values = self.db.list_property_values("lajjitaadi_by", subject)
        sources = sorted({v.split(":", 1)[1] for v in by_values if v.startswith(f"{avastha}:")})
        if sources:
            for s in sources:
                self.source_combo.addItem(f"by {s}", s)
            self.source_combo.show()
        else:
            self.source_combo.hide()

    def _on_source_changed(self, index):
        self._populate_mechanisms()

    def _populate_mechanisms(self):
        self.mechanism_combo.clear()
        self.mechanism_combo.addItem("(any)", "")
        subject = self.subject_combo.currentData()
        avastha = self.value_combo.currentData()
        source = self.source_combo.currentData()
        if not subject or not avastha or not source:
            self.mechanism_combo.hide()
            return
        via_values = self.db.list_property_values("lajjitaadi_via", subject)
        prefix = f"{avastha}:{source}:"
        mechanisms = sorted({v[len(prefix):] for v in via_values if v.startswith(prefix)})
        if mechanisms:
            for m in mechanisms:
                self.mechanism_combo.addItem(m, m)
            self.mechanism_combo.show()
        else:
            self.mechanism_combo.hide()

    def get_filter(self) -> tuple[str, str, str] | None:
        subject = self.subject_combo.currentData()
        prop = self.property_combo.currentData()
        value = self.value_combo.currentData()
        if not (subject and prop and value):
            return None
        if prop == "lajjitaadi":
            source = self.source_combo.currentData()
            mechanism = self.mechanism_combo.currentData() if source else ""
            if source and mechanism:
                return (subject, "lajjitaadi_via", f"{value}:{source}:{mechanism}")
            if source:
                return (subject, "lajjitaadi_by", f"{value}:{source}")
        return (subject, prop, value)


class ChartDBWindow(QMainWindow):

    def __init__(self, db: ChartDB):
        super().__init__()
        self.db = db
        self.setWindowTitle("ChartDB")
        self.setMinimumSize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # toolbar
        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search charts (name, place, notes)...")
        self.search_input.returnPressed.connect(self._on_search)
        toolbar.addWidget(self.search_input)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search)
        toolbar.addWidget(search_btn)

        show_all_btn = QPushButton("Show All")
        show_all_btn.clicked.connect(self._load_all)
        toolbar.addWidget(show_all_btn)

        import_btn = QPushButton("Import...")
        import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(import_btn)

        layout.addLayout(toolbar)

        # filter section
        filter_group = QGroupBox("Property Filters")
        filter_outer = QVBoxLayout(filter_group)

        self.filter_rows_layout = QVBoxLayout()
        filter_outer.addLayout(self.filter_rows_layout)
        self.filter_rows: list[FilterRow] = []

        filter_buttons = QHBoxLayout()
        add_filter_btn = QPushButton("+ Add Filter")
        add_filter_btn.clicked.connect(self._add_filter_row)
        filter_buttons.addWidget(add_filter_btn)

        apply_filter_btn = QPushButton("Apply Filters")
        apply_filter_btn.clicked.connect(self._on_apply_filters)
        filter_buttons.addWidget(apply_filter_btn)

        clear_filter_btn = QPushButton("Clear Filters")
        clear_filter_btn.clicked.connect(self._on_clear_filters)
        filter_buttons.addWidget(clear_filter_btn)

        filter_buttons.addStretch()
        filter_outer.addLayout(filter_buttons)
        layout.addWidget(filter_group)

        # main splitter: chart list | detail + similar
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # left: chart table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_table = QTableView()
        self.chart_table.setSelectionBehavior(QTableView.SelectRows)
        self.chart_table.setSelectionMode(QTableView.SingleSelection)
        self.chart_table.setSortingEnabled(True)
        left_layout.addWidget(self.chart_table)
        splitter.addWidget(left)

        # right: detail + similarity
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        detail_group = QGroupBox("Chart Details")
        detail_layout = QVBoxLayout(detail_group)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(200)
        detail_layout.addWidget(self.detail_text)
        right_layout.addWidget(detail_group)

        sim_group = QGroupBox("Similar Charts")
        sim_layout = QVBoxLayout(sim_group)
        sim_toolbar = QHBoxLayout()
        self.find_similar_btn = QPushButton("Find Similar (all)")
        self.find_similar_btn.clicked.connect(self._on_find_similar)
        sim_toolbar.addWidget(self.find_similar_btn)

        self.find_similar_filtered_btn = QPushButton("Find Similar (with filters)")
        self.find_similar_filtered_btn.clicked.connect(self._on_find_similar_filtered)
        sim_toolbar.addWidget(self.find_similar_filtered_btn)

        sim_toolbar.addStretch()
        sim_layout.addLayout(sim_toolbar)

        self.similar_table = QTableView()
        self.similar_table.setSelectionBehavior(QTableView.SelectRows)
        self.similar_table.setSortingEnabled(True)
        sim_layout.addWidget(self.similar_table)
        right_layout.addWidget(sim_group)

        splitter.addWidget(right)
        splitter.setSizes([500, 500])

        # status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # models
        self._setup_models()
        self._load_all()

    def _setup_models(self):
        self.chart_model = QStandardItemModel()
        self.chart_model.setHorizontalHeaderLabels(["Name", "Place", "JD", "Tags"])
        self.chart_table.setModel(self.chart_model)
        self.chart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.chart_table.setSelectionMode(QTableView.SingleSelection)
        self.chart_table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self.similar_model = QStandardItemModel()
        self.similar_model.setHorizontalHeaderLabels(["Name", "Place", "Distance"])
        self.similar_table.setModel(self.similar_model)
        self.similar_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

    def _load_all(self):
        charts = self.db.list_charts()
        self._populate_chart_model(charts)
        self.status.showMessage(f"{len(charts)} charts loaded")

    def _populate_chart_model(self, charts: list[dict]):
        self.chart_model.removeRows(0, self.chart_model.rowCount())
        for c in charts:
            tags = ", ".join(
                r["tag"] for r in self.db.conn.execute(
                    "select tag from chart_tags where chart_id = ?", (c["id"],)
                )
            )
            row = [
                QStandardItem(c["name"] or ""),
                QStandardItem(c.get("placename") or ""),
                QStandardItem(f"{c['jd']:.4f}"),
                QStandardItem(tags),
            ]
            row[0].setData(c["id"], Qt.UserRole)
            self.chart_model.appendRow(row)

    def _on_search(self):
        query = self.search_input.text().strip()
        if not query:
            self._load_all()
            return
        results = self.db.search(query)
        self._populate_chart_model(results)
        self.status.showMessage(f"{len(results)} results for '{query}'")

    def _on_selection_changed(self, selected, deselected):
        indexes = self.chart_table.selectionModel().selectedRows()
        if not indexes:
            self.detail_text.clear()
            return
        item = self.chart_model.item(indexes[0].row(), 0)
        chart_id = item.data(Qt.UserRole)
        chart = self.db.get_chart(chart_id)
        if chart:
            self._show_detail(chart)

    def _show_detail(self, chart: dict):
        lines = [
            f"Name: {chart['name']}",
            f"Place: {chart.get('placename') or 'unknown'}",
            f"JD: {chart['jd']:.6f}",
            f"Lat: {chart['lat']:.4f}  Lon: {chart['lon']:.4f}",
            f"UTC Offset: {chart['utc_offset']}",
            f"Tags: {', '.join(chart.get('tags', []))}",
            "",
        ]

        props = self.db.get_chart_properties(chart["id"])
        current_subject = None
        for p in props:
            if p["subject"] != current_subject:
                current_subject = p["subject"]
                lines.append(f"\n{current_subject}:")
            lines.append(f"  {p['property']}: {p['value']}")

        self.detail_text.setPlainText("\n".join(lines))

    # -- filters --

    def _add_filter_row(self):
        row = FilterRow(self.db)
        row.remove_btn.clicked.connect(lambda: self._remove_filter_row(row))
        self.filter_rows.append(row)
        self.filter_rows_layout.addWidget(row)

    def _remove_filter_row(self, row: FilterRow):
        self.filter_rows.remove(row)
        self.filter_rows_layout.removeWidget(row)
        row.deleteLater()

    def _get_active_filters(self) -> list[tuple[str, str, str]]:
        filters = []
        for row in self.filter_rows:
            f = row.get_filter()
            if f:
                filters.append(f)
        return filters

    def _on_apply_filters(self):
        filters = self._get_active_filters()
        if not filters:
            self._load_all()
            return
        results = self.db.filter_by_properties(filters)
        self._populate_chart_model(results)
        desc = " AND ".join(f"{s}.{p}={v}" for s, p, v in filters)
        self.status.showMessage(f"{len(results)} charts matching: {desc}")

    def _on_clear_filters(self):
        for row in self.filter_rows[:]:
            self._remove_filter_row(row)
        self._load_all()

    # -- similarity --

    def _selected_chart_id(self) -> str | None:
        indexes = self.chart_table.selectionModel().selectedRows()
        if not indexes:
            self.status.showMessage("Select a chart first")
            return None
        item = self.chart_model.item(indexes[0].row(), 0)
        return item.data(Qt.UserRole)

    def _show_similar_results(self, results: list):
        self.similar_model.removeRows(0, self.similar_model.rowCount())
        for chart, dist in results:
            row = [
                QStandardItem(chart["name"] or ""),
                QStandardItem(chart.get("placename") or ""),
                QStandardItem(f"{dist:.4f}"),
            ]
            self.similar_model.appendRow(row)
        self.status.showMessage(f"{len(results)} similar charts found")

    def _on_find_similar(self):
        chart_id = self._selected_chart_id()
        if not chart_id:
            return
        results = self.db.similar(chart_id, n=20)
        self._show_similar_results(results)

    def _on_find_similar_filtered(self):
        chart_id = self._selected_chart_id()
        if not chart_id:
            return
        filters = self._get_active_filters()
        results = self.db.filter_then_similar(chart_id, filters, n=20)
        self._show_similar_results(results)
        if filters:
            desc = " AND ".join(f"{s}.{p}={v}" for s, p, v in filters)
            self.status.showMessage(f"{len(results)} similar charts within filter: {desc}")

    # -- import --

    def _on_import(self):
        path = QFileDialog.getExistingDirectory(self, "Select directory with .chtk files")
        if path:
            ids = self.db.import_directory(path)
            self._load_all()
            self.status.showMessage(f"Imported {len(ids)} charts")


def run_gui(db_path: str = "charts.db"):
    app = QApplication(sys.argv)
    db = ChartDB(db_path)
    window = ChartDBWindow(db)
    window.show()
    ret = app.exec()
    db.close()
    sys.exit(ret)
