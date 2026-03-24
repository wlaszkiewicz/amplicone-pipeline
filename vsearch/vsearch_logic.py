import os
import subprocess
from shared import has_size_annotations
import os
import pty
import subprocess

def run_derep(fastq_path, output_path):
    """Run vsearch dereplication on a fasta file."""
    cmd = [
        "vsearch",
        "--fastx_uniques", fastq_path,
        "--fastaout", output_path,
        "--fastq_qmax", "60",
        "--lengthout",
        "--sizeout",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"vsearch derep failed:\n{result.stderr}")
    return result.stderr 


def run_fastq_stats(fastq_path, log_path):
    """Run vsearch --fastq_stats and save output to log file."""
    cmd = [
        "vsearch",
        "--fastq_stats", fastq_path,
        "--log", log_path,
        "--fastq_qmax", "60"
    ]
  
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"vsearch fastq_stats failed:\n{result.stderr}")
    return log_path



def _stream_stderr_pty(cmd, status_callback):
    """Run cmd with a fake terminal so vsearch outputs progress updates."""
    
    master_fd, slave_fd = pty.openpty() 
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=slave_fd,  
        close_fds=True
    )
    os.close(slave_fd)  
    
    buf = ""
    last_emitted = ""
    
    try:
        while True:
            try:
                char = os.read(master_fd, 1).decode('utf-8', errors='replace')
            except OSError:
                break  
            
            if char == '\r':
                line = buf.strip()
                if line and status_callback and line != last_emitted:
                    status_callback(line)
                    last_emitted = line
                buf = ""
                
            elif char == '\n':
                line = buf.strip()
                if line and status_callback and line != last_emitted:
                    status_callback(line)
                    last_emitted = line
                buf = ""
                
            else:
                buf += char
                
    finally:
        os.close(master_fd)
    
    process.wait()
    return process.returncode
        
def run_clustering(fasta_path, output_dir, method='cluster_size', identity=0.97, minsize=1, status_callback=None, check_derep=True):
    """Run vsearch clustering on a fasta file."""
    if check_derep and not has_size_annotations(fasta_path):
        raise ValueError("NO_SIZE_ANNOTATIONS")

    if method not in ['cluster_size', 'cluster_fast']:
        raise ValueError("method must be 'cluster_size' or 'cluster_fast'")

    method_name = "_size" if method == "cluster_size" else "_fast"

    output_path = os.path.join(output_dir, f"clustered{method_name}.fasta")
    sorted_path = os.path.join(output_dir, f"clustered_sorted{method_name}.fasta")
    uc_path     = os.path.join(output_dir, f"clusters{method_name}.uc")

    cmd = [
        "vsearch",
        f"--{method}", fasta_path,
        "--id",        str(identity),
        "--centroids", output_path,
        "--uc",        uc_path,
        "--sizein",
        "--sizeout",
        "--lengthout",
    ]

    returncode = _stream_stderr_pty(cmd, status_callback)
    if returncode != 0:
        raise RuntimeError("vsearch clustering failed")
   

    sort_cmd = [
        "vsearch", "--sortbysize", output_path,
        "--output", sorted_path,
        "--minsize", str(minsize),
    ]
   
    _stream_stderr_pty(sort_cmd, status_callback)
    returncode = _stream_stderr_pty(sort_cmd, status_callback)
    if returncode != 0:
        raise RuntimeError("vsearch sorting failed")


    return sorted_path
