import re
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from cobol_to_python import translate_cobol


class CobolToPythonTests(unittest.TestCase):
    def test_translates_hello_world(self) -> None:
        source = '''IDENTIFICATION DIVISION.
PROGRAM-ID. HELLO.
PROCEDURE DIVISION.
    DISPLAY "HELLO, WORLD!".
    STOP RUN.
'''

        translated = translate_cobol(source)

        self.assertEqual(translated.unsupported, ())
        namespace: dict[str, object] = {}
        exec(translated.python_source, namespace)
        output = StringIO()
        with redirect_stdout(output):
            namespace["main"]()
        self.assertEqual(output.getvalue(), "HELLO, WORLD!\n")

    def test_translates_and_runs_emi_sample(self) -> None:
        source_path = Path(__file__).with_name("MONTLY EMI PROGRAM.txt")
        translated = translate_cobol(source_path.read_text(encoding="utf-8"))

        self.assertEqual(translated.unsupported, ())
        namespace: dict[str, object] = {}
        exec(translated.python_source, namespace)
        output = StringIO()
        inputs = ["C12345", "Test User", "M", "20000101", "1234567890", "L12345", "10000", "12", "12"]
        with patch("builtins.input", side_effect=inputs), redirect_stdout(output):
            namespace["main"]()

        self.assertIn("EMI AMOUNT TO BE PAID MONTHLY:", output.getvalue())
        schedule_rows = [line for line in output.getvalue().splitlines() if re.match(r"^\d+ \|", line)]
        self.assertEqual(len(schedule_rows), 12)

    def test_translates_standard_cobol_control_flow(self) -> None:
        source = '''IDENTIFICATION DIVISION.
PROGRAM-ID. CONTROL-TEST.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 COUNTER PIC 9 VALUE ZERO.
01 WS-I PIC 9 VALUE ZERO.
PROCEDURE DIVISION.
    IF COUNTER = 0
        DISPLAY "START"
    ELSE
        DISPLAY "OTHER"
    END-IF.
    EVALUATE TRUE
        WHEN COUNTER = 0
            DISPLAY "ZERO"
        WHEN OTHER
            DISPLAY "NONZERO"
    END-EVALUATE.
    PERFORM UNTIL COUNTER >= 3
        ADD 1 TO COUNTER
        DISPLAY COUNTER
    END-PERFORM.
    PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 3
        DISPLAY WS-I
    END-PERFORM.
    STOP RUN.
'''

        translated = translate_cobol(source)

        self.assertEqual(translated.unsupported, ())
        namespace: dict[str, object] = {}
        exec(translated.python_source, namespace)
        output = StringIO()
        with redirect_stdout(output):
            namespace["main"]()
        self.assertEqual(
            output.getvalue().splitlines(),
            ["START", "ZERO", "1", "2", "3", "1", "2", "3"],
        )

    def test_reports_unsupported_statement(self) -> None:
        source = "IDENTIFICATION DIVISION.\nPROGRAM-ID. TEST.\nPROCEDURE DIVISION.\n    EXEC CICS SEND MAP('X').\n"
        translated = translate_cobol(source)

        self.assertEqual(len(translated.unsupported), 1)
        self.assertEqual(translated.unsupported[0].line, 4)


if __name__ == "__main__":
    unittest.main()