# Zoolog Family Journal System

## Overview
This system compiles family journal entries into organized books in HTML, TXT, and PDF formats. The entries are categorized and compiled into individual category books and separate 5-year period books for each category.

## Directory Structure
- `posts/` - Contains individual journal entries as .txt files, each with a header date line
- `covers/` - PDF covers for all books
- `monthly/` - Monthly compilation files (YYYY-MM.txt format)
- Individual category outputs: `AHNS.html`, `AHNS.pdf`, `AHNS.txt`, `J.html`, `J.pdf`, `J.txt`, `US.html`, `US.pdf`, `US.txt`
- US 5-year books: `book-US-2013-2017.pdf`, `book-US-2018-2022.pdf`, `book-US-2023-2027.pdf`
- J 5-year books: `book-J-2020-2024.pdf`, `book-J-2025-2029.pdf`
- AHNS single volume: `book-AHNS.pdf`
- Legacy combined book: `book.pdf`

## Post Categories
Posts are categorized by filename patterns:

### AHNS Category (Arlington Heights Nursery School)
- **Pattern**: Files containing "AHNS" in the filename
- **Example**: `2015-09-08-AHNS-2015-09-08.txt`
- **Note**: No new AHNS posts will be added (static collection)
- **Appears in**: AHNS.pdf, book-AHNS.pdf only

### J Category (Uncle J)
- **Pattern**: Files containing "J" in the filename
- **Example**: `2024-01-20-J-2024-01-20.txt`
- **Date range**: 2020-present
- **Appears in**: J.pdf, 5-year J books based on date

### US Category (Main family entries)
- **Pattern**: Files containing "-A-" or "-D-" in the filename
- **Example**: `2023-12-12-A-2024-01-16.txt`
- **Date range**: 2013-present
- **Appears in**: US.pdf, 5-year US books based on date

## Main Scripts

### `make_omnibus`
Primary compilation script that generates all books.

**Process**:
1. Generate text files and covers
2. Process files through markdown→HTML→PDF pipeline  
3. Assemble final books with pdftk
4. Generate monthly compilations
5. Clean up intermediate files

**Output Books**:
- US 5-year books: `book-US-2013-2017.pdf`, `book-US-2018-2022.pdf`, `book-US-2023-2027.pdf`
- J 5-year books: `book-J-2020-2024.pdf`, `book-J-2025-2029.pdf`
- AHNS single volume: `book-AHNS.pdf`
- `book.pdf`: Complete combined book (legacy)

### `make_monthlies`
Generates monthly compilation files in the `monthly/` directory. Only processes files with `-A-` or `-D-` patterns (US category files).

## Processing Pipeline
Each category goes through this pipeline via `process_file_type()`:

1. **Decode**: `python3 -m quopri -d` - Decode quoted-printable encoding
2. **Convert**: `pandoc -f markdown -t html` - Markdown to HTML
3. **Format**: `sed` commands - Format for table layout
4. **Style**: Combine with `pandoc.css` and process with `dow.py` (determines day of week)
5. **PDF**: `generate_content_pdf.py` - Create PDF (8"×10")

## Cover System
Generated covers stored in `covers/` directory:

**Main covers:**
- `a_cover.pdf` - Generic cover (title: "Outer Dibblestan")
- `a_ahns.pdf` - AHNS section divider
- `a_unclej.pdf` - Uncle J section divider

**Year-specific covers:**
- `a_cover-US-2013-2017.pdf` - "Outer Dibblestan" with "2013 - 2017"
- `a_cover-US-2018-2022.pdf` - "Outer Dibblestan" with "2018 - 2022"
- `a_cover-US-2023-2027.pdf` - "Outer Dibblestan" with "2023 - 2027"
- `a_cover-J-2020-2024.pdf` - "Uncle J" with "2020 - 2024"
- `a_cover-J-2025-2029.pdf` - "Uncle J" with "2025 - 2029"
- `a_cover-AHNS.pdf` - "AHNS" with "2015 - 2019"

**Cover format**: Large title with smaller date range below on separate line.

**Cover generation**: Covers are generated during build via `generate_cover.py`.

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
- Individual category files (AHNS.pdf, J.pdf, US.pdf)
- US 5-year books (book-US-2013-2017.pdf, book-US-2018-2022.pdf, book-US-2023-2027.pdf)
- J 5-year books (book-J-2020-2024.pdf, book-J-2025-2029.pdf)
- AHNS single volume (book-AHNS.pdf)
- Combined book (book.pdf)
- Covers
- Monthly compilations (-A- and -D- files only)
- HTML and TXT versions

### Clean all generated files
`./make_clean`

Removes all generated files and directories, including covers.

## Technical Notes
- Uses bash extended globbing (`shopt -s extglob`) and strict error handling (`set -euo pipefail`)
- Most operations run in parallel for speed
- File filtering uses `find` with `-name` patterns and `-o` (or) logic
- Year extraction via bash parameter expansion (`${file:6:4}`) from filename format `posts/YYYY-MM-DD-...`
- Chronological order maintained through YYYY-MM-DD filename prefixes
- Page dimensions: 8"×10" with margins for printing
- Uses WeasyPrint for PDF generation (covers and content)
- CSS styling applied via `pandoc.css` and `dow.py` processing