import os
import re
import json
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog, QCheckBox,
    QDoubleSpinBox, QFormLayout, QComboBox
)
from PyQt5.QtCore import pyqtSignal
from cutadapt_.cutadapt_worker import CutadaptWorker

# ── default primers ────────────────────────────────────────────────────────────
BUILTIN_PRESETS = {
    "csd":   {"f": "TATCGAGAAA",   "r": "TTTCAAT"},
    "dscam": {"f": "ACAGCCGAGATG", "r": "CATCGAGGGCT"},
}

PRESETS_FILE = os.path.join(os.path.dirname(__file__), "primer_presets.json")


def load_presets():
    """Load presets from file, falling back to builtins."""
    if os.path.isfile(PRESETS_FILE):
        try:
            with open(PRESETS_FILE) as fh:
                data = json.load(fh)
            # merge: builtins first, saved on top
            merged = dict(BUILTIN_PRESETS)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(BUILTIN_PRESETS)


def save_presets(presets):
    with open(PRESETS_FILE, "w") as fh:
        json.dump(presets, fh, indent=2)


class CutadaptSection(QGroupBox):
    cutadapt_finished = pyqtSignal(str, str)  # trimmed_path, output_dir

    def __init__(self, parent=None):
        super().__init__("2. Trim Primers (cutadapt)", parent)
        self._presets = load_presets()
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

        # ── gene / preset selector ─────────────────────────────────────────────
        preset_group = QGroupBox("Gene / Primer preset")
        preset_layout = QHBoxLayout()

        self.preset_combo = QComboBox()
        self._refresh_combo()
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)

        save_btn = QPushButton("Save as default")
        save_btn.setFixedWidth(130)
        save_btn.setToolTip(
            "Save the current primer sequences as the default for the selected gene.\n"
            "They will be loaded automatically next time."
        )
        save_btn.clicked.connect(self._save_current_as_preset)

        preset_layout.addWidget(QLabel("Gene:"))
        preset_layout.addWidget(self.preset_combo, stretch=1)
        preset_layout.addWidget(save_btn)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # ── primer sequences ───────────────────────────────────────────────────
        ref_group = QGroupBox(
            "Primer sequences  —  the primers themselves AND everything "
            "before the forward / after the reverse will be removed. "
            "Output contains insert only."
        )
        ref_layout = QFormLayout()

        self.ref1_edit = QLineEdit()
        self.ref2_edit = QLineEdit()
        self.ref1_edit.setMaxLength(80)
        self.ref2_edit.setMaxLength(80)
        self.ref1_edit.setToolTip(
            "Forward start primer (5' end).\n"
            "cutadapt -g: this sequence AND everything before it is removed.\n"
            "Output read starts right after this primer.\n"
            "Recommended length: 18–25 nt. Accepts IUPAC ambiguity codes (N, R, Y…)."
        )
        self.ref2_edit.setToolTip(
            "Forward end primer (3' end).\n"
            "cutadapt -a: this sequence AND everything after it is removed.\n"
            "Output read ends right before this primer.\n"
            "Recommended length: 18–25 nt. Accepts IUPAC ambiguity codes (N, R, Y…)."
        )
        for edit in (self.ref1_edit, self.ref2_edit):
            edit.textChanged.connect(lambda t, e=edit: e.setText(t.upper()))

        error_lbl = QLabel("Error rate:")
        error_lbl.setToolTip(
            "Maximum error rate for primer matching.\n"
            "0.15 = 15% errors — good default for Nanopore.\n"
            "PCR primers are usually present in full; errors come from sequencing noise."
        )
        self.error_spin = QDoubleSpinBox()
        self.error_spin.setRange(0.0, 0.5)
        self.error_spin.setSingleStep(0.05)
        self.error_spin.setValue(0.15)
        self.error_spin.setDecimals(2)
        self.error_spin.setFixedWidth(70)

        ref_layout.addRow("Forward start (5'):", self.ref1_edit)
        ref_layout.addRow("Forward end   (3'):", self.ref2_edit)
        ref_layout.addRow(error_lbl, self.error_spin)
        ref_group.setLayout(ref_layout)
        layout.addWidget(ref_group)

        # load first preset into fields
        self._on_preset_changed(self.preset_combo.currentText())

        # ── input ──────────────────────────────────────────────────────────────
        self.input_label = QLabel("Barcode folder:")
        layout.addWidget(self.input_label)
        self.input_edit, row = self._path_row(
            "Select barcode folder...", self._pick_input, folder=True
        )
        layout.addLayout(row)

        self.merge_check = QCheckBox("Merge all .fastq.gz files before trimming")
        self.merge_check.setChecked(True)
        self.merge_check.stateChanged.connect(self._on_merge_toggle)
        layout.addWidget(self.merge_check)

        # ── output ─────────────────────────────────────────────────────────────
        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output, folder=True
        )
        layout.addLayout(row)

        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        self.run_btn = QPushButton("Run Cutadapt")
        self.run_btn.setToolTip(
            "Trims primers from both ends of each read.\n"
            "Handles both orientations automatically (--revcomp).\n"
            "Reads without primers → untrimmed.fastq.gz."
        )
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

        self.setLayout(layout)

    # ── preset helpers ─────────────────────────────────────────────────────────

    def _refresh_combo(self):
        current = self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems(self._presets.keys())
        idx = self.preset_combo.findText(current)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, name):
        if name in self._presets:
            self.ref1_edit.setText(self._presets[name]["f"].upper())
            self.ref2_edit.setText(self._presets[name]["r"].upper())

    def _save_current_as_preset(self):
        name = self.preset_combo.currentText().strip()
        f = self.ref1_edit.text().strip().upper()
        r = self.ref2_edit.text().strip().upper()
        if not f or not r:
            QMessageBox.warning(self, "Empty primers", "Enter both primer sequences first.")
            return
        self._presets[name] = {"f": f, "r": r}
        save_presets(self._presets)
        QMessageBox.information(self, "Saved",
            f"Primers for '{name}' saved as default.\n\nF: {f}\nR: {r}")

    # ── path helpers ───────────────────────────────────────────────────────────

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
                self, "Select .fastq.gz file", "", "FASTQ (*.fastq.gz *.gz *.fastq)"
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
        if output_dir:
            self.output_edit.setText(output_dir)

    # ── run ────────────────────────────────────────────────────────────────────

    def _run(self):
        input_path = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        ref1_val   = self.ref1_edit.text().strip().upper()
        ref2_val   = self.ref2_edit.text().strip().upper()
        error_rate = self.error_spin.value()
        do_merge   = self.merge_check.isChecked()

        if not ref1_val or not ref2_val:
            QMessageBox.warning(self, "Missing primers", "Please enter both primer sequences.")
            return
        if not self._validate_ref(ref1_val) or not self._validate_ref(ref2_val):
            QMessageBox.warning(self, "Invalid primers",
                "Primers can only contain valid IUPAC nucleotide codes (A, C, G, T, U, R, Y, N…)")
            return
        if do_merge:
            if not input_path or not os.path.isdir(input_path):
                QMessageBox.warning(self, "Missing input", "Please select a valid barcode folder.")
                return
        else:
            if not input_path or not os.path.isfile(input_path):
                QMessageBox.warning(self, "Missing input", "Please select a valid fastq/fastq.gz file.")
                return
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return

        gene = self.preset_combo.currentText()
        self.run_btn.setEnabled(False)
        self.status_lbl.setText("Starting cutadapt...")

        self._worker = CutadaptWorker(
            input_path, output_dir,
            ref1_val, ref2_val,
            error_rate, do_merge,
            sample_name=gene
        )
        self._worker.status.connect(self.status_lbl.setText)
        self._worker.finished.connect(lambda t, u, r: self._on_finished(t, u, r, gene))
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, trimmed, discarded, report, gene):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Done! → {trimmed}")
        QMessageBox.information(self, "Cutadapt done",
            f"Trimming complete! [{gene}]\n\n"
            f"Trimmed:   {trimmed}\n"
            f"Discarded: {discarded}\n"
            f"Report:    {report}\n\n"
            "→ Use trimmed.fastq.gz as input for Quality Filter (step 3).")
        self.cutadapt_finished.emit(trimmed, self.output_edit.text().strip())

    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Cutadapt error", msg)
