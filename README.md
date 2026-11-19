# COBOL to Python Migration Prototype

This folder contains a file-to-file COBOL translator, its Python output example, tests, and the original [EMI COBOL sample](MONTLY%20EMI%20PROGRAM.txt). It also keeps the related [migration proposal](Legacy_Language_Migration_Hackathon_Proposal.md) and [agent document](COBOL%20Migration%20Agent.docx) alongside the code.

This first phase targets GnuCOBOL-style pure procedural/batch COBOL and intentionally excludes embedded DB2 and CICS. It is still a subset prototype, not a converter for every standard COBOL feature or dialect. The converter stops and reports source lines it cannot translate; it does not write a partial Python file in that case.

## Requirements

- Python 3.11 or newer (the workspace interpreter is Python 3.14.7)
- No third-party packages

## Translate A COBOL File

From this directory, run:

```powershell
python cobol_to_python.py "MONTLY EMI PROGRAM.txt" -o emi_translated.py
python emi_translated.py
```

For another source file, replace the input and output names:

```powershell
python cobol_to_python.py path\to\program.cbl -o path\to\program.py
```

The translated EMI program asks for customer and loan values, then prints the payment calculation and amortization schedule.

## Browser Workbench

Start the local interface from this directory:

```powershell
python app.py
```

Open `http://127.0.0.1:8000`. The workbench can load a local COBOL file, show generated Python, accept one input line per COBOL `ACCEPT`, and display the run output. It uses only the Python standard library. Execution is restricted to generated Python syntax, has a 5-second timeout, and caps displayed output.

Use **Open COBOL file** to select a local `.cbl`, `.cob`, or `.txt` program. **Load arithmetic sample** loads [SAMPLE-ARITH-LOOP.cbl](SAMPLE-ARITH-LOOP.cbl), which exercises `PERFORM VARYING`, `EVALUATE`, arithmetic, and `PIC Z,ZZZ,ZZ9.99` formatting. It should show subtotal `187.50`, discount `5.00`, and grand total `182.50`. **Load counter sample** prints 1, 2, and 3; **Load EMI sample** loads the loan-calculation example.

## Focus4 Batch Report Port

[focus4_out.cbl](focus4_out.cbl) reads an indexed COBOL `MAINFILE`. The matching native indexed data file was not available, so [focus4_report.py](focus4_report.py) is a specific Python port of its aggregation and HTML-report behavior that accepts a CSV export instead. The CSV must have `MAIN-KEY`, `AMOUNT`, and `PROD-TYPE` columns; [SAMPLE-MAINFILE.csv](SAMPLE-MAINFILE.csv) provides synthetic test records.

Run the port from this directory:

```powershell
python focus4_report.py SAMPLE-MAINFILE.csv report.html
```

This port does not convert arbitrary file-based COBOL or read the original indexed-file binary format. The general converter still reports `SELECT`, `FD`, `READ`, `WRITE`, and other unsupported source rather than claiming to translate them.

## Current Support

- Simple `01`/`05`/`77`-level `PIC` declarations, initial values, numeric versus text input, and common storage clauses (`COMP`, `COMP-3`, `BINARY`, `DISPLAY`).
- `ACCEPT`, `DISPLAY`, `MOVE`, `COMPUTE`, `ADD ... TO ...` with optional `GIVING`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, and `STOP RUN`/`GOBACK`.
- `STRING ... DELIMITED BY SPACE/SIZE INTO ... END-STRING`, including multiline statements and simple receiving-field reference modification.
- `MOVE` to `identifier(start:length)`, and `INSPECT identifier CONVERTING from TO to`.
- `IF`/`ELSE`/`END-IF`, `EVALUATE`/`WHEN`, `CONTINUE`, and `EXIT`.
- Zero-suppressed numeric display pictures in the form `Z,ZZZ,ZZ9.99`.
- Paragraph calls, `PERFORM paragraph UNTIL condition`, inline `PERFORM UNTIL`, and `PERFORM VARYING` loops.
- Common fixed-format source line prefixes and comments.

Out of scope for this phase: DB2 and CICS. Other pure COBOL features not implemented yet include file handling, `OCCURS` tables, `COPY` books, and many dialect-specific clauses. Storage clauses are recognized, but exact `PIC` display formatting, field-size limits, and COBOL rounding/truncation rules are not reproduced yet. Generated code must be reviewed and tested against the original program before being trusted.

## Tests

Run the tests from this directory:

```powershell
python -m unittest -v
```

Python 3.11 or newer is required. There are no third-party package dependencies.