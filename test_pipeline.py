"""
Pipeline tests — derep, clustering, cutadapt.
Uses real tools (vsearch, cutadapt) on tiny synthetic FASTQ/FASTA files in /tmp.
No GUI, no big files.

Run with:
    pytest test_pipeline.py -v
"""

import os
import gzip
import tempfile
import pytest

# ── helpers ────────────────────────────────────────────────────────────────────

def write_fastq_gz(path, reads):
    """reads: list of (name, seq, qual_str)"""
    with gzip.open(path, "wt") as f:
        for name, seq, qual in reads:
            assert len(seq) == len(qual), f"seq/qual length mismatch for {name}"
            f.write(f"@{name}\n{seq}\n+\n{qual}\n")

def write_fasta(path, seqs):
    """seqs: list of (name, seq)"""
    with open(path, "w") as f:
        for name, seq in seqs:
            f.write(f">{name}\n{seq}\n")

def read_fasta(path):
    seqs = []
    with open(path) as f:
        header = None
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                header = line[1:]
            elif header is not None:
                seqs.append((header, line))
                header = None
    return seqs

def count_fastq_gz(path):
    n = 0
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("@"):
                n += 1
    return n

def revcomp(seq):
    comp = str.maketrans("ACGTacgt", "TGCAtgca")
    return seq.translate(comp)[::-1]

def q(n):
    return "I" * n  # phred 40

# Realistic-length sequences (vsearch ignores very short seqs)
SEQ_A = "ACGT" * 30        # 120 nt
SEQ_B = "TTGG" * 30        # 120 nt, different from A
SEQ_C = "CCAA" * 30        # 120 nt

# No-primer sequence: must not partially match TATCGAGAAA or TTTCAAT
# GCGC repeats have no AAA or TTT runs
NO_PRIMER_SEQ = "GCGC" * 20  # 80 nt


# ── DEREP tests ────────────────────────────────────────────────────────────────

class TestDerep:

    def test_strand_both_collapses_revcomp(self, tmp_path):
        """With --strand both, a read and its RC → 1 unique, not 2."""
        from vsearch.vsearch_logic import run_derep

        rc = revcomp(SEQ_A)
        reads = [
            ("read1", SEQ_A, q(len(SEQ_A))),
            ("read2", rc,    q(len(rc))),
        ]
        fastq = str(tmp_path / "input.fastq.gz")
        write_fastq_gz(fastq, reads)

        out = str(tmp_path / "derep.fasta")
        run_derep(fastq, out)

        seqs = read_fasta(out)
        assert len(seqs) == 1, (
            f"Expected 1 unique with --strand both, got {len(seqs)}\n"
            f"Sequences: {[s[1][:20] for s in seqs]}"
        )

    def test_identical_reads_collapsed(self, tmp_path):
        """Three identical reads → one entry with size=3."""
        from vsearch.vsearch_logic import run_derep

        reads = [(f"r{i}", SEQ_A, q(len(SEQ_A))) for i in range(3)]
        fastq = str(tmp_path / "input.fastq.gz")
        write_fastq_gz(fastq, reads)

        out = str(tmp_path / "derep.fasta")
        run_derep(fastq, out)

        seqs = read_fasta(out)
        assert len(seqs) == 1
        assert "size=3" in seqs[0][0], f"Expected size=3, got: {seqs[0][0]}"

    def test_two_different_seqs_both_kept(self, tmp_path):
        """Two different sequences → two entries."""
        from vsearch.vsearch_logic import run_derep

        reads = [
            ("r1", SEQ_A, q(len(SEQ_A))),
            ("r2", SEQ_B, q(len(SEQ_B))),
        ]
        fastq = str(tmp_path / "input.fastq.gz")
        write_fastq_gz(fastq, reads)

        out = str(tmp_path / "derep.fasta")
        run_derep(fastq, out)

        seqs = read_fasta(out)
        assert len(seqs) == 2

    def test_size_annotations_present(self, tmp_path):
        """Output must have ;size= for clustering to work."""
        from vsearch.vsearch_logic import run_derep

        reads = [("r1", SEQ_A, q(len(SEQ_A))), ("r2", SEQ_A, q(len(SEQ_A)))]
        fastq = str(tmp_path / "input.fastq.gz")
        write_fastq_gz(fastq, reads)

        out = str(tmp_path / "derep.fasta")
        run_derep(fastq, out)

        seqs = read_fasta(out)
        assert any("size=" in h for h, _ in seqs), "No ;size= in derep output"

    def test_length_annotations_present(self, tmp_path):
        """Output must have ;length= for plot_logic to work."""
        from vsearch.vsearch_logic import run_derep

        reads = [("r1", SEQ_A, q(len(SEQ_A)))]
        fastq = str(tmp_path / "input.fastq.gz")
        write_fastq_gz(fastq, reads)

        out = str(tmp_path / "derep.fasta")
        run_derep(fastq, out)

        seqs = read_fasta(out)
        assert any("length=" in h for h, _ in seqs), "No ;length= in derep output"


# ── CLUSTERING tests ───────────────────────────────────────────────────────────

