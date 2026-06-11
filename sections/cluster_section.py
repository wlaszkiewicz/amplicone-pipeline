import os
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog, QComboBox, QDoubleSpinBox, QSpinBox
)
from PyQt5.QtCore import pyqtSignal
from shared import has_size_annotations
from vsearch.vsearch_worker import ClusterWorker


class ClusterSection(QGroupBox):
    # emits clustered_sorted.fasta path when done
    cluster_finished = pyqtSignal(str, str)  # (clustered_path, cluster_method)

    def __init__(self, parent=None):
        super().__init__("5. Clustering", parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

        lbl = QLabel("Input file (derep.fasta):")
        lbl.setToolTip(
            "Expected input: derep.fasta\n"
            "Auto-filled when dereplication finishes.\n"
            "Run Dereplication (step 2) before clustering!"
        )
        layout.addWidget(lbl)
        self.input_edit, row = self._path_row(
            "Auto-filled after derep, or browse...", self._pick_input, folder=False
        )
        layout.addLayout(row)

      
        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output, folder=True
        )
        layout.addLayout(row)

        opts_row = QHBoxLayout()

        # method
        method_lbl = QLabel("Method:")
        method_lbl.setToolTip(
            "cluster_size: sorts by abundance before clustering (recommended for amplicons)\n"
            "cluster_fast: sorts by length before clustering (faster)"
            "cluster_unoise: denoising method that tries to correct errors instead of clustering (experimental)"
        )
        self.method_combo = QComboBox()
        self.method_combo.addItems(["cluster_size", "cluster_fast", "cluster_unoise"])
        self.method_combo.setToolTip(method_lbl.toolTip())

        # identity
        id_lbl = QLabel("Identity (%):")
        id_lbl.setToolTip(
            "Minimum % similarity for two sequences to be clustered together.\n"
            "97% is classic for amplicon OTUs.\n"
            "For Nanopore (1-5% error rate), 97-99% is typical.\n"
            "Lower = more sequences merged, fewer clusters."
        )
        self.identity_spin = QDoubleSpinBox()
        self.identity_spin.setRange(0.50, 1.00)
        self.identity_spin.setSingleStep(0.01)
        self.identity_spin.setValue(0.97)
        self.identity_spin.setDecimals(2)
        self.identity_spin.setFixedWidth(70)
        self.identity_spin.setToolTip(id_lbl.toolTip())

        # min size filter after sort
        minsize_lbl = QLabel("Min size (sort filter):")
        minsize_lbl.setToolTip(
            "After clustering, drop centroids supported by fewer than this many reads.\n"
            "Removes low-confidence clusters likely caused by sequencing errors.\n"
            "Set to 1 to keep everything."
        )
        self.minsize_spin = QSpinBox()
        self.minsize_spin.setRange(1, 10000)
        self.minsize_spin.setValue(1)
        self.minsize_spin.setFixedWidth(70)
        self.minsize_spin.setToolTip(minsize_lbl.toolTip())

        opts_row.addWidget(method_lbl)
        opts_row.addWidget(self.method_combo)
        opts_row.addSpacing(12)
        opts_row.addWidget(id_lbl)
        opts_row.addWidget(self.identity_spin)
        opts_row.addSpacing(12)
        opts_row.addWidget(minsize_lbl)
        opts_row.addWidget(self.minsize_spin)
        opts_row.addStretch()
        layout.addLayout(opts_row)
       
        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        self.run_btn = QPushButton("Run Clustering")
        self.run_btn.setToolTip(
            "Groups similar sequences together within the chosen identity threshold.\n"
            "Output: clustered.fasta + clustered_sorted.fasta (sorted by abundance)\n"
            "Also produces clusters.uc with full cluster membership info."
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
            self, "Select derep.fasta", "", "FASTA (*.fasta *.fa)"
        )
        if f:
            self.input_edit.setText(f)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.output_edit.setText(d)

    def autofill(self, derep_path, output_dir):
        """Called by main app when derep finishes."""
        self.input_edit.setText(derep_path)
        self.output_edit.setText(output_dir)

    def get_output_dir(self):
        return self.output_edit.text().strip()

    def _run(self):
        input_path = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not input_path or not os.path.isfile(input_path):
            QMessageBox.warning(self, "Missing input",
                "Please select a valid input file.\n"
                "Expected: derep.fasta from the Dereplication step.\n\n"
                "Tip: run Dereplication (step 2) first!")
            return
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return

        if not has_size_annotations(input_path):
            reply = QMessageBox.warning(self, "Are you sure?",
                "The input file doesn't look like it was dereped first "
                "(no ;size=  or ;length= in headers).\n\n"
                "Running clustering on raw sequences will take much longer "
                "and can produce unreliable results.\n\n"
                "Do you want to continue anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.run_btn.setEnabled(False)
        self.status_lbl.setText("Running clustering...")

        self._worker = ClusterWorker(
            input_path, output_dir,
            method=self.method_combo.currentText(),
            identity=self.identity_spin.value(),
            minsize=self.minsize_spin.value()
        )
        self._worker.status.connect(self.status_lbl.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, output_path):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Done! → {output_path}")
        QMessageBox.information(self, "Clustering done",
            f"Clustering complete!\n\nSorted output: {output_path}\n\n"
            "Use clustered_sorted.fasta or derep.fasta as input for plotting.")
        self.cluster_finished.emit(output_path, self.method_combo.currentText())

    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Clustering error", msg)
