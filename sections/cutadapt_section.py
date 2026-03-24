import os
import re
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog, QCheckBox,
    QDoubleSpinBox, QFormLayout
)
from PyQt5.QtCore import pyqtSignal
from cutadapt_.cutadapt_worker import CutadaptWorker
from constants import ref1, ref2


class CutadaptSection(QGroupBox):
    cutadapt_finished = pyqtSignal(str, str)  # trimmed_path, output_dir

    def __init__(self, parent=None):
        super().__init__("2. Trim Primers (cutadapt)", parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

        # primer sequences
        ref_group = QGroupBox("Primer sequences")
        ref_layout = QFormLayout()

        self.ref1_edit = QLineEdit(ref1)
        self.ref2_edit = QLineEdit(ref2)
        self.ref1_edit.setMaxLength(80)
        self.ref2_edit.setMaxLength(80)
        self.ref1_edit.setToolTip(
            "Forward start primer (5' adapter).\n"
            "Everything before this sequence will be cut off.\n"
            "Accepts IUPAC ambiguity codes."
        )
        self.ref2_edit.setToolTip(
            "Forward end primer (3' adapter).\n"
            "Everything after this sequence will be cut off.\n"
            "Accepts IUPAC ambiguity codes."
        )
        self.ref1_edit.textChanged.connect(
            lambda: self.ref1_edit.setText(self.ref1_edit.text().upper())
        )
        self.ref2_edit.textChanged.connect(
            lambda: self.ref2_edit.setText(self.ref2_edit.text().upper())
        )

        # error rate spinner
        error_lbl = QLabel("Error rate:")
        error_lbl.setToolTip(
            "Maximum allowed error rate for primer matching (mismatches, indels).\n"
            "0.15 = 15% errors allowed — good default for Nanopore.\n"
            "Higher = more lenient matching, more reads trimmed but potentially less accurate."
        )
        self.error_spin = QDoubleSpinBox()
        self.error_spin.setRange(0.0, 0.5)
        self.error_spin.setSingleStep(0.05)
        self.error_spin.setValue(0.15)
        self.error_spin.setDecimals(2)
        self.error_spin.setFixedWidth(70)
        self.error_spin.setToolTip(error_lbl.toolTip())

        ref_layout.addRow("Forward start (5'):", self.ref1_edit)
        ref_layout.addRow("Forward end (3'):",   self.ref2_edit)
        ref_layout.addRow(error_lbl, self.error_spin)
        ref_group.setLayout(ref_layout)
        layout.addWidget(ref_group)

        # input 
        self.input_label = QLabel("Barcode folder:")
        self.input_label.setToolTip(
            "Select the folder containing .fastq.gz files.\n"
            "Files will be merged before trimming.\n"
            "Or uncheck merge to select a single file."
        )
        layout.addWidget(self.input_label)
        self.input_edit, row = self._path_row(
            "Select barcode folder...", self._pick_input, folder=True
        )
        layout.addLayout(row)

        # merge checkbox
        self.merge_check = QCheckBox("Merge all .fastq.gz files before trimming")
        self.merge_check.setChecked(True)
        self.merge_check.setToolTip(
            "Merges all .fastq.gz files in the folder into one before trimming.\n"
            "Recommended — keeps downstream steps simple with a single file.\n"
            "Uncheck to provide a single .fastq.gz file directly."
        )
        self.merge_check.stateChanged.connect(self._on_merge_toggle)
        layout.addWidget(self.merge_check)

        # output folder 
        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output, folder=True
        )
        layout.addLayout(row)

        # status
        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        # button
        self.run_btn = QPushButton("Run Cutadapt")
        self.run_btn.setToolTip(
            "Trims primers from both ends of each read.\n"
            "Automatically handles reads in both orientations (--revcomp).\n"
            "Reads without primers are saved separately as untrimmed.fastq.gz."
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

    def _on_merge_toggle(self):
        if self.merge_check.isChecked():
            self.input_label.setText("Barcode folder:")
            self.input_edit.setPlaceholderText("Select barcode folder...")
        else:
            self.input_label.setText("Input file:")
            self.input_edit.setPlaceholderText("Select .fastq.gz file...")
        self.input_edit.clear()

    def _pick_input(self):
        if self.merge_check.isChecked():
            d = QFileDialog.getExistingDirectory(self, "Select barcode folder")
            if d:
                self.input_edit.setText(d)
        else:
            f, _ = QFileDialog.getOpenFileName(
                self, "Select .fastq.gz file", "", "FASTQ GZ (*.fastq.gz *.gz)"
            )
            if f:
                self.input_edit.setText(f)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.output_edit.setText(d)

    def _validate_ref(self, seq):
        return bool(re.fullmatch(r'[ACGTUacgtuRYSWKMBDHVNryswkmbdhvn]+', seq))

    def autofill(self, input_path, output_dir):
        """Called by main app when NanoPlot finishes — autofill output folder."""
        self.output_edit.setText(output_dir)

    def _run(self):
        input_path  = self.input_edit.text().strip()
        output_dir  = self.output_edit.text().strip()
        ref1_val    = self.ref1_edit.text().strip().upper()
        ref2_val    = self.ref2_edit.text().strip().upper()
        error_rate  = self.error_spin.value()
        do_merge    = self.merge_check.isChecked()

        if not ref1_val or not ref2_val:
            QMessageBox.warning(self, "Missing primers", "Please enter both primer sequences.")
            return
        if not self._validate_ref(ref1_val) or not self._validate_ref(ref2_val):
            QMessageBox.warning(self, "Invalid primers",
                "Primers can only contain valid IUPAC nucleotide codes (A, C, G, T, U, R, Y, etc.)")
            return
        if do_merge:
            if not input_path or not os.path.isdir(input_path):
                QMessageBox.warning(self, "Missing input", "Please select a valid barcode folder.")
                return
        else:
            if not input_path or not os.path.isfile(input_path):
                QMessageBox.warning(self, "Missing input", "Please select a valid .fastq.gz file.")
                return
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return

        self.run_btn.setEnabled(False)
        self.status_lbl.setText("Starting cutadapt...")

        self._worker = CutadaptWorker(
            input_path, output_dir,
            ref1_val, ref2_val,
            error_rate, do_merge
        )
        self._worker.status.connect(self.status_lbl.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, trimmed, discarded, report):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Done! → {trimmed}")
        QMessageBox.information(
            self, "Cutadapt done",
            f"Trimming complete!\n\n"
            f"Trimmed:   {trimmed}\n"
            f"Discarded: {discarded}\n"
            f"Report:    {report}\n\n"
            "→ Use trimmed.fastq.gz as input for Chopper (step 3)."
        )
        self.cutadapt_finished.emit(trimmed, self.output_edit.text().strip())

    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Cutadapt error", msg)
