import os
import time
import subprocess
from shared import stream_stdout


def run_nanoplot(input_dir, output_dir, status_callback=None):
    """Run NanoPlot on all .fastq.gz files in a folder."""
    files = sorted([
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.endswith(".fastq.gz") or f.endswith(".fastq")
    ])
    if not files:
        raise FileNotFoundError(f"No .fastq.gz files found in {input_dir}")

    if status_callback:
        status_callback(f"Found {len(files)} files, running NanoPlot...")

    cmd = ["NanoPlot", "--fastq"] + files + ["--outdir", output_dir, "--plots", "dot"]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    assert process.stderr is not None

    stream_stdout(process, status_callback)
    process.wait()

    if process.returncode != 0:
        raise RuntimeError("NanoPlot failed")

    report_path = os.path.join(output_dir, "NanoPlot-report.html")
    if not os.path.isfile(report_path):
        raise FileNotFoundError(f"NanoPlot finished but report not found at {report_path}")

    return report_path