# Zoolog Family Journal System

## Overview
This system compiles family journal entries into organized books in HTML, TXT, and PDF formats. The entries are categorized and compiled into individual category files and decade-based books.

## Directory Structure
- `posts/` - Contains individual journal entries as .txt files, each with a header date line
- `monthly/` - Monthly compilation files (YYYY-MM.txt format)
- Individual category files: `AHNS.html`, `AHNS.pdf`, `AHNS.txt`, `J.html`, `J.pdf`, `J.txt`, `US.html`, `US.pdf`, `US.txt`
- **Decade books**: `book-2013-2019.pdf` (US + AHNS), `book-2020-YYYY.pdf` (US + J, where YYYY is current year)
- Combined book: `book.pdf` (all categories)

## Post Categories
Posts are categorized by filename patterns:

### AHNS Category (Arlington Heights Nursery School)
- **Pattern**: Files containing "AHNS" in the filename
- **Example**: `2015-09-08-AHNS-2015-09-08.txt`
- **Date range**: 2013-2019 (no new posts added)
- **Appears in**: AHNS.pdf, book-2013-2019.pdf, book.pdf

### J Category (Uncle J)
- **Pattern**: Files containing "J" in the filename
- **Example**: `2024-01-20-J-2024-01-20.txt`
- **Date range**: 2020-present
- **Appears in**: J.pdf, book-2020-YYYY.pdf, book.pdf

### US Category (Main family entries)
- **Pattern**: Files containing "-A-" or "-D-" in the filename
- **Example**: `2023-12-12-A-2024-01-16.txt`
- **Date range**: 2013-present
- **Appears in**: US.pdf, decade books based on date, book.pdf

## Main Scripts

### `make_omnibus`
Primary compilation script that generates all books.

**Process**:
1. Create build directory for intermediate files
2. Generate text files and temporary covers in build directory
3. Process files through markdown→HTML→PDF pipeline  
4. Assemble final books with pdftk
5. Generate monthly compilations
6. Move final files to main directory and clean up build directory

**Final Output Files**:
- **Decade books**: `book-2013-2019.pdf` (US + AHNS), `book-2020-YYYY.pdf` (US + J, where YYYY is current year)
- **Individual category files**: AHNS.{html,pdf,txt}, J.{html,pdf,txt}, US.{html,pdf,txt}
- **Combined book**: `book.pdf` (all categories with covers)

### `make_monthlies`
Generates monthly compilation files in the `monthly/` directory. Only processes files with `-A-` or `-D-` patterns (US category files). Uses single-pass file processing with associative arrays to group files by month.

## Processing Pipeline
Each category goes through this pipeline via `process_file_type()`:

1. **Decode**: `python3 -m quopri -d` - Decode quoted-printable encoding
2. **Convert**: `pandoc -f markdown -t html` - Markdown to HTML
3. **Format**: `sed` commands - Format for table layout
4. **Style**: Combine with `pandoc.css` and process with `dow.py` (determines day of week)
5. **PDF**: `generate_content_pdf.py` - Create PDF (8"×10")

## Cover System
Covers are generated temporarily during the build process and cleaned up automatically:

**Cover Types:**
- Generic cover (title: "Outer Dibblestan") - for combined book main section
- AHNS section divider with date range (e.g., "2013 - 2019") - for AHNS sections  
- Uncle J section divider with date range (e.g., "2020 - 2025") - for J sections
- Decade-specific main covers with date ranges - for decade books

**Cover format**: Large title with smaller date range below on separate line.

**Cover generation**: Covers are generated during build via `generate_cover.py` and automatically cleaned up.

## File Naming Convention
Posts follow the pattern: `YYYY-MM-DD-[description]-[category]-YYYY-MM-DD.txt`

Examples:
- `2023-12-12-A-2024-01-16.txt` (US category)
- `2024-01-20-J-2024-01-20.txt` (J category)  
- `2015-09-08-AHNS-2015-09-08.txt` (AHNS category)

## Dependencies
- `python3` - For quopri decoding and dow.py processing
- `pandoc` - Markdown to HTML conversion
- `sed` - Text processing  
- `sponge` - From moreutils, for in-place file editing
- `pdftk` - PDF concatenation
- `awk` - File aggregation
- `uv` - Python package manager (for WeasyPrint PDF generation)

## Usage

### Generate all books
`./make_omnibus`

Creates:
- **Decade books**: book-2013-2019.pdf (US + AHNS), book-2020-YYYY.pdf (US + J, where YYYY is current year)
- **Individual category files**: AHNS.{html,pdf,txt}, J.{html,pdf,txt}, US.{html,pdf,txt}
- **Combined book**: book.pdf (all categories with section covers)
- **Monthly compilations**: monthly/YYYY-MM.txt files (-A- and -D- files only)

### Clean all generated files
`./make_clean`

Removes all generated files and directories.

## Technical Notes
- **Build system**: Uses temporary `build/` directory for intermediate files, cleaned up automatically
- **Error handling**: Uses bash settings (`set -euo pipefail`) and extended globbing (`shopt -s extglob`)
- **Parallel processing**: Most operations run in parallel; file processing avoids command line length limits
- **File processing**: Single-pass file discovery with associative arrays to group files
- **Year extraction**: Uses bash parameter expansion to extract years from filename format `posts/YYYY-MM-DD-...`
- **Chronological order**: Maintained through YYYY-MM-DD filename prefixes and sorted processing
- **PDF generation**: Uses WeasyPrint for covers and content (8"×10" page dimensions)
- **Decade handling**: Adapts to current year for future decades without hardcoding