class TestClustering:

    def _derep_fasta(self, path, entries):
        """entries: list of (name, seq, size)"""
        with open(path, "w") as f:
            for name, seq, size in entries:
                f.write(f">{name};size={size};length={len(seq)}\n{seq}\n")

    def test_identical_seqs_one_cluster(self, tmp_path):
        """Two identical sequences → one cluster."""
        from vsearch.vsearch_logic import run_clustering

        fasta = str(tmp_path / "derep.fasta")
        self._derep_fasta(fasta, [("s1", SEQ_A, 10), ("s2", SEQ_A, 5)])

        out = run_clustering(fasta, str(tmp_path), identity=0.97,
                             status_callback=None, check_derep=False)
        seqs = read_fasta(out)
        assert len(seqs) == 1, f"Expected 1 cluster, got {len(seqs)}"

    def test_different_seqs_two_clusters(self, tmp_path):
        """Two very different sequences → two clusters."""
        from vsearch.vsearch_logic import run_clustering

        fasta = str(tmp_path / "derep.fasta")
        self._derep_fasta(fasta, [("s1", SEQ_A, 10), ("s2", SEQ_B, 10)])

        out = run_clustering(fasta, str(tmp_path), identity=0.97,
                             status_callback=None, check_derep=False)
        seqs = read_fasta(out)
        assert len(seqs) == 2, f"Expected 2 clusters, got {len(seqs)}"

    def test_output_file_exists_and_nonempty(self, tmp_path):
        """Output file must exist and not be empty."""
        from vsearch.vsearch_logic import run_clustering

        fasta = str(tmp_path / "derep.fasta")
        self._derep_fasta(fasta, [("s1", SEQ_A, 5)])

        out = run_clustering(fasta, str(tmp_path), identity=0.97,
                             status_callback=None, check_derep=False)
        assert os.path.isfile(out), f"Output not found: {out}"
        assert os.path.getsize(out) > 0, "Output file is empty"

    def test_sorted_by_size_descending(self, tmp_path):
        """Largest cluster must come first."""
        from vsearch.vsearch_logic import run_clustering

        fasta = str(tmp_path / "derep.fasta")
        # SEQ_B has bigger size — should be first
        self._derep_fasta(fasta, [("s1", SEQ_A, 2), ("s2", SEQ_B, 100)])

        out = run_clustering(fasta, str(tmp_path), identity=0.97,
                             status_callback=None, check_derep=False)
        seqs = read_fasta(out)
        assert len(seqs) == 2, f"Expected 2 clusters, got {len(seqs)}"

        sizes = []
        for header, _ in seqs:
            for part in header.split(";"):
                if part.startswith("size="):
                    sizes.append(int(part.split("=")[1]))
        assert sizes[0] >= sizes[1], f"Not sorted descending: {sizes}"


# ── CUTADAPT tests ─────────────────────────────────────────────────────────────

PRIMER_F = "TATCGAGAAA"
PRIMER_R = "TTTCAAT"
INSERT   = "GCGCGCGCGCGCGCGCGCGC"  # 20 nt, no primer-like subsequences


class TestCutadapt:

    def _run(self, tmp_path, reads):
        from cutadapt_.cutadapt_logic import run_cutadapt
        fastq = str(tmp_path / "input.fastq.gz")
        write_fastq_gz(fastq, reads)
        trimmed, untrimmed, report = run_cutadapt(
            fastq, str(tmp_path),
            PRIMER_F, PRIMER_R,
            error_rate=0.15, do_merge=False
        )
        return trimmed, untrimmed

    def test_forward_read_trimmed(self, tmp_path):
        """Forward read with primers → trimmed output."""
        seq = PRIMER_F + INSERT + PRIMER_R
        reads = [("r1", seq, q(len(seq)))]
        trimmed, _ = self._run(tmp_path, reads)
        assert count_fastq_gz(trimmed) == 1

    def test_reverse_read_oriented_and_trimmed(self, tmp_path):
        """RC read → --revcomp orients and trims it."""
        fwd = PRIMER_F + INSERT + PRIMER_R
        seq = revcomp(fwd)
        reads = [("r1", seq, q(len(seq)))]
        trimmed, _ = self._run(tmp_path, reads)
        assert count_fastq_gz(trimmed) == 1, \
            "Reverse read should be oriented+trimmed, not discarded"

    def test_no_primer_goes_to_untrimmed(self, tmp_path):
        """Read without primers → untrimmed output."""
        reads = [("r1", NO_PRIMER_SEQ, q(len(NO_PRIMER_SEQ)))]
        _, untrimmed = self._run(tmp_path, reads)
        assert count_fastq_gz(untrimmed) == 1, \
            "Read without primers should go to untrimmed"

    def test_both_output_files_created(self, tmp_path):
        """Both trimmed and untrimmed files must exist."""
        seq = PRIMER_F + INSERT + PRIMER_R
        reads = [("r1", seq, q(len(seq)))]
        trimmed, untrimmed = self._run(tmp_path, reads)
        assert os.path.isfile(trimmed),   f"trimmed.fastq.gz not found"
        assert os.path.isfile(untrimmed), f"untrimmed.fastq.gz not found"

    def test_mixed_batch(self, tmp_path):
        """2 forward + 1 reverse + 1 no-primer → 3 trimmed, 1 untrimmed."""
        fwd = PRIMER_F + INSERT + PRIMER_R
        rev = revcomp(fwd)
        reads = [
            ("fwd1", fwd,           q(len(fwd))),
            ("fwd2", fwd,           q(len(fwd))),
            ("rev1", rev,           q(len(rev))),
            ("nop1", NO_PRIMER_SEQ, q(len(NO_PRIMER_SEQ))),
        ]
        trimmed, untrimmed = self._run(tmp_path, reads)
        assert count_fastq_gz(trimmed)   == 3, \
            f"Expected 3 trimmed, got {count_fastq_gz(trimmed)}"
        assert count_fastq_gz(untrimmed) == 1, \
            f"Expected 1 untrimmed, got {count_fastq_gz(untrimmed)}"
