import os
import webbrowser
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog, QCheckBox
)
from PyQt5.QtCore import pyqtSignal
from nanoplot_.nanoplot_worker import NanoPlotWorker


class NanoPlotSection(QGroupBox):
    nanoplot_finished = pyqtSignal(str)  #  output_dir

    def __init__(self, parent=None):
        super().__init__("1. Quality Check (NanoPlot)", parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

        self.input_label = QLabel("Barcode folder:")
        self.input_label.setToolTip(
            "Select the folder containing raw .fastq.gz files from your Nanopore run.\n"
            "NanoPlot will analyze all files and generate a quality report.\n"
            "Run this BEFORE trimming to understand your raw data quality."
        )
        layout.addWidget(self.input_label)
        self.input_edit, row = self._path_row(
            "Select barcode folder...", self._pick_input, folder=True
        )
        layout.addLayout(row)

        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output, folder=True
        )
        layout.addLayout(row)

        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        self.run_btn = QPushButton("Run NanoPlot")
        self.run_btn.setToolTip(
            "Generates a quality report for your raw Nanopore reads.\n"
            "The HTML report will open automatically in your browser when done."
        )
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

        self.setLayout(layout)

    def _path_row(self, placeholder, callback, folder=True):
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setReadOnly(True)
        btn = QPushButton("Browse")
        btn.setFixedWidth(70)
        btn.clicked.connect(callback)
        row = QHBoxLayout()
        row.addWidget(edit)
        row.addWidget(btn)
        return edit, row

    def _pick_input(self):
        d = QFileDialog.getExistingDirectory(self, "Select barcode folder")
        if d:
            self.input_edit.setText(d)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.output_edit.setText(d)

    def get_input_path(self):
        return self.input_edit.text().strip()

    def get_output_dir(self):
        return self.output_edit.text().strip()

    def _run(self):
        input_path = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not input_path or not os.path.isdir(input_path):
            QMessageBox.warning(self, "Missing input", "Please select a valid barcode folder.")
            return

        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return

        self.run_btn.setEnabled(False)
        self.status_lbl.setText("Starting NanoPlot...")

        self._worker = NanoPlotWorker(input_path, output_dir)
        self._worker.status.connect(self.status_lbl.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, report_path):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Done! → {report_path}")
        QMessageBox.information(
            self, "NanoPlot done",
            f"Quality report ready!\n\n{report_path}\n\nOpening in browser..."
        )
        webbrowser.open(f"file://{report_path}")
        self.nanoplot_finished.emit(self.output_edit.text().strip())

    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "NanoPlot error", msg)
