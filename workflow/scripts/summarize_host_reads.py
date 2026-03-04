#!/usr/bin/env python3
"""
Summarize host read counts across all samples in a directory.

Combines all *_host_read_counts.tsv files into a single summary table.
"""

import argparse
import sys
from pathlib import Path

import polars as pl


def parse_args():
    parser = argparse.ArgumentParser(
        description="Summarize host read counts across samples"
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing *_host_read_counts.tsv files",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output summary TSV file",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    
    # Find all per-sample host read count files (recursive search)
    count_files = list(input_dir.glob("**/*_host_read_counts.tsv"))
    
    if not count_files:
        print(f"[WARNING] No *_host_read_counts.tsv files found in {input_dir}", file=sys.stderr)
        # Create empty output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
        return
    
    print(f"[INFO] Found {len(count_files)} host read count files", file=sys.stderr)
    
    dfs = []
    for filepath in sorted(count_files):
        try:
            df = pl.read_csv(filepath, separator="\t")
            
            if df.height == 0:
                print(f"[INFO] Skipping empty file: {filepath.name}", file=sys.stderr)
                continue
            
            dfs.append(df)
            
        except Exception as e:
            print(f"[WARNING] Error reading {filepath.name}: {e}", file=sys.stderr)
            continue
    
    if not dfs:
        print("[WARNING] No valid data found, creating empty output", file=sys.stderr)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
        return
    
    # Concatenate all dataframes
    combined = pl.concat(dfs, how="diagonal")
    
    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.write_csv(output_path, separator="\t")
    
    print(f"[INFO] Wrote {combined.height} rows to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
