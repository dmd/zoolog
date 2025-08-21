# Zoolog Family Journal System

## Overview
This system compiles family journal entries into organized books in HTML, TXT, and PDF formats. The entries are categorized and compiled into individual category books and separate 5-year period books for each category.

## Directory Structure
- `posts/` - Contains individual journal entries as .txt files, each with a header date line
- `covers/` - LaTeX source files and PDF covers for all books
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
1. Uses `create_period_book()` function to generate 5-year period text files:
   - US books: 2013-2017, 2018-2022, 2023-2027 (files with -A- or -D-)
   - J books: 2020-2024, 2025-2029 (files with J)
   - AHNS book: 2015-2019 (files with AHNS)
2. Generates combined category files (US.txt, J.txt, AHNS.txt)
3. Processes all files through markdown→HTML→PDF pipeline using `process_file_type()`
4. Creates separate books for each period using pdftk with year-specific covers
5. Runs `make_monthlies` for monthly compilations (only -A- and -D- files)
6. Automatically cleans up intermediate period files, keeping only combined files and final books

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
5. **PDF**: `wkhtmltopdf` - Generate PDF with specific page dimensions (8"×10")

## Cover System
LaTeX-based covers stored in `covers/` directory:

**Main covers:**
- `a_cover.tex` → `a_cover.pdf` - Generic cover (title: "Outer Dibblestan")
- `a_ahns.tex` → `a_ahns.pdf` - AHNS section divider
- `a_unclej.tex` → `a_unclej.pdf` - Uncle J section divider

**Year-specific covers:**
- `a_cover-US-2013-2017.tex` → `a_cover-US-2013-2017.pdf` - "Outer Dibblestan" with "2013 - 2017"
- `a_cover-US-2018-2022.tex` → `a_cover-US-2018-2022.pdf` - "Outer Dibblestan" with "2018 - 2022"
- `a_cover-US-2023-2027.tex` → `a_cover-US-2023-2027.pdf` - "Outer Dibblestan" with "2023 - 2027"
- `a_cover-J-2020-2024.tex` → `a_cover-J-2020-2024.pdf` - "Uncle J" with "2020 - 2024"
- `a_cover-J-2025-2029.tex` → `a_cover-J-2025-2029.pdf` - "Uncle J" with "2025 - 2029"
- `a_cover-AHNS.tex` → `a_cover-AHNS.pdf` - "AHNS" with "2015 - 2019"

**Cover format**: Large title with smaller date range below on separate line.

**To compile covers**: Run `xelatex filename.tex` in the `covers/` directory with LaTeX installed.

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
- `wkhtmltopdf` - HTML to PDF conversion
- `pdftk` - PDF concatenation
- `awk` - File aggregation
- `xelatex` - LaTeX compilation (for covers)

## Usage

### Generate all books
`./make_omnibus`

This will create:
- Individual category files (AHNS.pdf, J.pdf, US.pdf)
- US 5-year books (book-US-2013-2017.pdf, book-US-2018-2022.pdf, book-US-2023-2027.pdf)
- J 5-year books (book-J-2020-2024.pdf, book-J-2025-2029.pdf)
- AHNS single volume (book-AHNS.pdf)
- Combined book (book.pdf) - legacy
- Monthly compilations (only -A- and -D- files)
- HTML and TXT versions of all categories

### Clean all generated files
`./make_clean`

Removes all generated .txt, .html, .pdf files and directories, leaving only source files and covers.

## Technical Notes
- Uses bash extended globbing (`shopt -s extglob`) and strict error handling (`set -euo pipefail`)
- Processes run in parallel using `&` and `wait` for performance
- File filtering uses `find` with `-name` patterns and `-o` (or) logic
- Year extraction via bash parameter expansion (`${file:6:4}`) from filename format `posts/YYYY-MM-DD-...`
- Chronological order maintained through YYYY-MM-DD filename prefixes
- Page dimensions: 8"×10" with specific margins for printing
- CSS styling applied via `pandoc.css` and `dow.py` processing