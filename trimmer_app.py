import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QScrollArea
from sections.nanoplot_section  import NanoPlotSection
from sections.cutadapt_section  import CutadaptSection
from sections.nanofilt_section   import NanofiltSection
from sections.derep_section     import DerepSection
from sections.cluster_section   import ClusterSection
from sections.plot_section     import PlotsSection
from sections.stats_section     import StatsSection
from sections.filter_section    import FilterSection
import os


class TrimmerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nanopore Amplicon Pipeline")
        self.setMinimumWidth(600)
        self.setMinimumHeight(600)
        self._build_ui()

    def _build_ui(self):
        self.nanoplot_sec  = NanoPlotSection()
        self.cutadapt_sec  = CutadaptSection()
        self.nanofilt_sec   = NanofiltSection()
        self.derep_sec     = DerepSection()
        self.cluster_sec   = ClusterSection()
        self.filter_sec    = FilterSection()
        self.plots_sec     = PlotsSection()
        self.stats_sec     = StatsSection()

        # wire autofill chain
        self.nanoplot_sec.nanoplot_finished.connect(self._on_nanoplot_done)
        self.cutadapt_sec.cutadapt_finished.connect(self._on_cutadapt_done)
        self.nanofilt_sec.nanofilt_finished.connect(self._on_nanofilt_done)
        self.derep_sec.derep_finished.connect(self._on_derep_done)
        self.cluster_sec.cluster_finished.connect(self._on_cluster_done)
        self.filter_sec.filter_finished.connect(self._on_filter_done)

        inner = QWidget()
        inner_layout = QVBoxLayout()
        inner_layout.setSpacing(12)
        inner_layout.setContentsMargins(16, 16, 16, 16)
        inner_layout.addWidget(self.nanoplot_sec)
        inner_layout.addWidget(self.cutadapt_sec)
        inner_layout.addWidget(self.nanofilt_sec)
        inner_layout.addWidget(self.derep_sec)
        inner_layout.addWidget(self.cluster_sec)
        inner_layout.addWidget(self.filter_sec)
        inner_layout.addWidget(self.plots_sec)
        inner_layout.addWidget(self.stats_sec)
        inner_layout.addStretch()
        inner.setLayout(inner_layout)

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        self.setLayout(root)
        
    def _on_nanoplot_done(self, output_dir):
        self.cutadapt_sec.autofill(None, output_dir)

    def _on_cutadapt_done(self, trimmed_path, output_dir):
        self.nanofilt_sec.autofill(trimmed_path, output_dir)

    def _on_nanofilt_done(self, filtered_path, output_dir):
        self.derep_sec.autofill(filtered_path, output_dir)

    def _on_filter_done(self, filtered_path):
  
        output_dir = os.path.dirname(filtered_path)
        self.plots_sec.autofill(filtered_path, output_dir)

    def _on_derep_done(self, derep_path):
        output_dir = os.path.dirname(derep_path)
        self.cluster_sec.autofill(derep_path, output_dir)
        self.plots_sec.autofill( derep_path, output_dir)

    def _on_cluster_done(self, clustered_path, cluster_method):
        output_dir  = os.path.dirname(clustered_path)
        self.plots_sec.autofill(clustered_path, output_dir)
        


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TrimmerApp()
    window.show()
    sys.exit(app.exec_())
