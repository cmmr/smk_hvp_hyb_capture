# Goal
Make a snakemake pipeline to decompress hybrid capture virome sequencing reads from a sample sheet, run EsViritu, and quantify host reads.

## Design notes
- use snakemake best practices
	- See this repo for style guide: notes/style/StainedGlass
- this will be run on an HPC with SLURM job scheduling
	- use the conventions in the repo: notes/style/smk-simple-slurm
		- especially note this config: notes/style/smk-simple-slurm/simple/config.v8+.yaml

## Pipeline inputs
- sample sheet
	- required fields
		- Sample_ID
		- path to forward read file (compressed)
		- path to reverse  read file (compressed)
		- compression type
		- category (sample or control)
- config file arguments
	- PoolID
	- host_genome path

# Modules

## Preprocessing
### Decompressing files
- inputs
	- sample sheet
- config
	- temp directory
	- threads: 8
	- memory 8g
	- conda env: preprocess
- actions
	- read sample sheet
		- determine if reads are compressed in .gz or .bz2 format
		- merge sample_ID and PoolID strings to generate unique_ID
	- use `pigz` (multithread) or `pbzip2` to uncompress reads to temp directory
- outputs
	- uncompressed read files path (tempfile)
	- example output path: r1=str(TEMP_ROOT / "{category}" / "01_decompress" / "{unique_id}.R1.fastq")

### Quality filter reads
- inputs
	- uncompressed read files path
- config
	- temp directory
	- threads: 16
	- memory 16g
	- conda env: preprocess
- actions
	- use `fastp` with default settings to quality filter reads
- outputs
	- quality filtered read files path (tempfile)

### Remove reads aligning to vector sequences
- inputs
	- quality filtered read files path
- config
	- temp directory
	- samples output directory
	- controls output directory
	- threads: 8
	- memory 8g
	- conda env: preprocess
- actions
	- use `vrr` (from vector_read_removal repo) with `--nm-threshold 4`
- outputs
	- vector-removed read files path (tempfile)

## Virome analysis

### EsViritu
- inputs
	- vector-removed read files path (tempfile)
- config
	- esviritu DB path
	- threads: 8
	- memory 8g
	- conda env: esviritu
- actions
	- use `EsViritu` (from https://github.com/cmmr/EsViritu) with  `-q F --keep T` flags
- outputs
	- {unique_ID}.detected_virus.info.tsv
	- {unique_ID}.detected_virus.assembly_summary.tsv
	- {unique_ID}.tax_profile.tsv
	- {unique_ID}.virus_coverage_windows.tsv
	- example output path: str(ESVIRITU_ROOT / "{category}" / "esviritu_{PoolID}" / "{unique_id}.{extension}")

### Summarize EsViritu
- inputs
	- all per-sample EsViritu info.tsv files for a category
- actions
	- use `summarize_esv_runs` to concatenate results
- outputs
	- esviritu_{PoolID}.detected_virus.info.tsv (per category)

## Host read quantification

### Calculate host reads
- inputs
	- vector-removed read files path (tempfile)
- config
	- host genome path
	- threads: 8
	- memory 8g
	- conda env: preprocess
- actions
	- count total input reads (R1 + R2)
	- align to host genome with `minimap2 -a -x sr` piped to `samtools view -F 4 -c`
	- no BAM or alignment files saved (pipe only)
- outputs
	- {unique_ID}_host_read_counts.tsv (columns: unique_id, total_reads, host_aligned_reads)

### Summarize host reads
- inputs
	- all per-sample host_read_counts.tsv files for a category
- actions
	- python script concatenates into one TSV
- outputs
	- host_reads_summary.tsv (per category)