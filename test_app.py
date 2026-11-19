import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import create_server


class WorkbenchApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request_json(self, path: str, payload: dict[str, str] | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def test_sample_source_is_served(self) -> None:
        status, result = self.request_json("/api/sample")

        self.assertEqual(status, 200, result)
        self.assertIn("PROGRAM-ID. EMIPGM2.", result["source"])

    def test_counter_sample_translates_and_runs_without_input(self) -> None:
        status, sample = self.request_json("/api/sample?name=counter")
        self.assertEqual(status, 200, sample)
        self.assertIn("PROGRAM-ID. SAMPLE-COUNTER.", sample["source"])

        status, translated = self.request_json("/api/translate", {"source": sample["source"]})
        self.assertEqual(status, 200, translated)

        status, result = self.request_json(
            "/api/run", {"python": translated["python"], "stdin": ""}
        )

        self.assertEqual(status, 200, result)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertEqual(result["stdout"].splitlines(), ["Counting from 1 to 3:", "1", "2", "3"])

    def test_translate_and_run_emi_program(self) -> None:
        _, sample = self.request_json("/api/sample")
        status, translated = self.request_json("/api/translate", {"source": sample["source"]})
        self.assertEqual(status, 200, translated)

        inputs = "C12345\nTest User\nM\n20000101\n1234567890\nL12345\n10000\n12\n12"
        status, result = self.request_json(
            "/api/run", {"python": translated["python"], "stdin": inputs}
        )

        self.assertEqual(status, 200, result)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertIn("EMI AMOUNT TO BE PAID MONTHLY:", result["stdout"])
        self.assertIn("12 |", result["stdout"])

    def test_translate_and_run_pure_cobol_control_flow(self) -> None:
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
    PERFORM UNTIL COUNTER >= 2
        ADD 1 TO COUNTER
        DISPLAY COUNTER
    END-PERFORM.
    PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 2
        DISPLAY WS-I
    END-PERFORM.
    STOP RUN.
'''
        status, translated = self.request_json("/api/translate", {"source": source})
        self.assertEqual(status, 200, translated)

        status, result = self.request_json(
            "/api/run", {"python": translated["python"], "stdin": ""}
        )

        self.assertEqual(status, 200, (result, translated["python"]))
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertEqual(
            result["stdout"].splitlines(),
            ["START", "ZERO", "1", "2", "1", "2"],
        )

    def test_translate_and_run_comp3_and_exit(self) -> None:
        source = '''IDENTIFICATION DIVISION.
PROGRAM-ID. DECIMAL-TEST.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 WS-AMOUNT PIC S9(5)V99 COMP-3 VALUE 10.25.
01 WS-TAX PIC 9(3)V99 USAGE IS COMP-3 VALUE 1.50.
PROCEDURE DIVISION.
    COMPUTE WS-AMOUNT = WS-AMOUNT + WS-TAX
    DISPLAY WS-AMOUNT
    EXIT.
    STOP RUN.
'''
        status, translated = self.request_json("/api/translate", {"source": source})
        self.assertEqual(status, 200, translated)

        status, result = self.request_json(
            "/api/run", {"python": translated["python"], "stdin": ""}
        )

        self.assertEqual(status, 200, result)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertEqual(result["stdout"].splitlines(), ["11.75"])

    def test_continue_runs_as_generated_python_pass(self) -> None:
        source = '''IDENTIFICATION DIVISION.
PROGRAM-ID. CONTINUE-TEST.
PROCEDURE DIVISION.
    CONTINUE.
    DISPLAY "AFTER CONTINUE".
    STOP RUN.
'''
        status, translated = self.request_json("/api/translate", {"source": source})
        self.assertEqual(status, 200, translated)

        status, result = self.request_json(
            "/api/run", {"python": translated["python"], "stdin": ""}
        )

        self.assertEqual(status, 200, result)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertEqual(result["stdout"].splitlines(), ["AFTER CONTINUE"])

    def test_arith_loop_with_edited_numeric_pic_runs(self) -> None:
        _, sample = self.request_json("/api/sample?name=arith-loop")
        source = sample["source"]
        status, translated = self.request_json("/api/translate", {"source": source})
        self.assertEqual(status, 200, translated)

        status, result = self.request_json(
            "/api/run", {"python": translated["python"], "stdin": ""}
        )

        self.assertEqual(status, 200, result)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        output_lines = result["stdout"].splitlines()
        self.assertTrue(output_lines[0].endswith("187.50"), output_lines)
        self.assertTrue(output_lines[1].endswith("5.00"), output_lines)
        self.assertTrue(output_lines[2].endswith("182.50"), output_lines)

    def test_level_77_add_giving_is_input_driven(self) -> None:
        source = '''IDENTIFICATION DIVISION.
PROGRAM-ID. SIMPLE-ADD.
ENVIRONMENT DIVISION.
DATA DIVISION.
WORKING-STORAGE SECTION.
77 NUM1 PIC 9(5) VALUE 0.
77 NUM2 PIC 9(5) VALUE 0.
77 RESULT PIC 9(6) VALUE 0.
PROCEDURE DIVISION.
    DISPLAY "Enter first number: ".
    ACCEPT NUM1.
    DISPLAY "Enter second number: ".
    ACCEPT NUM2.
    ADD NUM1 TO NUM2 GIVING RESULT.
    DISPLAY "The sum of " NUM1 " and " NUM2 " is: " RESULT.
    STOP RUN.
'''
        status, translated = self.request_json("/api/translate", {"source": source})
        self.assertEqual(status, 200, translated)

        for first, second, expected in (("21", "20", "The sum of 21 and 20 is: 41"), ("7", "35", "The sum of 7 and 35 is: 42")):
            with self.subTest(first=first, second=second):
                status, result = self.request_json(
                    "/api/run",
                    {"python": translated["python"], "stdin": f"{first}\n{second}"},
                )
                self.assertEqual(status, 200, result)
                self.assertEqual(result["exit_code"], 0, result["stderr"])
                self.assertEqual(
                    result["stdout"].splitlines(),
                    ["Enter first number: ", "Enter second number: ", expected],
                )

    def test_string_reference_modification_and_inspect_convert(self) -> None:
        source = '''IDENTIFICATION DIVISION.
PROGRAM-ID. STRING-TEST.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 WS-FIRST-NAME PIC X(20).
01 WS-LAST-NAME PIC X(20).
01 WS-FULL-NAME PIC X(40).
01 WS-GREETING PIC X(80) VALUE SPACES.
01 WS-TEMP PIC X(20) VALUE 'hello world'.
PROCEDURE DIVISION.
    ACCEPT WS-FIRST-NAME.
    ACCEPT WS-LAST-NAME.
    STRING WS-FIRST-NAME DELIMITED BY SPACE
           SPACE
           WS-LAST-NAME DELIMITED BY SPACE
        INTO WS-FULL-NAME
    END-STRING.
    MOVE 'Hello, ' TO WS-GREETING(1:7).
    STRING WS-FULL-NAME DELIMITED BY SIZE
           '!' DELIMITED BY SIZE
        INTO WS-GREETING(8:60)
    END-STRING.
    INSPECT WS-TEMP CONVERTING 'abcdefghijklmnopqrstuvwxyz'
        TO 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.
    DISPLAY WS-FULL-NAME(1:12).
    DISPLAY WS-GREETING(1:20).
    DISPLAY WS-TEMP(1:11).
    STOP RUN.
'''
        status, translated = self.request_json("/api/translate", {"source": source})
        self.assertEqual(status, 200, translated)

        status, result = self.request_json(
            "/api/run", {"python": translated["python"], "stdin": "Ada\nLovelace"}
        )

        self.assertEqual(status, 200, result)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertEqual(
            [line.rstrip() for line in result["stdout"].splitlines()],
            ["Ada Lovelace", "Hello, Ada Lovelace", "HELLO WORLD"],
        )

    def test_unsupported_cobol_is_reported(self) -> None:
        source = (
            "IDENTIFICATION DIVISION.\nPROGRAM-ID. TEST.\nPROCEDURE DIVISION.\n"
            "    EXEC CICS SEND MAP('X').\n"
        )
        status, result = self.request_json("/api/translate", {"source": source})

        self.assertEqual(status, 422)
        self.assertEqual(result["unsupported"][0]["line"], 4)

    def test_arbitrary_python_is_rejected(self) -> None:
        status, result = self.request_json(
            "/api/run", {"python": "import os\n", "stdin": ""}
        )

        self.assertEqual(status, 400)
        self.assertIn("not allowed", result["error"])


if __name__ == "__main__":
    unittest.main()