import os
import subprocess
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog, QSpinBox, QCheckBox, QGridLayout
)
from PyQt5.QtCore import pyqtSignal, QThread


class FilterWorker(QThread):
    status   = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, input_path, output_path, min_size=None, max_size=None,
                 min_length=None, max_length=None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.min_size   = min_size
        self.max_size   = max_size
        self.min_length = min_length
        self.max_length = max_length

    def run(self):
        try:
            cmd = ["vsearch", "--sortbysize", self.input_path, "--output", self.output_path]
            if self.min_size   is not None: cmd += ["--minsize",      str(self.min_size)]
            if self.max_size   is not None: cmd += ["--maxsize",      str(self.max_size)]
            if self.min_length is not None: cmd += ["--minseqlength", str(self.min_length)]
            if self.max_length is not None: cmd += ["--maxseqlength", str(self.max_length)]

            self.status.emit("Filtering...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"vsearch filter failed:\n{result.stderr}")

            self.status.emit(result.stderr.strip() if result.stderr.strip() else "Done.")
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))


class FilterSection(QGroupBox):
    filter_finished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("6. Filter (size && length)", parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

        #input
        input_lbl = QLabel("Input file (clustered_sorted.fasta):")
        input_lbl.setToolTip(
            "Expected input: clustered_sorted.fasta from the Clustering step.\n"
            "Auto-filled when clustering finishes.\n"
            "Or browse to any .fasta file. eg. derep.fasta from step 2."
        )
        layout.addWidget(input_lbl)
        self.input_edit, row = self._path_row(
            "Auto-filled after clustering, or browse...", self._pick_input
        )
        layout.addLayout(row)

        #  output
        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output
        )
        layout.addLayout(row)

        # select all / deselect all 
        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("Select all")
        sel_all_btn.setFixedWidth(90)
        sel_all_btn.clicked.connect(self._select_all)
        desel_all_btn = QPushButton("Deselect all")
        desel_all_btn.setFixedWidth(90)
        desel_all_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(sel_all_btn)
        sel_row.addWidget(desel_all_btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        #  filter grid 
        grid = QGridLayout()
        grid.setSpacing(8)

        self.min_size_check, self.min_size_spin = self._filter_row(
            "Min size:", 1, 10000000, 1000,
            "Minimum number of reads supporting a cluster.\n"
            "Clusters with fewer reads are likely sequencing errors."
        )
        # self.max_size_check, self.max_size_spin = self._filter_row(
        #     "Max size:", 1, 10000000, 100000,
        #     "Maximum number of reads supporting a cluster.\n"
        #     "Rarely needed but can remove dominant contaminants."
        # )
        self.min_len_check, self.min_len_spin = self._filter_row(
            "Min length:", 1, 100000, 200,
            "Minimum sequence length in bp.\n"
            "Removes short sequences likely to be artifacts."
        )
        self.max_len_check, self.max_len_spin = self._filter_row(
            "Max length:", 1, 100000, 500,
            "Maximum sequence length in bp.\n"
            "Removes chimeric or concatenated sequences."
        )

        self._all_checks = [
            self.min_size_check, #self.max_size_check,
            self.min_len_check,  self.max_len_check
        ]
        self._all_spins = [
            self.min_size_spin, #self.max_size_spin,
            self.min_len_spin,  self.max_len_spin
        ]

        for check, spin in zip(self._all_checks, self._all_spins):
            check.stateChanged.connect(lambda state, s=spin: s.setEnabled(state == 2))

        #labels = ["Min size:", "Max size:", "Min length (bp):", "Max length (bp):"]
        labels = ["Min size:", "Min length (bp):", "Max length (bp):"]
        for i, (lbl_text, check, spin) in enumerate(zip(
            labels,
            self._all_checks,
            self._all_spins
        )):
            lbl = QLabel(lbl_text)
            lbl.setToolTip(spin.toolTip())
            grid.addWidget(check, i, 0)
            grid.addWidget(lbl,   i, 1)
            grid.addWidget(spin,  i, 2)

        layout.addLayout(grid)

        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        self.run_btn = QPushButton("Run Filter")
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

        self.setLayout(layout)

    def _filter_row(self, label, min_val, max_val, default, tooltip):
        check = QCheckBox()
        check.setChecked(False)
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setFixedWidth(100)
        spin.setEnabled(False)
        spin.setToolTip(tooltip)
        check.setToolTip(tooltip)
        return check, spin

    def _select_all(self):
        for check in self._all_checks:
            check.setChecked(True)

    def _deselect_all(self):
        for check in self._all_checks:
            check.setChecked(False)

    def _path_row(self, placeholder, callback):
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
            self, "Select .fasta file", "", "FASTA (*.fasta *.fa)"
        )
        if f:
            self.input_edit.setText(f)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.output_edit.setText(d)

    def autofill(self, clustered_path, output_dir):
        self.input_edit.setText(clustered_path)
        self.output_edit.setText(output_dir)

    def _run(self):
        input_path = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not input_path or not os.path.isfile(input_path):
            QMessageBox.warning(self, "Missing input", "Please select a valid .fasta file.")
            return
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return
        if not any(c.isChecked() for c in self._all_checks):
            QMessageBox.warning(self, "No filters selected",
                "Please enable at least one filter.")
            return
        
        if "cluster" in input_path.lower():
            output_name = "filtered_clusters.fasta"
        elif "derep" in input_path.lower():
            output_name = "filtered_derep.fasta"
        else:
            output_name = "filtered.fasta"

        output_path = os.path.join(output_dir, output_name)

        min_size   = self.min_size_spin.value() if self.min_size_check.isChecked() else None
        max_size   = self.max_size_spin.value() if self.max_size_check.isChecked() else None
        min_length = self.min_len_spin.value()  if self.min_len_check.isChecked()  else None
        max_length = self.max_len_spin.value()  if self.max_len_check.isChecked()  else None

        self.run_btn.setEnabled(False)
        self.status_lbl.setText("Running filter...")

        self._worker = FilterWorker(input_path, output_path, min_size, max_size, min_length, max_length)
        self._worker.status.connect(self.status_lbl.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, output_path):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Done! → {output_path}")
        QMessageBox.information(self, "Filter done",
            f"Filtering complete!\n\nOutput: {output_path}\n\n"
            "→ Use filtered_clusters.fasta for plots.")
        self.filter_finished.emit(output_path)

    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Filter error", msg)