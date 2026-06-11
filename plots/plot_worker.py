import os
from PyQt5.QtCore import QThread, pyqtSignal
from plots.plot_logic import plot_all


class PlotWorker(QThread):
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, input_path, threshold_pct):
        super().__init__()
        self.input_path    = input_path
        self.threshold_pct = threshold_pct

    def run(self):
        try:
            fig = plot_all(self.input_path, self.threshold_pct)
            self.finished.emit(fig)
        except Exception as e:
            self.error.emit(str(e))