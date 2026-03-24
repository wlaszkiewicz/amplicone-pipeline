import os
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog
)
from vsearch.vsearch_worker import StatsWorker


class StatsSection(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Additional Stats", parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

        input_lbl = QLabel("Input file:")
        input_lbl.setToolTip(
            "Accepts .fastq.gz files.\n"
            "Run stats on trimmed or merged output to see how trimming affected the length distribution.\n"
            "It won't work on .fasta files because they don't have quality scores any more."
        )
        layout.addWidget(input_lbl)
        self.input_edit, row = self._path_row(
            "Select .fastq.gz file...", self._pick_input, folder=False
        )
        layout.addLayout(row)

        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output, folder=True
        )
        layout.addLayout(row)


        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        self.stats_btn = QPushButton("Run Stats")
        self.stats_btn.setToolTip(
            "Runs vsearch --fastq_stats on the selected file.\n"
            "Produces fastq_stats.log with length distribution, quality scores, and more.\n"
        )
        self.stats_btn.clicked.connect(self._run_stats)
        layout.addWidget(self.stats_btn)

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
        f, _ = QFileDialog.getOpenFileName(
            self, "Select input file", "",
            "FASTQ (*.fastq.gz *.gz)"
        )
        if f:
            self.input_edit.setText(f)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.output_edit.setText(d)

    def _set_buttons(self, enabled):
        self.stats_btn.setEnabled(enabled)

    def autofill(self, trimmed_path, output_dir):
        """Called by main app when trim finishes."""
        self.input_edit.setText(trimmed_path)
        self.output_edit.setText(output_dir)

    def _run_stats(self):
        input_path = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not input_path or not os.path.isfile(input_path):
            QMessageBox.warning(self, "Missing input",
                "Please select a valid input file.\n"
                "Make sure to run this on a .fastq.gz file with quality scores, not on a .fasta file!")
            return
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return

        self._set_buttons(False)
        self.status_lbl.setText("Running stats...")

        self._stats_worker = StatsWorker(input_path, output_dir)
        self._stats_worker.status.connect(self.status_lbl.setText)
        self._stats_worker.finished.connect(self._on_stats_finished)
        self._stats_worker.error.connect(self._on_error)
        self._stats_worker.start()

    def _on_stats_finished(self, log_path):
        self._set_buttons(True)
        self.status_lbl.setText(f"Done! → {log_path}")
        QMessageBox.information(self, "Stats done",
            f"Stats complete!\n\nLog: {log_path}\n\n")

    def _on_error(self, msg):
        self._set_buttons(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Stats error", msg)
