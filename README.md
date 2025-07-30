# Zoolog Family Journal System

## Overview
This system compiles family journal entries into organized books in HTML, TXT, and PDF formats. The entries are categorized and compiled into both individual category books and decade-based omnibus books.

## Directory Structure
- `posts/` - Contains individual journal entries as .txt files, each with a header date line
- `monthly/` - Monthly compilation files (YYYY-MM.txt format)
- Individual category outputs: `AHNS.html`, `AHNS.pdf`, `AHNS.txt`, `J.html`, `J.pdf`, `J.txt`, `US.html`, `US.pdf`, `US.txt`
- Decade books: `book-2013-2023.pdf`, `book-2024-2034.pdf`
- Legacy combined book: `book.pdf`

## Post Categories
Posts are categorized by filename patterns:

### AHNS Category (Arlington Heights Nursery School)
- **Pattern**: Files containing "AHNS" in the filename
- **Example**: `2015-09-08-AHNS-2015-09-08.txt`
- **Note**: No new AHNS posts will be added (static collection)
- **Appears in**: AHNS.pdf, book-2013-2023.pdf only

### J Category (Uncle J)
- **Pattern**: Files containing "J" in the filename
- **Example**: `2024-01-20-J-2024-01-20.txt`
- **Date range**: 2020-present
- **Appears in**: J.pdf, decade books based on date

### US Category (Everything else)
- **Pattern**: All other files (not containing "AHNS" or "J")
- **Example**: `2023-12-12-A-2024-01-16.txt`
- **Date range**: 2013-present
- **Appears in**: US.pdf, decade books based on date

## Main Scripts

### `make_omnibus`
Primary compilation script that generates all books.

**Process**:
1. Generates decade-specific text files for 2013-2023 and 2024-2034
2. Generates combined category files
3. Processes all files through markdown→HTML→PDF pipeline
4. Combines sections with covers using pdftk
5. Runs `make_monthlies` for monthly compilations

**Output Books**:
- `book-2013-2023.pdf`: AHNS + J(2020-2023) + US(2013-2023)
- `book-2024-2034.pdf`: J(2024+) + US(2024+)
- `book.pdf`: Complete combined book

### `make_monthlies`
Generates monthly compilation files in the `monthly/` directory.

## Processing Pipeline
Each category goes through this pipeline via `process_file_type()`:

1. **Decode**: `python3 -m quopri -d` - Decode quoted-printable encoding
2. **Convert**: `pandoc -f markdown -t html` - Markdown to HTML
3. **Format**: `sed` commands - Format for table layout
4. **Style**: Combine with `pandoc.css` and process with `dow.py` (determines day of week)
5. **PDF**: `wkhtmltopdf` - Generate PDF with specific page dimensions (8"×10")

## Cover System
LaTeX-based covers for different books:

- `a_cover.tex` → `a_cover.pdf` - Main cover (title: "Outer Dibblestan")
- `a_cover-2013-2023.tex` → `a_cover-2013-2023.pdf` - "Outer Dibblestan 2013 - 2023"  
- `a_cover-2024-2034.tex` → `a_cover-2024-2034.pdf` - "Outer Dibblestan 2024 - 2034"
- `a_ahns.tex` → `a_ahns.pdf` - AHNS section divider
- `a_unclej.tex` → `a_unclej.pdf` - Uncle J section divider

**To compile covers**: Run `xelatex filename.tex` in environment with LaTeX installed.

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
To generate all books: `./make_omnibus`

This will create:
- Individual category files (AHNS.pdf, J.pdf, US.pdf)
- Decade books (book-2013-2023.pdf, book-2024-2034.pdf) 
- Combined book (book.pdf)
- Monthly compilations
- HTML and TXT versions of all categories

## Technical Notes
- Uses bash extended globbing (`shopt -s extglob`)
- Processes run in parallel using `&` and `wait`
- File patterns use `find` with `grep` filtering for reliability
- Page dimensions: 8"×10" with specific margins for printing
- CSS styling applied via `pandoc.css` and `dow.py` processing