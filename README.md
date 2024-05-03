# Docs-Exporter

This script automates the process of exporting Next.js documentation from the GitHub repository, converting it to HTML, and then compiling it into a PDF document. It also ensures that all visual content, including images used in the online documentation, and crucial formatting, such as code blocks and tables, are accurately fetched and included.

## Features
- **Accurate Content Replication**: Clones the Next.js documentation from the Canary channel of the GitHub repository and preserves its layout.
- **Image Handling**: Fetches and embeds the exact images used in the online documentation, ensuring that all visual explanations and illustrations are retained.
- **Advanced Formatting**: Maintains the integrity of advanced formatting elements such as code blocks, tables, and special markdown features, ensuring that the educational value of the documentation is preserved.
- **Custom PDF Styling**: Generates a styled PDF document with a cover page and a detailed table of contents, formatted through an external CSS file.


## Prerequisites

- Python
- Git
- wkhtmltopdf

## Installation
- Install `wkhtmltopdf` which is required for PDF generation. You can download it from [wkhtmltopdf downloads](https://wkhtmltopdf.org/downloads.html) and follow the installation instructions for your operating system.
- Clone the Repository
```bash
git clone https://github.com/Riyooo/Docs-Exporter.git
```
- Go into the Directory
```bash
cd Docs-Exporter
```
- Install Python Dependencies
```bash
pip install -r requirements.txt
```

## Usage

To run the script, execute the following command from the root of the repository:
```bash
python export-docs.py
```
