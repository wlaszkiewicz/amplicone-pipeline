import os
import subprocess
from shared import stream_stdout

def merge_fastq(input_dir, merged_path, status_callback=None):
    """Merge all .fastq.gz files in a folder into one."""
    files = sorted([
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.endswith(".fastq.gz")
    ])
    if not files:
        raise FileNotFoundError(f"No .fastq.gz files found in {input_dir}")

    if status_callback:
        status_callback(f"Merging {len(files)} .fastq.gz files...")

    with open(merged_path, 'wb') as outfile:
        for f in files:
            with open(f, 'rb') as infile:
                outfile.write(infile.read())

    if status_callback:
        status_callback(f"Merged {len(files)} files → {merged_path}")

    return merged_path


def run_cutadapt(input_path, output_dir, adapter_front, adapter_back,
                 error_rate=0.15, do_merge=False, status_callback=None):
    """
    Run cutadapt to trim primers from amplicon Nanopore reads.
    - Trimmed reads → trimmed.fastq.gz
    - Reads without primers → untrimmed.fastq.gz
    """
    if do_merge:
        merged_path = os.path.join(output_dir, "merged.fastq.gz")
        input_path = merge_fastq(input_path, merged_path, status_callback)

    output_path    = os.path.join(output_dir, "trimmed.fastq.gz")
    untrimmed_path = os.path.join(output_dir, "untrimmed.fastq.gz")
    report_path    = os.path.join(output_dir, "cutadapt_report.txt")

    cmd = [
        "cutadapt",
        "-g", adapter_front,
        "-a", adapter_back,
        "--revcomp",
        "-e", str(error_rate),
        "--untrimmed-output", untrimmed_path,
        "-o", output_path,
        "--report", "minimal",
        input_path
    ]

    if status_callback:
        status_callback("Running cutadapt...")

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    assert process.stdout is not None
    assert process.stderr is not None

    stream_stdout(process, status_callback)

    stderr_output = process.stderr.read()
    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"cutadapt failed:\n{stderr_output}")

    with open(report_path, 'w') as f:
        f.write(stderr_output)

    return output_path, untrimmed_path, report_path