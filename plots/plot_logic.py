import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import defaultdict
from shared import has_size_annotations


def parse_fasta_annotations(fasta_path):
    """
    Parse all headers and return:
    - length_counts: dict of length -> total reads (weighted by size)
    - sizes: list of all size values (one per sequence)
    - lengths: list of all length values (one per sequence)
    """
    if not has_size_annotations(fasta_path):
        raise ValueError("NO_SIZE_ANNOTATIONS")

    size_re   = re.compile(r";size=(\d+)")
    length_re = re.compile(r";length=(\d+)")

    length_counts = defaultdict(int)
    sizes   = []
    lengths = []

    with open(fasta_path, "r", buffering=1 << 20) as f:
        for line in f:
            if line[0] != ">":
                continue
            sm = size_re.search(line)
            if not sm:
                continue
            lm = length_re.search(line)
            if not lm:
                continue
            size   = int(sm.group(1))
            length = int(lm.group(1))
            sizes.append(size)
            lengths.append(length)
            length_counts[length] += size

    if not sizes:
        raise ValueError("Could not find any annotated sequences.")

    return length_counts, sizes, lengths


def trim_outliers(lengths, counts, threshold_pct=0.1):
    total  = sum(counts)
    cutoff = total * (threshold_pct / 100)
    paired = list(zip(lengths, counts))
    while paired and paired[0][1] < cutoff:
        paired.pop(0)
    while paired and paired[-1][1] < cutoff:
        paired.pop()
    if not paired:
        return lengths, counts
    return [p[0] for p in paired], [p[1] for p in paired]


def plot_all(fasta_path, threshold_pct=0.1):
    """Generate all three plots side by side and return the figure."""
    length_counts, sizes, seq_lengths = parse_fasta_annotations(fasta_path)

    # sort for length distribution
    paired  = sorted(length_counts.items())
    lengths = [p[0] for p in paired]
    counts  = [p[1] for p in paired]
    total_lengths = len(lengths)
    lengths_trimmed, counts_trimmed = trim_outliers(lengths, counts, threshold_pct)
    n_dropped = total_lengths - len(lengths_trimmed)

    # sort sizes descending for rank plot
    sizes_sorted = sorted(sizes, reverse=True)
    ranks = list(range(1, len(sizes_sorted) + 1))

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # --- Plot 1: Length distribution ---
    ax1 = axes[0]
    ax1.bar(lengths_trimmed, counts_trimmed, width=1.0, color="steelblue", edgecolor="none")
    ax1.set_xlabel("Read length (bp)")
    ax1.set_ylabel("Number of reads")
    ax1.set_title("Length Distribution\n(weighted by abundance)")
    ax1.margins(x=0.01)
    length_range = lengths_trimmed[-1] - lengths_trimmed[0] if lengths_trimmed else 0
    step = max(1, len(lengths_trimmed) // 20)
    if n_dropped > 0:
        ax1.annotate(
            f"{n_dropped} sparse length(s) hidden (< {threshold_pct}% of reads)",
            xy=(0.01, 0.97), xycoords="axes fraction",
            fontsize=8, color="gray", va="top"
        )
    if length_range <= 60:
        ax1.set_xticks(lengths_trimmed)
        ax1.set_xticklabels([str(l) for l in lengths_trimmed], rotation=45, ha="right", fontsize=7)
    else:
        tick_positions = lengths_trimmed[::step]
        ax1.set_xticks(tick_positions)
        ax1.set_xticklabels([str(l) for l in tick_positions], rotation=45, ha="right")

    # --- Plot 2: Cluster rank vs abundance ---
    ax2 = axes[1]
    ax2.plot(ranks, sizes_sorted, color="steelblue", linewidth=0.8)
    ax2.fill_between(ranks, sizes_sorted, alpha=0.3, color="steelblue")
    ax2.set_xlabel("Cluster rank")
    ax2.set_ylabel("Abundance (reads)")
    ax2.set_title("Abundance Distribution\n(rank vs size)")
    ax2.set_yscale("log")
    ax2.margins(x=0.01)

    # --- Plot 3: Length vs abundance scatter ---
    ax3 = axes[2]
    ax3.scatter(seq_lengths, sizes, alpha=0.4, s=8, color="steelblue", edgecolors="none")
    ax3.set_xlabel("Sequence length (bp)")
    ax3.set_ylabel("Abundance (reads)")
    ax3.set_title("Length vs Abundance\n(each dot = one sequence)")
    ax3.set_yscale("log")

    plt.tight_layout()
    return fig