from PyQt5.QtCore import QThread, pyqtSignal
from nanoplot_.nanoplot_logic import run_nanoplot


class NanoPlotWorker(QThread):
    status   = pyqtSignal(str)
    finished = pyqtSignal(str)  # report html path
    error    = pyqtSignal(str)

    def __init__(self, input_dir, output_dir):
        super().__init__()
        self.input_dir  = input_dir
        self.output_dir = output_dir

    def run(self):
        try:
            report_path = run_nanoplot(
                self.input_dir, self.output_dir,
                status_callback=self.status.emit
            )
            self.finished.emit(report_path)
        except Exception as e:
            self.error.emit(str(e))