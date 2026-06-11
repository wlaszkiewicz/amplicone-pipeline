import os
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog, QSpinBox, QCheckBox
)
from PyQt5.QtCore import pyqtSignal
from nanofilt_.nanofilt_worker import NanoFiltWorker


class NanofiltSection(QGroupBox):
    nanofilt_finished = pyqtSignal(str, str)  # filtered_path, output_dir

    def __init__(self, parent=None):
        super().__init__("2. Quality Filter (Nanofilt) [OPTIONAL]", parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

        input_lbl = QLabel("Input file (trimmed.fastq.gz):")
        input_lbl.setToolTip(
            "All sequences with quality below 10 (Q10) were already removed so this is optional.\n"
            "Expected input:.fastq raw from dorado\n"
        )
        layout.addWidget(input_lbl)
        self.input_edit, row = self._path_row(
            "Browse...", self._pick_input, folder=False
        )
        layout.addLayout(row)

        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output, folder=True
        )
        layout.addLayout(row)

        opts_row = QHBoxLayout()

        q_lbl = QLabel("Min quality:")
        q_lbl.setToolTip(
            "Minimum mean quality score (Phred) to keep a read.\n"
            "Q10 = 90% accuracy, Q15 = 97% accuracy.\n"
            "Q10-Q15 is typical."
        )
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(0, 40)
        self.quality_spin.setValue(10)
        self.quality_spin.setFixedWidth(60)
        self.quality_spin.setToolTip(q_lbl.toolTip())

        minlen_lbl = QLabel("Min length:")
        minlen_lbl.setToolTip(
            "Minimum read length to keep (bp).\n"
            "Set based on your expected amplicon size.\n"
            "Shorter reads are likely incomplete or artifacts."
        )
        self.minlen_spin = QSpinBox()
        self.minlen_spin.setRange(0, 100000)
        self.minlen_spin.setValue(200)
        self.minlen_spin.setFixedWidth(80)
        self.minlen_spin.setToolTip(minlen_lbl.toolTip())

        maxlen_lbl = QLabel("Max length:")
        maxlen_lbl.setToolTip(
            "Maximum read length to keep (bp).\n"
            "Uncheck to disable.\n"
            "Useful to remove chimeric or concatenated reads."
        )
        self.maxlen_check = QCheckBox()
        self.maxlen_check.setChecked(False)
        self.maxlen_check.setToolTip("Enable max length filter")
        self.maxlen_spin = QSpinBox()
        self.maxlen_spin.setRange(0, 1000000)
        self.maxlen_spin.setValue(2000)
        self.maxlen_spin.setFixedWidth(80)
        self.maxlen_spin.setEnabled(False)
        self.maxlen_spin.setToolTip(maxlen_lbl.toolTip())
        self.maxlen_check.stateChanged.connect(
            lambda: self.maxlen_spin.setEnabled(self.maxlen_check.isChecked())
        )

        opts_row.addWidget(q_lbl)
        opts_row.addWidget(self.quality_spin)
        opts_row.addSpacing(12)
        opts_row.addWidget(minlen_lbl)
        opts_row.addWidget(self.minlen_spin)
        opts_row.addSpacing(12)
        opts_row.addWidget(maxlen_lbl)
        opts_row.addWidget(self.maxlen_check)
        opts_row.addWidget(self.maxlen_spin)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        self.run_btn = QPushButton("Run Nanofilt")
        self.run_btn.setToolTip(
            "Filters reads by quality score and length.\n"
            "Output: filtered.fastq.gz — use this as input for Dereplication (step 4)."
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
        f, _ = QFileDialog.getOpenFileName(
            self, "Select trimmed.fastq.gz", "", "FASTQ GZ (*.fastq.gz *.gz)"
        )
        if f:
            self.input_edit.setText(f)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.output_edit.setText(d)

    def autofill(self, trimmed_path, output_dir):
        """Called by main app when cutadapt finishes."""
        self.input_edit.setText(trimmed_path)
        self.output_edit.setText(output_dir)

    def _run(self):
        input_path  = self.input_edit.text().strip()
        output_dir  = self.output_edit.text().strip()
        min_quality = self.quality_spin.value()
        min_length  = self.minlen_spin.value()
        max_length  = self.maxlen_spin.value() if self.maxlen_check.isChecked() else None

        if not input_path or not os.path.isfile(input_path):
            QMessageBox.warning(self, "Missing input",
                "Please select a valid input file.\n"
                "Expected: trimmed.fastq.gz from the Cutadapt step.")
            return
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return

        self.run_btn.setEnabled(False)
        self.status_lbl.setText("Starting nanofilt...")

        self._worker = NanoFiltWorker(
            input_path, output_dir,
            min_quality, min_length, max_length
        )
        self._worker.status.connect(self.status_lbl.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, output_path):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Done! → {output_path}")
        QMessageBox.information(
            self, "Nanofilt done",
            f"Filtering complete!\n\nOutput: {output_path}\n\n"
            "→ Use filtered.fastq.gz as input for Dereplication (step 4)."
        )
        self.nanofilt_finished.emit(output_path, self.output_edit.text().strip())
    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Nanofilt error", msg)
