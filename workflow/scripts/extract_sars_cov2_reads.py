#!/usr/bin/env python3
"""
Extract reads from EsViritu BAM file that align to a specific species.

This script:
1. Reads the EsViritu metadata table to get accessions for the target species
2. Extracts paired reads with primary alignments to those accessions from the BAM
3. Writes the reads to FASTQ files
"""

import argparse
import sys
from pathlib import Path

import polars as pl
import pysam


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract reads aligning to a specific species from EsViritu BAM"
    )
    parser.add_argument(
        "--bam",
        required=True,
        help="Input BAM file from EsViritu (e.g., sample.third.filt.sorted.bam)",
    )
    parser.add_argument(
        "--metadata",
        required=True,
        help="EsViritu metadata table (virus_pathogen_database.all_metadata.tsv)",
    )
    parser.add_argument(
        "--species",
        required=True,
        help="Species name to extract (e.g., 's__Betacoronavirus pandemicum')",
    )
    parser.add_argument(
        "--out-r1",
        required=True,
        help="Output FASTQ file for R1 reads",
    )
    parser.add_argument(
        "--out-r2",
        required=True,
        help="Output FASTQ file for R2 reads",
    )
    return parser.parse_args()


def get_target_accessions(metadata_path: str, species: str) -> set:
    """Get accessions belonging to the target species from metadata table."""
    try:
        df = pl.read_csv(metadata_path, separator="\t")
        
        # Look for species column - might be named differently
        species_col = None
        for col in df.columns:
            if "species" in col.lower():
                species_col = col
                break
        
        if species_col is None:
            print(f"[WARNING] No species column found in metadata", file=sys.stderr)
            return set()
        
        # Filter for target species
        filtered = df.filter(pl.col(species_col) == species)
        
        # Get accession column
        accession_col = None
        for col in df.columns:
            if "accession" in col.lower():
                accession_col = col
                break
        
        if accession_col is None:
            print(f"[WARNING] No accession column found in metadata", file=sys.stderr)
            return set()
        
        accessions = set(filtered[accession_col].to_list())
        print(f"[INFO] Found {len(accessions)} accessions for species '{species}'", file=sys.stderr)
        return accessions
        
    except Exception as e:
        print(f"[WARNING] Error reading metadata: {e}", file=sys.stderr)
        return set()


def extract_reads(bam_path: str, target_accessions: set, out_r1: str, out_r2: str):
    """Extract paired reads aligning to target accessions."""
    if not target_accessions:
        print("[INFO] No target accessions, creating empty output files", file=sys.stderr)
        Path(out_r1).touch()
        Path(out_r2).touch()
        return
    
    # Check if BAM file exists
    if not Path(bam_path).exists():
        print(f"[WARNING] BAM file not found: {bam_path}", file=sys.stderr)
        Path(out_r1).touch()
        Path(out_r2).touch()
        return
    
    try:
        bam = pysam.AlignmentFile(bam_path, "rb")
    except Exception as e:
        print(f"[WARNING] Error opening BAM file: {e}", file=sys.stderr)
        Path(out_r1).touch()
        Path(out_r2).touch()
        return
    
    # Get reference names that match our target accessions
    target_refs = set()
    for ref in bam.references:
        # Accession might be the full ref name or part of it
        for acc in target_accessions:
            if acc in ref or ref in acc:
                target_refs.add(ref)
                break
    
    print(f"[INFO] Found {len(target_refs)} matching references in BAM", file=sys.stderr)
    
    if not target_refs:
        print("[INFO] No matching references, creating empty output files", file=sys.stderr)
        bam.close()
        Path(out_r1).touch()
        Path(out_r2).touch()
        return
    
    # Collect reads - store by read name to pair them
    reads_r1 = {}
    reads_r2 = {}
    
    for ref in target_refs:
        try:
            for read in bam.fetch(ref):
                # Only consider primary alignments
                if read.is_secondary or read.is_supplementary:
                    continue
                
                read_name = read.query_name
                seq = read.get_forward_sequence()
                qual = pysam.qualities_to_qualitystring(read.get_forward_qualities())
                
                if seq is None or qual is None:
                    continue
                
                if read.is_read1:
                    reads_r1[read_name] = (seq, qual)
                elif read.is_read2:
                    reads_r2[read_name] = (seq, qual)
        except Exception as e:
            print(f"[WARNING] Error fetching reads from {ref}: {e}", file=sys.stderr)
            continue
    
    bam.close()
    
    # Write paired reads
    paired_count = 0
    
    # Ensure output directories exist
    Path(out_r1).parent.mkdir(parents=True, exist_ok=True)
    Path(out_r2).parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_r1, "w") as f1, open(out_r2, "w") as f2:
        for read_name in reads_r1:
            if read_name in reads_r2:
                seq1, qual1 = reads_r1[read_name]
                seq2, qual2 = reads_r2[read_name]
                
                f1.write(f"@{read_name}/1\n{seq1}\n+\n{qual1}\n")
                f2.write(f"@{read_name}/2\n{seq2}\n+\n{qual2}\n")
                paired_count += 1
    
    print(f"[INFO] Extracted {paired_count} read pairs", file=sys.stderr)


def main():
    args = parse_args()
    
    print(f"[INFO] Extracting reads for species: {args.species}", file=sys.stderr)
    
    # Get target accessions
    target_accessions = get_target_accessions(args.metadata, args.species)
    
    # Extract reads
    extract_reads(args.bam, target_accessions, args.out_r1, args.out_r2)
    
    print("[INFO] Done", file=sys.stderr)


if __name__ == "__main__":
    main()
