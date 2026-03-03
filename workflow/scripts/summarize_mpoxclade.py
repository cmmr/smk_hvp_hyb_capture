#!/usr/bin/env python3
"""
Summarize mpoxclade results across all samples in a directory.

Combines all *_per_clade_summary.tsv files into a single summary table
with an added unique_id column.
"""

import argparse
import sys
from pathlib import Path

import polars as pl


def parse_args():
    parser = argparse.ArgumentParser(
        description="Summarize mpoxclade results across samples"
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing *_per_clade_summary.tsv files",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output summary TSV file",
    )
    return parser.parse_args()


def extract_unique_id(filepath: Path) -> str:
    """Extract unique_id from filename like {unique_id}_per_clade_summary.tsv."""
    return filepath.name.replace("_per_clade_summary.tsv", "")


def main():
    args = parse_args()
    
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    
    # Find all per-sample summary files (recursive search)
    summary_files = list(input_dir.glob("**/*_per_clade_summary.tsv"))
    
    if not summary_files:
        print(f"[WARNING] No *_per_clade_summary.tsv files found in {input_dir}", file=sys.stderr)
        # Create empty output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
        return
    
    print(f"[INFO] Found {len(summary_files)} summary files", file=sys.stderr)
    
    dfs = []
    for filepath in sorted(summary_files):
        unique_id = extract_unique_id(filepath)
        
        try:
            # Read the summary file
            df = pl.read_csv(filepath, separator="\t")
            
            # Skip empty files
            if df.height == 0:
                print(f"[INFO] Skipping empty file: {filepath.name}", file=sys.stderr)
                continue
            
            # Add unique_id as first column
            df = df.with_columns(pl.lit(unique_id).alias("unique_id"))
            
            # Reorder to put unique_id first
            cols = ["unique_id"] + [c for c in df.columns if c != "unique_id"]
            df = df.select(cols)
            
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
