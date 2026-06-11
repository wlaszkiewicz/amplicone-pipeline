import os
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog
)
from PyQt5.QtCore import pyqtSignal
from vsearch.vsearch_worker import DerepWorker


class DerepSection(QGroupBox):
    derep_finished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("4. Dereplication", parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

     
        lbl = QLabel("Input file (trimmed.fastq.gz):")
        lbl.setToolTip(
            "Expected input: trimmed.fastq.gz\n"
            "Merges strictly identical sequences (same length + nucleotides)."
        )
        layout.addWidget(lbl)
        self.input_edit, row = self._path_row(
            "Auto-filled after trim, or browse...", self._pick_input, folder=False
        )
        layout.addLayout(row)

   
        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output, folder=True
        )
        layout.addLayout(row)

        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        self.run_btn = QPushButton("Run Derep")
        self.run_btn.setToolTip(
            "Merges strictly identical sequences into unique entries.\n"
            "--strand both: reads and their reverse complements are treated as the same sequence\n"
            "— no separate orientation step needed.\n"
            "Accepts .fastq, .fastq.gz files.\n"
            "Output: derep.fasta — use this as input for clustering."
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
            self, "Select fastq.gz or fastq files", "", "FASTQ GZ (*.fastq.gz *.gz );;FASTQ (*.fastq)"
        )
        if f:
            self.input_edit.setText(f)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.output_edit.setText(d)

    def autofill(self, trimmed_path, output_dir):
        """Called by main app when trim finishes.""" 
        self.input_edit.setText(trimmed_path)
        self.output_edit.setText(output_dir)

    def get_derep_path(self):
        file_name = self.input_edit.text().strip()
        base_name = os.path.basename(file_name)
        barcode_number = base_name.find("barcode") # find the position of "barcode" in the filename
        if barcode_number != -1:
            sample_name = base_name[:barcode_number+2] # extract the sample name after "barcode"
        
        return os.path.join(self.output_edit.text().strip(), sample_name + "_derep.fasta" if sample_name else "derep.fasta")

    def get_output_dir(self):
        return self.output_edit.text().strip()

    def _run(self):
        input_path = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not input_path or not os.path.isfile(input_path):
            QMessageBox.warning(self, "Missing input",
                "Please select a valid input file.\n"
                "Expected: trimmed.fastq.gz from the Trim step.")
            return
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return

        self.run_btn.setEnabled(False)
        self.status_lbl.setText("Running dereplication...")

        self._worker = DerepWorker(input_path, output_dir)
        self._worker.status.connect(self.status_lbl.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, output_path):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(f"Done! → {output_path}")
        QMessageBox.information(self, "Derep done",
            f"Dereplication complete!\n\nOutput: {output_path}\n\n"
            "Use derep.fasta as input for clustering.")
        self.derep_finished.emit(output_path)

    def _on_error(self, msg):
        self.run_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Derep error", msg)