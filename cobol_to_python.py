"""Translate a deliberately small, reviewable subset of COBOL into Python."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


IDENTIFIER = r"[A-Z][A-Z0-9-]*"
COBOL_VERBS = {
    "ACCEPT",
    "ADD",
    "CALL",
    "COMPUTE",
    "CONTINUE",
    "DISPLAY",
    "DIVIDE",
    "ELSE",
    "EVALUATE",
    "EXIT",
    "GOBACK",
    "IF",
    "INITIALIZE",
    "INSPECT",
    "MOVE",
    "MULTIPLY",
    "PERFORM",
    "READ",
    "SET",
    "STOP",
    "STRING",
    "SUBTRACT",
    "WHEN",
    "WRITE",
}
DATA_ITEM = re.compile(
    rf"^\s*(?:\d{{2}}|77)\s+({IDENTIFIER})\s+PIC\s+([A-Z0-9()VXS+,*\-]+(?:\.[A-Z0-9()VXS+,*\-]+)?)"
    rf"(?:\s+(?:USAGE\s+(?:IS\s+)?)?(?:COMP(?:-[345])?|BINARY|DISPLAY|PACKED-DECIMAL))?"
    rf"(?:\s+SIGN\s+IS\s+(?:LEADING|TRAILING)(?:\s+SEPARATE)?)?"
    rf"(?:\s+VALUE\s+(.+?))?\.?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class UnsupportedStatement:
    line: int
    source: str


@dataclass(frozen=True)
class Translation:
    python_source: str
    unsupported: tuple[UnsupportedStatement, ...]


def _source_lines(source: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        if len(raw_line) > 6 and raw_line[:6].strip().isdigit():
            raw_line = raw_line[7:]
        elif len(raw_line) > 7 and not raw_line[:6].strip() and raw_line[6] in " */-":
            if raw_line[6] in "*/":
                continue
            raw_line = raw_line[7:]
        line = raw_line.strip()
        if line:
            lines.append((line_number, line))
    return _combine_multiline_statements(lines)


def _combine_multiline_statements(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    combined: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        line_number, line = lines[index]
        upper_line = line.upper()
        if re.match(r"STRING\b", upper_line):
            parts = [line]
            index += 1
            while index < len(lines):
                parts.append(lines[index][1])
                if re.search(r"\bEND-STRING\b", lines[index][1], re.IGNORECASE):
                    break
                index += 1
            combined.append((line_number, " ".join(parts)))
            index += 1
            continue

        if "INSPECT" in upper_line and "CONVERTING" in upper_line and not re.search(
            r"\bTO\s+", line, re.IGNORECASE
        ):
            parts = [line]
            index += 1
            if index < len(lines) and re.match(r"\s*TO\s+", lines[index][1], re.IGNORECASE):
                parts.append(lines[index][1])
                index += 1
            combined.append((line_number, " ".join(parts)))
            continue

        combined.append((line_number, line))
        index += 1
    return combined


def _picture_length(picture: str) -> int:
    length = 0
    for symbol, repeat in re.findall(r"([AX9Z*0-9$,+.\-V])(?:\((\d+)\))?", picture.upper()):
        if symbol != "V":
            length += int(repeat or 1)
    return length


def _field_reference(name: str, start: str | None, length: str | None, declared_fields: set[str]) -> str:
    normalized_name = name.upper()
    if normalized_name not in declared_fields:
        raise ValueError(f"undeclared data item {normalized_name}")
    if start is None:
        return f"state[{normalized_name!r}]"
    first = int(start) - 1
    last = first + int(length) if length is not None else ""
    return f"state[{normalized_name!r}][{first}:{last}]"


def _literal(value: str, numeric: bool) -> str:
    value = value.strip().rstrip(".")
    upper_value = value.upper()
    if upper_value in {"ZERO", "ZEROS", "ZEROES"}:
        return "Decimal('0')" if numeric else "'0'"
    if upper_value in {"SPACE", "SPACES"}:
        return "''"
    if upper_value in {"LOW-VALUE", "LOW-VALUES"}:
        return "''"
    if value.startswith("'") and value.endswith("'"):
        return repr(value[1:-1].replace("''", "'"))
    if value.startswith('"') and value.endswith('"'):
        return repr(value[1:-1].replace('""', '"'))
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        return f"Decimal({value!r})" if numeric else repr(value)
    if re.fullmatch(IDENTIFIER, value, re.IGNORECASE):
        return f"state[{value.upper()!r}]"
    raise ValueError(f"unsupported value: {value}")


def _expression(expression: str, declared_fields: set[str]) -> str:
    expression = expression.rstrip(".").strip()
    expression = re.sub(r"\bNOT\s*=", "!=", expression, flags=re.IGNORECASE)
    expression = re.sub(r"(?<![<>=!])=(?!=)", "==", expression)
    expression = re.sub(r"\bAND\b", "and", expression, flags=re.IGNORECASE)
    expression = re.sub(r"\bOR\b", "or", expression, flags=re.IGNORECASE)

    def replace_reference_modification(match: re.Match[str]) -> str:
        return _field_reference(match.group(1), match.group(2), match.group(3), declared_fields)

    expression = re.sub(
        rf"\b({IDENTIFIER})\s*\(\s*(\d+)\s*:\s*(\d+)\s*\)",
        replace_reference_modification,
        expression,
        flags=re.IGNORECASE,
    )

    def replace_identifier(match: re.Match[str]) -> str:
        name = match.group(0)
        if name.upper() == "TRUE":
            return "True"
        if name.upper() == "FALSE":
            return "False"
        if name.upper() in {"AND", "OR", "NOT"}:
            return name.lower()
        if name.upper() not in declared_fields:
            raise ValueError(f"undeclared data item {name.upper()}")
        return f"state[{name.upper()!r}]"

    expression = re.sub(rf"\b{IDENTIFIER}\b", replace_identifier, expression, flags=re.IGNORECASE)
    expression = re.sub(r"(?<![\w.])\d+\.\d+(?!\w)", lambda m: f"Decimal({m.group(0)!r})", expression)
    return expression


def _translate_display(
    operand_text: str,
    line_number: int,
    declared_fields: set[str],
    edited_pics: dict[str, str],
) -> str:
    tokens = re.findall(
        rf"'[^']*(?:''[^']*)*'|\"[^\"]*(?:\"\"[^\"]*)*\"|{IDENTIFIER}\s*\(\s*\d+\s*:\s*\d+\s*\)|{IDENTIFIER}|-?\d+(?:\.\d+)?",
        operand_text,
        re.IGNORECASE,
    )
    if not tokens:
        raise ValueError(f"line {line_number}: DISPLAY has no supported operands")
    parts = []
    for token in tokens:
        reference_match = re.fullmatch(rf"({IDENTIFIER})\s*\(\s*(\d+)\s*:\s*(\d+)\s*\)", token, re.IGNORECASE)
        if reference_match:
            field_name, start, length = reference_match.groups()
            parts.append(_field_reference(field_name, start, length, declared_fields))
            continue
        field_name = token.upper()
        if re.fullmatch(IDENTIFIER, token, re.IGNORECASE) and field_name not in declared_fields:
            raise ValueError(f"undeclared data item {field_name}")
        picture = edited_pics.get(field_name)
        if picture:
            match = re.fullmatch(r"([Z9,]+)\.([9]+)", picture)
            if not match:
                raise ValueError(f"unsupported edited numeric PIC {picture} for {field_name}")
            integer_picture, decimal_picture = match.groups()
            grouping = "," if "," in integer_picture else ""
            format_spec = f"{grouping}.{len(decimal_picture)}f"
            parts.append(
                f"format(state[{field_name!r}], {format_spec!r}).rjust({len(picture)})"
            )
        else:
            parts.append(_literal(token, numeric=False))
    return "print(''.join(str(part) for part in [" + ", ".join(parts) + "]))"


def _python_paragraph_name(name: str) -> str:
    return "_perform_" + name.lower().replace("-", "_")


def _string_source_tokens(source_text: str, declared_fields: set[str]) -> list[tuple[str, str | None]]:
    token_pattern = re.compile(
        r"'[^']*(?:''[^']*)*'|\"[^\"]*(?:\"\"[^\"]*)*\"|[A-Z][A-Z0-9-]*|\d+(?:\.\d+)?",
        re.IGNORECASE,
    )
    tokens = token_pattern.findall(source_text)
    sources: list[tuple[str, str | None]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        upper_token = token.upper()
        if upper_token in {"DELIMITED", "BY", "SIZE"}:
            raise ValueError(f"unexpected STRING token {token}")
        if upper_token in {"SPACE", "SPACES"}:
            value = repr(" ")
        else:
            if re.fullmatch(IDENTIFIER, token, re.IGNORECASE) and token.upper() not in declared_fields:
                raise ValueError(f"undeclared data item {token.upper()}")
            value = _literal(token, False)
        delimiter: str | None = None
        index += 1
        if index < len(tokens) and tokens[index].upper() == "DELIMITED":
            if index + 2 >= len(tokens) or tokens[index + 1].upper() != "BY":
                raise ValueError("STRING DELIMITED phrase must include BY and a delimiter")
            delimiter_token = tokens[index + 2]
            if delimiter_token.upper() == "SIZE":
                delimiter = None
            elif delimiter_token.upper() in {"SPACE", "SPACES"}:
                delimiter = repr(" ")
            else:
                delimiter = _literal(delimiter_token, False)
            index += 3
        sources.append((value, delimiter))
    return sources


def _translate_string(statement: str, declared_fields: set[str], pic_lengths: dict[str, int]) -> str:
    match = re.fullmatch(
        rf"STRING\s+(.+?)\s+INTO\s+({IDENTIFIER})(?:\s*\(\s*(\d+)\s*:\s*(\d+)\s*\))?(?:\s+WITH\s+POINTER\s+({IDENTIFIER}))?\s+END-STRING",
        statement.strip().rstrip("."),
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("unsupported STRING form")
    source_text, receiver, start, length, pointer = match.groups()
    receiver = receiver.upper()
    if receiver not in declared_fields:
        raise ValueError(f"undeclared data item {receiver}")
    if receiver not in pic_lengths:
        raise ValueError(f"STRING receiver {receiver} has no supported PIC length")
    if pointer and pointer.upper() not in declared_fields:
        raise ValueError(f"undeclared pointer data item {pointer.upper()}")
    sources = _string_source_tokens(source_text, declared_fields)
    source_list = "[" + ", ".join(
        f"({value}, {delimiter if delimiter is not None else 'None'})" for value, delimiter in sources
    ) + "]"
    start_value = start or "1"
    length_value = length or "None"
    pointer_value = repr(pointer.upper()) if pointer else "None"
    return (
        f"_cobol_string(state, {receiver!r}, {source_list}, {pic_lengths[receiver]}, "
        f"{start_value}, {length_value}, {pointer_value})"
    )


def _translate_inspect(statement: str, declared_fields: set[str]) -> str:
    match = re.fullmatch(
        rf"INSPECT\s+({IDENTIFIER})\s+CONVERTING\s+(.+?)\s+TO\s+(.+)",
        statement.strip().rstrip("."),
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("unsupported INSPECT form")
    name, from_value, to_value = match.groups()
    name = name.upper()
    if name not in declared_fields:
        raise ValueError(f"undeclared data item {name}")
    return (
        f"state[{name!r}] = _inspect_convert(state[{name!r}], "
        f"{_literal(from_value, False)}, {_literal(to_value, False)})"
    )


def _translate_statements(
    statements: list[tuple[int, str]],
    numeric_fields: set[str],
    declared_fields: set[str],
    paragraph_names: set[str],
    edited_pics: dict[str, str],
    pic_lengths: dict[str, int],
) -> tuple[list[str], list[UnsupportedStatement]]:
    body: list[str] = []
    unsupported: list[UnsupportedStatement] = []
    blocks: list[dict[str, object]] = []
    indent = 0

    def emit(statement: str, at_indent: int | None = None) -> None:
        level = indent if at_indent is None else at_indent
        body.append("    " + "    " * level + statement)

    def ensure_branch_body(block: dict[str, object]) -> None:
        if len(body) == block["branch_start"]:
            emit("pass", int(block["branch_indent"]) + 1)

    for line_number, raw_statement in statements:
        statement = raw_statement.strip().rstrip(".").strip()
        upper_statement = statement.upper()
        try:
            match = re.fullmatch(r"IF\s+(.+)", statement, re.IGNORECASE)
            if match:
                emit(f"if {_expression(match.group(1), declared_fields)}:")
                blocks.append({"kind": "IF", "line": line_number, "branch_indent": indent, "branch_start": len(body)})
                indent += 1
                continue

            if upper_statement == "ELSE":
                if not blocks or blocks[-1]["kind"] != "IF" or blocks[-1].get("has_else"):
                    raise ValueError("ELSE without a matching IF, or duplicate ELSE")
                block = blocks[-1]
                ensure_branch_body(block)
                indent = int(block["branch_indent"])
                emit("else:")
                indent += 1
                block["has_else"] = True
                block["branch_start"] = len(body)
                continue

            match = re.fullmatch(r"EVALUATE\s+(.+)", statement, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                evaluate_true = target.upper() == "TRUE"
                target_expression = "True" if evaluate_true else _expression(target, declared_fields)
                blocks.append({
                    "kind": "EVALUATE",
                    "line": line_number,
                    "branch_indent": indent,
                    "branch_start": len(body),
                    "target": target_expression,
                    "evaluate_true": evaluate_true,
                    "has_branch": False,
                    "has_other": False,
                })
                continue

            match = re.fullmatch(r"WHEN\s+(.+)", statement, re.IGNORECASE)
            if match:
                if not blocks or blocks[-1]["kind"] != "EVALUATE":
                    raise ValueError("WHEN without a matching EVALUATE")
                block = blocks[-1]
                if block.get("has_branch"):
                    ensure_branch_body(block)
                indent = int(block["branch_indent"])
                value = match.group(1).strip()
                if value.upper() == "OTHER":
                    if block.get("has_other"):
                        raise ValueError("duplicate WHEN OTHER")
                    emit("else:")
                    block["has_other"] = True
                else:
                    if block.get("has_other"):
                        raise ValueError("WHEN cannot follow WHEN OTHER")
                    if block["evaluate_true"]:
                        condition = _expression(value, declared_fields)
                    else:
                        target_expression = str(block["target"])
                        condition = f"{target_expression} == {_literal(value, True)}"
                    keyword = "elif" if block.get("has_branch") else "if"
                    emit(f"{keyword} {condition}:")
                indent += 1
                block["has_branch"] = True
                block["branch_start"] = len(body)
                continue

            if upper_statement in {"END-IF", "END-EVALUATE", "END-PERFORM"}:
                expected = upper_statement.removeprefix("END-")
                if not blocks or blocks[-1]["kind"] != expected:
                    raise ValueError(f"{upper_statement} without a matching {expected}")
                block = blocks.pop()
                if block["kind"] == "EVALUATE" and not block.get("has_branch"):
                    unsupported.append(UnsupportedStatement(line_number, "EVALUATE without WHEN"))
                elif block["kind"] == "EVALUATE" or block["kind"] == "IF":
                    ensure_branch_body(block)
                elif block["kind"] == "PERFORM" and block.get("varying_target"):
                    emit(
                        f"state[{block['varying_target']!r}] += {block['varying_step']}",
                        int(block["branch_indent"]) + 1,
                    )
                elif len(body) == block["branch_start"]:
                    emit("pass", int(block["branch_indent"]) + 1)
                indent = int(block["branch_indent"])
                continue

            match = re.fullmatch(
                rf"PERFORM\s+VARYING\s+({IDENTIFIER})\s+FROM\s+(.+?)\s+BY\s+(.+?)\s+UNTIL\s+(.+)",
                statement,
                re.IGNORECASE,
            )
            if match:
                name, start_value, step_value, condition = match.groups()
                name = name.upper()
                if name not in declared_fields:
                    raise ValueError(f"undeclared data item {name}")
                emit(f"state[{name!r}] = {_literal(start_value, name in numeric_fields)}")
                emit(f"while not ({_expression(condition, declared_fields)}):")
                blocks.append({
                    "kind": "PERFORM",
                    "line": line_number,
                    "branch_indent": indent,
                    "branch_start": len(body) + 1,
                    "varying_target": name,
                    "varying_step": _expression(step_value, declared_fields),
                })
                indent += 1
                continue

            match = re.fullmatch(r"PERFORM\s+UNTIL\s+(.+)", statement, re.IGNORECASE)
            if match:
                emit(f"while not ({_expression(match.group(1), declared_fields)}):")
                blocks.append({"kind": "PERFORM", "line": line_number, "branch_indent": indent, "branch_start": len(body)})
                indent += 1
                continue

            if upper_statement.startswith("END PROGRAM"):
                continue
            if upper_statement in {"STOP RUN", "GOBACK"}:
                emit("return")
                continue
            if upper_statement in {"CONTINUE", "EXIT"}:
                emit("pass")
                continue

            match = re.fullmatch(
                rf"PERFORM\s+({IDENTIFIER})\s+UNTIL\s+(.+)", statement, re.IGNORECASE
            )
            if match:
                name, condition = match.groups()
                name = name.upper()
                if name not in paragraph_names:
                    raise ValueError(f"unknown paragraph {name}")
                emit(f"while not ({_expression(condition, declared_fields)}):")
                emit(f"{_python_paragraph_name(name)}(state)", indent + 1)
                continue

            match = re.fullmatch(rf"PERFORM\s+({IDENTIFIER})", statement, re.IGNORECASE)
            if match:
                name = match.group(1).upper()
                if name not in paragraph_names:
                    raise ValueError(f"unknown paragraph {name}")
                emit(f"{_python_paragraph_name(name)}(state)")
                continue

            match = re.fullmatch(
                rf"ADD\s+(.+?)\s+TO\s+({IDENTIFIER})(?:\s+GIVING\s+({IDENTIFIER}))?",
                statement,
                re.IGNORECASE,
            )
            if match:
                values, name, giving_name = match.groups()
                name = name.upper()
                if name not in declared_fields:
                    raise ValueError(f"undeclared data item {name}")
                terms = [_expression(value, declared_fields) for value in re.split(r"\s+", values)]
                if giving_name:
                    giving_name = giving_name.upper()
                    if giving_name not in declared_fields:
                        raise ValueError(f"undeclared data item {giving_name}")
                    emit(
                        f"state[{giving_name!r}] = state[{name!r}] + {' + '.join(terms)}"
                    )
                else:
                    emit(f"state[{name!r}] += {' + '.join(terms)}")
                continue

            match = re.fullmatch(rf"SUBTRACT\s+(.+?)\s+FROM\s+({IDENTIFIER})", statement, re.IGNORECASE)
            if match:
                value, name = match.groups()
                name = name.upper()
                if name not in declared_fields:
                    raise ValueError(f"undeclared data item {name}")
                emit(f"state[{name!r}] -= {_expression(value, declared_fields)}")
                continue

            match = re.fullmatch(rf"MULTIPLY\s+(.+?)\s+BY\s+({IDENTIFIER})", statement, re.IGNORECASE)
            if match:
                value, name = match.groups()
                name = name.upper()
                if name not in declared_fields:
                    raise ValueError(f"undeclared data item {name}")
                emit(f"state[{name!r}] *= {_expression(value, declared_fields)}")
                continue

            match = re.fullmatch(rf"DIVIDE\s+(.+?)\s+INTO\s+({IDENTIFIER})", statement, re.IGNORECASE)
            if match:
                value, name = match.groups()
                name = name.upper()
                if name not in declared_fields:
                    raise ValueError(f"undeclared data item {name}")
                emit(f"state[{name!r}] /= {_expression(value, declared_fields)}")
                continue

            match = re.fullmatch(rf"ACCEPT\s+({IDENTIFIER})", statement, re.IGNORECASE)
            if match:
                name = match.group(1).upper()
                if name not in declared_fields:
                    raise ValueError(f"undeclared data item {name}")
                conversion = (
                    "Decimal(input())"
                    if name in numeric_fields
                    else f"_cobol_text(input(), {pic_lengths.get(name, 0)})"
                )
                emit(f"state[{name!r}] = {conversion}")
                continue

            match = re.fullmatch(r"DISPLAY\s+(.+)", statement, re.IGNORECASE)
            if match:
                emit(_translate_display(match.group(1), line_number, declared_fields, edited_pics))
                continue

            if upper_statement.startswith("STRING "):
                emit(_translate_string(statement, declared_fields, pic_lengths))
                continue

            if upper_statement.startswith("INSPECT "):
                emit(_translate_inspect(statement, declared_fields))
                continue

            match = re.fullmatch(
                rf"MOVE\s+(.+?)\s+TO\s+({IDENTIFIER})(?:\s*\(\s*(\d+)\s*:\s*(\d+)\s*\))?",
                statement,
                re.IGNORECASE,
            )
            if match:
                value, name, start, ref_length = match.groups()
                name = name.upper()
                if name not in declared_fields:
                    raise ValueError(f"undeclared data item {name}")
                value_expression = _literal(value, name in numeric_fields)
                if start is not None:
                    if name not in pic_lengths:
                        raise ValueError(f"reference-modified item {name} has no supported PIC length")
                    emit(
                        f"_cobol_refmod(state, {name!r}, {start}, {ref_length}, "
                        f"{value_expression}, {pic_lengths[name]})"
                    )
                elif name in numeric_fields:
                    emit(f"state[{name!r}] = {value_expression}")
                else:
                    emit(f"state[{name!r}] = _cobol_text({value_expression}, {pic_lengths.get(name, 0)})")
                continue

            match = re.fullmatch(rf"COMPUTE\s+({IDENTIFIER})\s*=\s*(.+)", statement, re.IGNORECASE)
            if match:
                name, expression = match.groups()
                name = name.upper()
                if name not in declared_fields:
                    raise ValueError(f"undeclared data item {name}")
                emit(f"state[{name!r}] = {_expression(expression, declared_fields)}")
                continue
        except ValueError as error:
            unsupported.append(UnsupportedStatement(line_number, f"{raw_statement} ({error})"))
            continue

        unsupported.append(UnsupportedStatement(line_number, raw_statement))

    for block in blocks:
        unsupported.append(
            UnsupportedStatement(int(block["line"]), f"unclosed {block['kind']} block")
        )
    return body, unsupported


def translate_cobol(source: str) -> Translation:
    """Translate declarations and simple statements, reporting anything unknown."""
    declarations: dict[str, tuple[bool, str]] = {}
    edited_pics: dict[str, str] = {}
    pic_lengths: dict[str, int] = {}
    procedure: list[tuple[int, str]] = []
    paragraphs: dict[str, list[tuple[int, str]]] = {}
    active_paragraph: str | None = None
    unsupported: list[UnsupportedStatement] = []
    in_procedure = False
    in_program = False

    for line_number, line in _source_lines(source):
        upper_line = line.upper()
        if upper_line == "IDENTIFICATION DIVISION.":
            in_program = True
            continue
        if not in_program:
            continue
        if upper_line.startswith("PROCEDURE DIVISION"):
            in_procedure = True
            continue
        if not in_procedure:
            match = DATA_ITEM.match(line)
            if match and match.group(1).upper() != "FILLER":
                name, picture, initial = match.groups()
                numeric = "9" in picture or "V" in picture
                try:
                    initial_value = _literal(initial, numeric) if initial else ("Decimal('0')" if numeric else "''")
                    declarations[name.upper()] = (numeric, initial_value)
                    pic_lengths[name.upper()] = _picture_length(picture)
                    if not numeric:
                        declarations[name.upper()] = (
                            numeric,
                            f"_cobol_text({initial_value}, {pic_lengths[name.upper()]})",
                        )
                    if "Z" in picture.upper() or "*" in picture:
                        edited_pics[name.upper()] = picture.upper()
                except ValueError as error:
                    unsupported.append(UnsupportedStatement(line_number, f"{line} ({error})"))
                continue
            if re.fullmatch(r"\d{2}\s+[A-Z][A-Z0-9-]*\.", line, re.IGNORECASE):
                continue
            known_headers = {
                "ENVIRONMENT DIVISION.",
                "DATA DIVISION.",
                "WORKING-STORAGE SECTION.",
                "LOCAL-STORAGE SECTION.",
                "LINKAGE SECTION.",
                "FILE SECTION.",
                "INPUT-OUTPUT SECTION.",
                "FILE-CONTROL.",
            }
            if upper_line in known_headers or upper_line.startswith(("PROGRAM-ID.", "AUTHOR.")):
                continue
            unsupported.append(UnsupportedStatement(line_number, line))
            continue
        paragraph_match = re.fullmatch(rf"({IDENTIFIER})\.\s*", line, re.IGNORECASE)
        reserved_paragraph_names = COBOL_VERBS | {
            "END-IF",
            "END-EVALUATE",
            "END-PERFORM",
        }
        if paragraph_match and paragraph_match.group(1).upper() not in reserved_paragraph_names:
            active_paragraph = paragraph_match.group(1).upper()
            paragraphs[active_paragraph] = []
            continue
        if upper_line in {"STOP RUN.", "GOBACK."} or upper_line.startswith("END PROGRAM"):
            target = paragraphs[active_paragraph] if active_paragraph else procedure
            target.append((line_number, line))
            continue
        target = paragraphs[active_paragraph] if active_paragraph else procedure
        target.append((line_number, line))

    if not in_procedure:
        unsupported.append(
            UnsupportedStatement(len(source.splitlines()) or 1, "PROCEDURE DIVISION not found")
        )

    numeric_fields = {name for name, (numeric, _) in declarations.items() if numeric}
    declared_fields = set(declarations)
    paragraph_names = set(paragraphs)
    body, statement_errors = _translate_statements(
        procedure, numeric_fields, declared_fields, paragraph_names, edited_pics, pic_lengths
    )
    unsupported.extend(statement_errors)

    initialization = [f"    {name!r}: {value}," for name, (_, value) in declarations.items()]
    generated = [
        '"""Generated from a supported subset of COBOL; review before production use."""',
        "from decimal import Decimal",
        "",
        "def _cobol_text(value, width):",
        "    return (str(value) + (' ' * width))[:width]",
        "",
        "def _cobol_refmod(state, name, start, length, value, width):",
        "    buffer = _cobol_text(state[name], width)",
        "    start_index = start - 1",
        "    replacement = _cobol_text(value, length)",
        "    state[name] = buffer[:start_index] + replacement + buffer[start_index + length:]",
        "",
        "def _cobol_string(state, name, fragments, width, start, length, pointer):",
        "    buffer = _cobol_text(state[name], width)",
        "    start_index = int(state[pointer]) - 1 if pointer is not None else start - 1",
        "    limit = min(width, start_index + length) if length is not None else width",
        "    result = ''",
        "    for value, delimiter in fragments:",
        "        text = str(value)",
        "        if delimiter is not None:",
        "            text = text.split(str(delimiter), 1)[0]",
        "        remaining = limit - start_index - len(result)",
        "        if remaining > 0:",
        "            result += text[:remaining]",
        "    state[name] = buffer[:start_index] + result + buffer[start_index + len(result):]",
        "    if pointer is not None:",
        "        state[pointer] = Decimal(start_index + len(result) + 1)",
        "",
        "def _inspect_convert(value, from_chars, to_chars):",
        "    return str(value).translate(str.maketrans(str(from_chars), str(to_chars)))",
        "",
    ]
    for name, statements in paragraphs.items():
        paragraph_body, paragraph_errors = _translate_statements(
            statements, numeric_fields, declared_fields, paragraph_names, edited_pics, pic_lengths
        )
        unsupported.extend(paragraph_errors)
        generated.extend(
            [f"def {_python_paragraph_name(name)}(state: dict[str, object]) -> None:", *(paragraph_body or ["    pass"]), ""]
        )
    generated.extend([
        "def main() -> None:",
        "    state = {",
        *initialization,
        "    }",
        *(body or ["    pass"]),
        "",
        "if __name__ == '__main__':",
        "    main()",
        "",
    ])
    return Translation("\n".join(generated), tuple(unsupported))


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate a supported COBOL subset to Python.")
    parser.add_argument("source", type=Path, help="input COBOL source file")
    parser.add_argument("-o", "--output", type=Path, help="output Python file (default: same name with .py)")
    arguments = parser.parse_args()

    try:
        source = arguments.source.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        print(f"Could not read {arguments.source}: {error}", file=sys.stderr)
        return 2

    translation = translate_cobol(source)
    if translation.unsupported:
        print("Translation stopped; unsupported or undeclared code was found:", file=sys.stderr)
        for item in translation.unsupported:
            print(f"  line {item.line}: {item.source}", file=sys.stderr)
        print("No Python output was written.", file=sys.stderr)
        return 1

    output = arguments.output or arguments.source.with_suffix(".py")
    try:
        output.write_text(translation.python_source, encoding="utf-8")
    except OSError as error:
        print(f"Could not write {output}: {error}", file=sys.stderr)
        return 2
    print(f"Wrote translated Python to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())