from PyQt5.QtCore import QThread, pyqtSignal
from cutadapt_.cutadapt_logic import run_cutadapt


class CutadaptWorker(QThread):
    status   = pyqtSignal(str)
    finished = pyqtSignal(str, str, str)  # trimmed, untrimmed, report
    error    = pyqtSignal(str)

    def __init__(self, input_path, output_dir, adapter_front, adapter_back,
                 error_rate=0.15, do_merge=False):
        super().__init__()
        self.input_path    = input_path
        self.output_dir    = output_dir
        self.adapter_front = adapter_front
        self.adapter_back  = adapter_back
        self.error_rate    = error_rate
        self.do_merge      = do_merge

    def run(self):
        try:
            trimmed, untrimmed, report = run_cutadapt(
                self.input_path, self.output_dir,
                self.adapter_front, self.adapter_back,
                self.error_rate, self.do_merge,
                status_callback=self.status.emit
            )
            self.finished.emit(trimmed, untrimmed, report)
        except Exception as e:
            self.error.emit(str(e))