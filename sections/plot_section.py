import os
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QMessageBox, QFileDialog,
    QDoubleSpinBox, QDialog, QWidget
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from plots.plot_worker import PlotWorker
from shared import has_size_annotations


class PlotsSection(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("7. Plots", parent)
        self._known_paths = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)

        input_lbl = QLabel("Input file:")
        input_lbl.setToolTip(
            "Accepts .fasta files with size and length annotations.\n"
            "Use derep.fasta or clustered_sorted.fasta.\n"
            "Generates 3 plots: length distribution, rank vs abundance, length vs abundance scatter."
        )
        layout.addWidget(input_lbl)
        self.input_edit, row = self._path_row(
            "Auto-filled after derep/cluster, or browse...", self._pick_input, folder=False
        )
        layout.addLayout(row)

        layout.addWidget(QLabel("Output folder:"))
        self.output_edit, row = self._path_row(
            "Select output folder...", self._pick_output, folder=True
        )
        layout.addLayout(row)

        self.status_lbl = QLabel("Ready.")
        layout.addWidget(self.status_lbl)

        # plot button + threshold spinner on same row
        plot_row = QHBoxLayout()
        self.plot_btn = QPushButton("Generate Plots")
        self.plot_btn.setToolTip(
            "Generates 3 plots side by side:\n"
            "1. Length distribution (weighted by abundance)\n"
            "2. Cluster rank vs abundance (shows if you have few dominant sequences)\n"
            "3. Length vs abundance scatter (each dot = one sequence)"
        )
        self.plot_btn.clicked.connect(self._run_plot)
        plot_row.addWidget(self.plot_btn, stretch=1)

        right = QHBoxLayout()
        right.addStretch()
        thr_lbl = QLabel("Outlier threshold (%):")
        thr_lbl.setToolTip(
            "Hide lengths whose read count is below this % of total reads.\n"
            "Only affects the length distribution plot.\n"
            "0.0 = show everything."
        )
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 10.0)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setValue(0.1)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setFixedWidth(70)
        self.threshold_spin.setToolTip(thr_lbl.toolTip())
        right.addWidget(thr_lbl)
        right.addWidget(self.threshold_spin)
        right.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right)
        plot_row.addWidget(right_widget, stretch=1)
        layout.addLayout(plot_row)

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
            self, "Select input file", "", "FASTA (*.fasta *.fa)"
        )
        if f:
            self.input_edit.setText(f)

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.output_edit.setText(d)

    def register_path(self, label, path, output_dir=None):
        """Called by main app to autofill when derep/cluster finishes."""
        self._known_paths[label] = path
        self.input_edit.setText(path)
        if output_dir:
            self.output_edit.setText(output_dir)

    def _run_plot(self):
        input_path = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()

        if not input_path or not os.path.isfile(input_path):
            QMessageBox.warning(self, "Missing input",
                "Please select a valid .fasta file.\n"
                "Use derep.fasta or clustered_sorted.fasta.")
            return
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Missing output", "Please select a valid output folder.")
            return
        if not has_size_annotations(input_path):
            QMessageBox.warning(self, "Missing annotations",
                "This file doesn't have size/length annotations.\n\n"
                "Run Dereplication first — derep.fasta and clustered_sorted.fasta both have them.")
            return

        self.plot_btn.setEnabled(False)
        self.status_lbl.setText("Generating plots...")

        self._worker = PlotWorker(input_path, round(self.threshold_spin.value(), 2))
        self._worker.finished.connect(self._on_plot_ready)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def autofill(self, input_path, output_dir):
        """Called by main app to autofill when derep/cluster finishes."""
        if input_path:
            self.input_edit.setText(input_path)
        if output_dir:
            self.output_edit.setText(output_dir)

    def _on_plot_ready(self, fig):
        self.plot_btn.setEnabled(True)
        self.status_lbl.setText("Ready.")
        output_dir = self.output_edit.text().strip()

        dialog = QDialog(self)
        dialog.setWindowTitle("Sequence Analysis Plots")
        dialog.resize(1400, 520)
        dlg_layout = QVBoxLayout()
        canvas = FigureCanvasQTAgg(fig)
        dlg_layout.addWidget(canvas)

        btn_row = QHBoxLayout()
        save_btn  = QPushButton("Save as PNG")
        close_btn = QPushButton("Close")

        def save_plot():
            out_png = os.path.join(output_dir, "plots.png")
            fig.savefig(out_png, dpi=150, bbox_inches="tight")
            QMessageBox.information(dialog, "Saved", f"Plots saved to:\n{out_png}")

        save_btn.clicked.connect(save_plot)
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        dlg_layout.addLayout(btn_row)
        dialog.setLayout(dlg_layout)
        dialog.exec_()
        plt.close(fig)

    def _on_error(self, msg):
        self.plot_btn.setEnabled(True)
        self.status_lbl.setText("Error.")
        QMessageBox.critical(self, "Plot error", msg)