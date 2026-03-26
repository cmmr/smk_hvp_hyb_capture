#!/usr/bin/env python

import argparse
import os
import sys

import pysam
from subprocess import Popen, PIPE, STDOUT
import subprocess

def strobe_filt(
    reference: str, read1: str, read2: str, cpus: str
    ) -> int:

    '''
    aligns read pairs to reference with minimap2, passes it to pysam,
    then filter low quality alignments. Return total reads aligned.
    Args:
        reference: reference genome index.
        read1: fastq read file 1
        read2: fastq read file 2
        cpus: number of CPUs to use for minimap2
    Returns:
        reads_aligned_to_host
    '''
    
    strobe_command = [
        'strobealign', 
        reference, 
        read1, read2,
        '-t', cpus, 
        '--use-index',
        '-U',
        '--no-progress'
        ]

    # Launch process, to stdout and catch it with pysam
    with subprocess.Popen(
        strobe_command,
        stdout=subprocess.PIPE,
        #stderr=STDOUT
        ) as strobe_proc:

        fd_child = strobe_proc.stdout.fileno()
    
        # read minimap2 output with pysam

        with pysam.AlignmentFile(fd_child, 'r') as ministream:


            filtered_alignment_list = []
            for record in ministream:
                readLength: int = record.infer_read_length()
                alignLength: int = record.query_alignment_length

                # NM flag reports "edit distance" between read and ref
                try:
                    alignEdit: int=dict(record.get_tags(with_value_type=False)).get('NM')
                except:
                    alignEdit: int=100
                try:
                    alignProp: float=alignLength/readLength
                except:
                    alignProp: float=0
                # assume the edit distance is between aligned part of read and ref
                try:
                    alignAcc: float=(alignLength-alignEdit)/alignLength
                except:
                    alignAcc: float=0

                if alignLength >= 100 and alignProp >= 0.9 and alignAcc >= 0.8:

                    filtered_alignment_list.append(record)


    # count alignments

    reads_aligned_to_host = len(filtered_alignment_list)

    # return count of reads aligned
    return reads_aligned_to_host


def count_fastq_reads(path: str) -> int:
    """Count reads in a FASTQ file (= number of lines / 4)."""
    n = 0
    with open(path) as fh:
        for _ in fh:
            n += 1
    return n // 4


def parse_args():
    parser = argparse.ArgumentParser(
        description="Align reads to host genome and count quality-filtered alignments"
    )
    parser.add_argument("--reference", required=True, help="Host genome FASTA")
    parser.add_argument("--r1", required=True, help="Forward reads FASTQ")
    parser.add_argument("--r2", required=True, help="Reverse reads FASTQ")
    parser.add_argument("--threads", type=int, default=8, help="Threads for strobealign")
    parser.add_argument("--sample-id", required=True, help="Sample unique_id for output TSV")
    parser.add_argument("--output", required=True, help="Output TSV path")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    print(f"[INFO] Counting input reads ...", file=sys.stderr)
    total_reads = count_fastq_reads(args.r1) + count_fastq_reads(args.r2)
    print(f"[INFO] Total input reads: {total_reads}", file=sys.stderr)

    print(f"[INFO] Running strobealign + quality filter ...", file=sys.stderr)
    reads_aligned = strobe_filt(
        args.reference,
        args.r1,
        args.r2,
        str(args.threads),
    )
    print(f"[INFO] Host-aligned reads (filtered): {reads_aligned}", file=sys.stderr)

    # Write output TSV
    with open(args.output, "w") as fh:
        fh.write("unique_id\ttotal_reads\thost_aligned_reads\n")
        fh.write(f"{args.sample_id}\t{total_reads}\t{reads_aligned}\n")

    print(f"[INFO] Wrote {args.output}", file=sys.stderr)