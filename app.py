"""Local web workbench for the COBOL-to-Python migration prototype."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from cobol_to_python import translate_cobol


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
MAX_REQUEST_BYTES = 1_000_000
MAX_SOURCE_CHARS = 100_000
MAX_INPUT_CHARS = 100_000
RUN_TIMEOUT_SECONDS = 5

ALLOWED_NODES = {
    ast.Add,
    ast.And,
    ast.Assign,
    ast.Attribute,
    ast.AugAssign,
    ast.BinOp,
    ast.BoolOp,
    ast.Call,
    ast.Compare,
    ast.Constant,
    ast.Dict,
    ast.Div,
    ast.Eq,
    ast.Expr,
    ast.For,
    ast.FunctionDef,
    ast.GeneratorExp,
    ast.Gt,
    ast.GtE,
    ast.If,
    ast.IfExp,
    ast.IsNot,
    ast.ImportFrom,
    ast.List,
    ast.Load,
    ast.Lt,
    ast.LtE,
    ast.Mod,
    ast.Mult,
    ast.Name,
    ast.Not,
    ast.NotEq,
    ast.Or,
    ast.Pow,
    ast.Pass,
    ast.Return,
    ast.Store,
    ast.Sub,
    ast.Slice,
    ast.Subscript,
    ast.Tuple,
    ast.UnaryOp,
    ast.UAdd,
    ast.USub,
    ast.While,
    ast.arguments,
    ast.arg,
    ast.alias,
    ast.comprehension,
}


class GeneratedCodeError(ValueError):
    pass


def validate_generated_python(source: str) -> None:
    if len(source) > MAX_SOURCE_CHARS:
        raise GeneratedCodeError("Python output exceeds the 100 KB execution limit.")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise GeneratedCodeError(f"Python syntax error on line {error.lineno}: {error.msg}") from error

    function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    callable_names = {"Decimal", "format", "input", "int", "len", "main", "min", "print", "str", *function_names}
    readable_names = callable_names | {
        "buffer", "delimiter", "dict", "from_chars", "fragments", "length", "limit",
        "name", "object", "part", "payload", "pointer", "remaining", "replacement",
        "result", "source_chars", "start", "start_index", "state", "target_chars",
        "text", "to_chars", "value", "width", "__name__", "None",
    }

    for node in ast.walk(tree):
        if type(node) not in ALLOWED_NODES and not isinstance(node, ast.Module):
            raise GeneratedCodeError(f"Execution is not allowed for Python syntax: {type(node).__name__}.")
        if isinstance(node, ast.ImportFrom):
            if node.module != "decimal" or {alias.name for alias in node.names} != {"Decimal"}:
                raise GeneratedCodeError("Only the generated Decimal import is allowed.")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in callable_names:
                    raise GeneratedCodeError(f"Calling {node.func.id!r} is not allowed.")
            elif (
                isinstance(node.func, ast.Attribute)
                and (
                    (
                        node.func.attr == "join"
                        and isinstance(node.func.value, ast.Constant)
                        and node.func.value.value == ""
                    )
                    or (
                        node.func.attr == "rjust"
                        and isinstance(node.func.value, ast.Call)
                        and isinstance(node.func.value.func, ast.Name)
                        and node.func.value.func.id == "format"
                    )
                    or (node.func.attr == "split" and isinstance(node.func.value, ast.Name) and node.func.value.id == "text")
                    or (node.func.attr == "translate" and isinstance(node.func.value, ast.Call) and isinstance(node.func.value.func, ast.Name) and node.func.value.func.id == "str")
                    or (node.func.attr == "maketrans" and isinstance(node.func.value, ast.Name) and node.func.value.id == "str")
                )
            ):
                pass
            else:
                raise GeneratedCodeError("Only generated COBOL-to-Python calls can be run.")
        elif isinstance(node, ast.Attribute):
            valid_join = (
                node.attr == "join"
                and isinstance(node.value, ast.Constant)
                and node.value.value == ""
            )
            valid_numeric_format = (
                node.attr == "rjust"
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "format"
            )
            valid_split = node.attr == "split" and isinstance(node.value, ast.Name) and node.value.id == "text"
            valid_translate = node.attr == "translate" and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "str"
            valid_maketrans = node.attr == "maketrans" and isinstance(node.value, ast.Name) and node.value.id == "str"
            if not (valid_join or valid_numeric_format or valid_split or valid_translate or valid_maketrans):
                raise GeneratedCodeError("Python attribute access is not allowed.")
        elif isinstance(node, ast.Name) and node.id.startswith("__") and node.id != "__name__":
            raise GeneratedCodeError("Private Python names are not allowed.")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in readable_names:
            raise GeneratedCodeError(f"Reading Python name {node.id!r} is not allowed.")


WORKER_SOURCE = '''
import ast
import json
import sys
from decimal import Decimal
from pathlib import Path

MAX_OUTPUT = 100_000
output_size = 0
inputs = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
input_index = 0

def bounded_print(*values, sep=" ", end="\\n", file=None, flush=False):
    global output_size
    if file is not None and file is not sys.stdout:
        raise ValueError("Writing to other streams is not allowed.")
    text = sep.join(str(value) for value in values) + end
    remaining = MAX_OUTPUT - output_size
    if remaining > 0:
        sys.stdout.write(text[:remaining])
        output_size += min(len(text), remaining)
    if len(text) > remaining:
        raise OutputLimitReached

class OutputLimitReached(Exception):
    pass

def read_input(prompt=None):
    global input_index
    if input_index >= len(inputs):
        raise EOFError("No more program input was provided.")
    value = inputs[input_index]
    input_index += 1
    return value

program_path = Path(sys.argv[1])
tree = ast.parse(program_path.read_text(encoding="utf-8"))
tree.body = [node for node in tree.body if not isinstance(node, ast.ImportFrom)]
namespace = {
    "__builtins__": {
        "dict": dict,
        "format": format,
        "int": int,
        "input": read_input,
        "len": len,
        "min": min,
        "object": object,
        "print": bounded_print,
        "str": str,
    },
    "__name__": "translated_program",
    "Decimal": Decimal,
}
try:
    exec(compile(tree, str(program_path), "exec"), namespace, namespace)
    namespace["main"]()
except OutputLimitReached:
    sys.stderr.write("Program output was truncated at 100 KB.\\n")
except Exception as error:
    sys.stderr.write(f"{type(error).__name__}: {error}\\n")
    sys.exit(1)
'''


class MigrationHandler(BaseHTTPRequestHandler):
    server_version = "CobolMigrationWorkbench/1.0"

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        route = parsed_url.path
        if route == "/api/sample":
            sample_name = parse_qs(parsed_url.query).get("name", ["emi"])[0]
            sample_files = {
                "emi": "MONTLY EMI PROGRAM.txt",
                "counter": "SAMPLE-COUNTER.cbl",
                "arith-loop": "SAMPLE-ARITH-LOOP.cbl",
            }
            sample_file = sample_files.get(sample_name)
            if sample_file is None:
                self._send_json(404, {"error": "Unknown COBOL sample."})
                return
            self._send_json(200, {"source": (ROOT / sample_file).read_text(encoding="utf-8")})
            return
        static_files = {
            "/": (WEB_ROOT / "index.html", "text/html; charset=utf-8"),
            "/app.css": (WEB_ROOT / "app.css", "text/css; charset=utf-8"),
            "/app.js": (WEB_ROOT / "app.js", "text/javascript; charset=utf-8"),
        }
        entry = static_files.get(route)
        if entry is None:
            self._send_json(404, {"error": "Not found."})
            return
        path, content_type = entry
        try:
            content = path.read_bytes()
        except OSError:
            self._send_json(404, {"error": "Frontend file not found."})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        try:
            request = self._read_json()
            if route == "/api/translate":
                self._translate(request)
            elif route == "/api/run":
                self._run(request)
            else:
                self._send_json(404, {"error": "Not found."})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request must contain a JSON body no larger than 1 MB.")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON request must be an object.")
        return value

    def _translate(self, request: dict[str, Any]) -> None:
        source = request.get("source")
        if not isinstance(source, str) or not source.strip():
            self._send_json(400, {"error": "Enter COBOL source code first."})
            return
        if len(source) > MAX_SOURCE_CHARS:
            self._send_json(413, {"error": "COBOL source exceeds the 100 KB limit."})
            return
        result = translate_cobol(source)
        if result.unsupported:
            self._send_json(422, {
                "error": "Some COBOL statements are not supported yet.",
                "unsupported": [{"line": item.line, "source": item.source} for item in result.unsupported],
            })
            return
        self._send_json(200, {"python": result.python_source})

    def _run(self, request: dict[str, Any]) -> None:
        source = request.get("python")
        program_input = request.get("stdin", "")
        if not isinstance(source, str) or not source.strip():
            self._send_json(400, {"error": "Translate COBOL before running Python."})
            return
        if not isinstance(program_input, str) or len(program_input) > MAX_INPUT_CHARS:
            self._send_json(400, {"error": "Program input must be text no larger than 100 KB."})
            return
        try:
            validate_generated_python(source)
        except GeneratedCodeError as error:
            self._send_json(400, {"error": str(error)})
            return

        input_lines = program_input.splitlines()
        with tempfile.TemporaryDirectory(prefix="cobol-python-run-") as temporary_directory:
            temp_path = Path(temporary_directory)
            program_path = temp_path / "translated.py"
            worker_path = temp_path / "runner.py"
            input_path = temp_path / "input.json"
            program_path.write_text(source, encoding="utf-8")
            worker_path.write_text(WORKER_SOURCE, encoding="utf-8")
            input_path.write_text(json.dumps(input_lines), encoding="utf-8")
            try:
                result = subprocess.run(
                    [sys.executable, "-I", str(worker_path), str(program_path), str(input_path)],
                    cwd=temp_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=RUN_TIMEOUT_SECONDS,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                self._send_json(408, {"error": "Program exceeded the 5 second execution limit."})
                return
        self._send_json(200, {
            "stdout": result.stdout[:MAX_SOURCE_CHARS],
            "stderr": result.stderr[:10_000],
            "exit_code": result.returncode,
            "timed_out": False,
        })

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"{self.address_string()} - {format_string % args}")


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), MigrationHandler)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the local COBOL-to-Python workbench.")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8000, help="port (default: 8000)")
    arguments = parser.parse_args()
    server = create_server(arguments.host, arguments.port)
    print(f"COBOL to Python Workbench: http://{arguments.host}:{arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping workbench.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()