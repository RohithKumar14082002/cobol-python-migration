# Hackathon Idea Submission
## Legacy Language Migration Assistant

**Proposed domain:** Application modernization
**Source languages:** SAS, FOCUS/WebFOCUS, and COBOL
**Initial demo target:** Python

### Idea

Build an assistant that helps teams understand and modernize legacy SAS, FOCUS, and COBOL programs. It analyzes source code and its dependencies, proposes a translation to a modern language, and checks the translated program against known test cases. The assistant highlights uncertain or unsupported logic so developers can review it instead of trusting an unchecked automatic rewrite.

### Problem

Many organizations rely on legacy programs that contain important business rules but are difficult to maintain or move to modern platforms. Manual migration takes time and can introduce subtle errors in calculations, data handling, and reports. Translating syntax alone is not enough; the migrated program must preserve the original behavior.

### Proposed solution

The assistant will:

- Accept a legacy source file and identify its language and relevant dependencies.
- Summarize the program's inputs, outputs, calculations, and data references.
- Generate readable target-language code for supported constructs.
- Mark unsupported or low-confidence logic for human review.
- Compare the translated program's results with known expected results and show differences.

### Hackathon requirements and scope

To keep the project achievable, the hackathon demo will support **one representative program in one source language**, translated to Python. The team can select a small FOCUS report or a self-contained COBOL batch program. SAS can be added as a separate language adapter in a later phase.

The demo requires:

- A legally usable sample program and any required metadata or supporting files.
- A small set of synthetic test inputs and reviewed expected outputs.
- Source analysis that can identify the selected subset of language constructs and their locations.
- Translation rules for that subset, with unsupported behavior clearly reported.
- A simple interface or command-line flow to analyze, translate, and view test results.
- A validation runner that executes the generated Python code and compares results.
- Human review before any generated code is treated as correct or ready to use.

### Success criteria

- Analyze and explain one representative legacy program.
- Generate target code for a clearly stated subset of its behavior.
- Run at least three test cases, including an edge case, and show pass/fail results.
- Report unsupported constructs and output differences instead of silently ignoring them.
- Demonstrate that the approach can be extended with separate SAS, FOCUS, and COBOL language adapters.

### Feasibility and future scope

The idea is feasible as a hackathon prototype when limited to one language subset and a known sample. Full migration across SAS, FOCUS, and COBOL is a larger modernization effort because each language has its own runtime, data formats, reporting behavior, and dependencies. After the hackathon, the team can expand language coverage, dependency analysis, automated test support, and review workflows.

### Data and safety requirements

Use synthetic or explicitly approved source code and data. Do not submit confidential programs or business data to an unapproved AI service. Run generated code only in a restricted environment, and treat its output as a proposal that requires developer review and testing.

### Expected impact

The prototype can reduce the effort needed to understand legacy programs, make migration assumptions visible, and give teams evidence to guide modernization. Its primary value is a safer, more reviewable migration process, not a claim of fully automatic conversion.
