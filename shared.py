import time


def has_size_annotations(fasta_path):
    """Check if first sequence header contains ;size=  and ;length= from derep."""
    
    with open(fasta_path, 'r') as f:
        for line in f:
            if line.startswith('>'):
                return ';size=' in line and ';length=' in line
    return False


def stream_stdout(process, status_callback):
    buf = ""
    last_emitted = ""
    assert process.stdout is not None
    while True:
        char = process.stdout.read(1)
        if not char:
            break
        if char in ('\r', '\n'):
            line = buf.strip()
            if line and status_callback and line != last_emitted:
                status_callback(line)
                last_emitted = line
                time.sleep(0.01)
            buf = ""
        else:
            buf += char
    if buf.strip() and status_callback:
        status_callback(buf.strip())