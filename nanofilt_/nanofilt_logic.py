import os
import subprocess


def run_nanofilt(input_path, output_dir, min_quality=10, min_length=200,
                 max_length=None, status_callback=None):

    # derive a clean sample name from the input filename
    basename = os.path.basename(input_path)
    for ext in (".fastq.gz", ".fastq", ".gz"):
        if basename.endswith(ext):
            basename = basename[: -len(ext)]
            break
    output_path = os.path.join(output_dir, f"{basename}_filtered.fastq.gz")

    # support both .fastq.gz and plain .fastq
    if input_path.endswith(".gz"):
        decompress = f"gunzip -c {input_path}"
    else:
        decompress = f"cat {input_path}"

    cmd = f"{decompress} | NanoFilt -q {min_quality} -l {min_length}"
    if max_length:
        cmd += f" --maxlength {max_length}"
    cmd += f" | gzip > {output_path}"

    if status_callback:
        status_callback("Filtering reads...")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"NanoFilt failed:\n{result.stderr}")

    if status_callback:
        status_callback(result.stderr.strip() if result.stderr.strip() else "Done.")

    return output_path
