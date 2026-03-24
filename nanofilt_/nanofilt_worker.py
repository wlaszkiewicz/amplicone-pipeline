from PyQt5.QtCore import QThread, pyqtSignal
from nanofilt_.nanofilt_logic import run_nanofilt

class NanoFiltWorker(QThread):
    status   = pyqtSignal(str)
    finished = pyqtSignal(str)   # emits filtered.fastq.gz path
    error    = pyqtSignal(str)

    def __init__(self, input_path, output_dir, min_quality=10,
                 min_length=200, max_length=None):
        super().__init__()
        self.input_path  = input_path
        self.output_dir  = output_dir
        self.min_quality = min_quality
        self.min_length  = min_length
        self.max_length  = max_length

    def run(self):
        try:
            output_path = run_nanofilt(
                self.input_path, self.output_dir,
                self.min_quality, self.min_length, self.max_length,
                status_callback=self.status.emit
            )
            self.finished.emit(output_path)
        except Exception as e:
            self.error.emit(str(e))
