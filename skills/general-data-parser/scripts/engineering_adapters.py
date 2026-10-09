"""Executable, dependency-free adapters with explicit scopes and checks.

All adapters read bytes as data. No source code, DTD, plugin or network execution.
"""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import io
import json
import math
import re
import struct
import xml.etree.ElementTree as ET


VERSION = "1"
FORMATS = {
    "csv": "Rectangular text table, explicit header policy; optional time-series checks",
    "tsv": "Tab-separated rectangular table; optional time-series checks",
    "json": "Strict JSON with preserved numeric lexemes, types and pointers",
    "jsonl": "One strict JSON value per nonblank line; physical line locators",
    "xml": "DTD-free XML document-element tree, namespaces, attributes, text/tail and ordered children",
    "stl": "ASCII or binary triangle surface geometry; no manufacturing claim",
    "obj": "Vertex/normal/UV/face mesh subset; material directives retained, appearance not interpreted",
}
MESH_FORMATS = {"stl", "obj"}


class ParseError(ValueError):
    pass


class Unsupported(ParseError):
    pass


def need(condition, message):
    if not condition:
        raise ParseError(message)


@dataclass
class Result:
    data: dict
    metrics: dict
    checks: list
    limitations: list


def check(name, passed, method, actual=None, expected=None):
    return {"id": name, "result": "pass" if passed else "fail", "executed": True,
            "method": method, "actual": actual, "expected": expected}


def decoded(raw, options):
    try:
        value = raw.decode(options["encoding"])
    except (UnicodeError, LookupError) as exc:
        raise ParseError("Cannot decode source using declared encoding") from exc
    need("\x00" not in value, "NUL is not supported in text input")
    return value


def decimal_value(value):
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ParseError("Invalid numeric value") from exc
    need(number.is_finite(), "Nonfinite numeric value")
    return number


def coordinate(value, options):
    need(len(value) <= 4096, "Coordinate token exceeds numeric precision scope")
    exact = decimal_value(value)
    number = float(exact)
    need(math.isfinite(number), "Coordinate overflows binary64")
    with localcontext() as context:
        context.prec = max(1100, len(exact.as_tuple().digits) + 40)
        tolerance = Decimal(str(options["abs_tolerance"])) + Decimal(str(options["rel_tolerance"])) * abs(exact)
        need(abs(Decimal.from_float(number) - exact) <= tolerance, "Coordinate precision exceeds declared tolerance")
    return number


def parse_table(raw, fmt, options):
    text = decoded(raw, options)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="\t" if fmt == "tsv" else ",", strict=True)
    records, spans = [], []
    previous = 0
    try:
        for record in reader:
            need(len(records) < options["max_items"], "Table record limit exceeded")
            records.append(record)
            spans.append([previous + 1, reader.line_num])
            previous = reader.line_num
    except csv.Error as exc:
        raise ParseError(f"Invalid delimited record near physical line {reader.line_num}") from exc
    need(bool(records), "Empty table")
    if options["header"]:
        columns, rows, row_spans = records[0], records[1:], spans[1:]
        need(all(name.strip() for name in columns), "Empty column name")
        need(len(columns) == len(set(columns)), "Duplicate column names")
    else:
        columns, rows, row_spans = [f"column_{i + 1}" for i in range(len(records[0]))], records, spans
    need(bool(columns), "Empty table header")
    need(all(len(row) == len(columns) for row in rows), "Ragged/blank row: column counts differ")
    buffer = io.StringIO(newline="")
    csv.writer(buffer, delimiter="\t" if fmt == "tsv" else ",", lineterminator="\n").writerows(records)
    roundtrip = list(csv.reader(io.StringIO(buffer.getvalue()), delimiter="\t" if fmt == "tsv" else ","))
    checks = [
        check("format.structure", True, "Validate rectangular rows and unique nonempty column names"),
        check("engineering.values", roundtrip == records, "CSV writer/reader roundtrip preserves every string cell, including empty and zero"),
    ]
    data = {"columns": columns, "header_present": options["header"],
            "rows": [{"index": i, "source_lines": span, "values": row}
                     for i, (row, span) in enumerate(zip(rows, row_spans))]}
    metrics = {"record_count": len(rows), "column_count": len(columns), "physical_lines": len(text.splitlines())}
    if options["time_column"] is not None:
        need(options["time_column"] in columns, "Requested time column does not exist")
        need(bool(rows), "Time series has no samples")
        index = columns.index(options["time_column"])
        times = []
        for row in rows:
            value = row[index]
            need(bool(value.strip()), "Missing time value")
            if options["time_unit"]:
                original = decimal_value(value).as_tuple()
                scale = {"s": 0, "ms": -3, "us": -6, "ns": -9}[options["time_unit"]]
                times.append(Decimal((original.sign, original.digits, original.exponent + scale)))
            else:
                need(bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})", value)),
                     "ISO time requires seconds, explicit timezone and at most six fractional digits; use numeric ns for higher precision")
                try:
                    at = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ParseError("Time is neither declared numeric time nor ISO 8601") from exc
                need(at.utcoffset() is not None, "ISO time requires an explicit timezone")
                elapsed = at.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
                times.append(Decimal(elapsed.days * 86400 + elapsed.seconds) + Decimal(elapsed.microseconds) / 1000000)
        precision = max(50, max(t.adjusted() for t in times) - min(t.as_tuple().exponent for t in times) + 3)
        need(precision <= 4096, "Time arithmetic exceeds declared 4096-digit range")
        with localcontext() as context:
            context.prec = precision
            gaps = [right - left for left, right in zip(times, times[1:])]
            span = str(times[-1] - times[0])
        ordered = all(gap > 0 for gap in gaps) if options["time_order"] == "strict" else all(gap >= 0 for gap in gaps)
        checks.append(check("engineering.time", ordered, f"Check {options['time_order']} ordering in declared time basis",
                            [str(gap) for gap in gaps], "positive gaps" if options["time_order"] == "strict" else "nonnegative gaps"))
        data["time"] = {"column": options["time_column"], "seconds": [str(value) for value in times],
                        "basis": "relative numeric axis, epoch unspecified" if options["time_unit"] else "UTC since 1970-01-01"}
        metrics["time_span_seconds"] = span
    return Result(data, metrics, checks, [])


class NumberToken(str):
    pass


def json_value(text):
    def pairs(entries):
        result = {}
        for key, value in entries:
            need(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ParseError(f"Nonstandard JSON constant: {value}")

    try:
        parsed = json.loads(text, object_pairs_hook=pairs, parse_int=NumberToken,
                            parse_float=NumberToken, parse_constant=invalid)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}") from exc
    tokens = []

    def visit(value, pointer):
        if isinstance(value, NumberToken):
            decimal_value(value)
            tokens.append({"pointer": pointer, "lexeme": str(value),
                           "type": "number" if any(c in value for c in ".eE") else "integer"})
            return str(value)
        if isinstance(value, dict):
            for key in value:
                try:
                    key.encode("utf-8")
                except UnicodeError as exc:
                    raise ParseError("Unpaired Unicode surrogate in JSON key") from exc
            return {key: visit(item, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
                    for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item, pointer + "/" + str(i)) for i, item in enumerate(value)]
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError as exc:
                raise ParseError("Unpaired Unicode surrogate in JSON string") from exc
        return value

    return {"value": visit(parsed, ""), "numeric_tokens": tokens}


def parse_json(raw, fmt, options):
    text = decoded(raw, options)
    if fmt == "json":
        records = [{"source_lines": [1, max(1, len(text.splitlines()))], **json_value(text)}]
        blank_lines = 0
    else:
        records, blank_lines = [], 0
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                blank_lines += 1
                continue
            need(len(records) < options["max_items"], "JSONL record limit exceeded")
            records.append({"source_lines": [number, number], **json_value(line)})
    numeric = sum(len(record["numeric_tokens"]) for record in records)
    nodes = 0
    stack = [record["value"] for record in records]
    while stack:
        value = stack.pop()
        nodes += 1
        need(nodes <= options["max_items"], "JSON node limit exceeded")
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return Result({"records": records, "numeric_representation": "lexical strings plus numeric_tokens type map"},
                  {"record_count": len(records), "node_count": nodes, "numeric_token_count": numeric,
                   "blank_lines": blank_lines},
                  [check("format.structure", True, "Strict JSON decoding rejects duplicate keys and nonstandard constants"),
                   check("engineering.values", True, "Preserve numeric tokens without floating-point conversion; preserve null, boolean and string types")], [])


def parse_xml(raw, fmt, options):
    text = decoded(raw, options)

    class NoDTD(ET.TreeBuilder):
        def doctype(self, name, pubid, system):
            raise Unsupported("DTD/entity declarations are outside the supported XML scope")

    try:
        parser = ET.XMLParser(target=NoDTD(insert_comments=True, insert_pis=True))
        root = ET.fromstring(text, parser=parser)
    except ET.ParseError as exc:
        raise ParseError("Invalid XML") from exc
    nodes = []

    def visit(element, indices):
        need(len(nodes) < options["max_items"], "XML node limit exceeded")
        tag = element.tag if isinstance(element.tag, str) else (
            "#comment" if element.tag is ET.Comment else "#processing-instruction")
        item = {"id": len(nodes), "path_indices": indices, "tag": tag, "attributes": dict(element.attrib),
                "text": element.text, "tail": element.tail, "children": []}
        nodes.append(item)
        for index, child in enumerate(element):
            item["children"].append(visit(child, indices + [index]))
        return item["id"]

    visit(root, [])
    serialized = ET.tostring(root, encoding="unicode")
    second = ET.fromstring(serialized, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True)))

    def signature(node):
        tag = node.tag if isinstance(node.tag, str) else repr(node.tag.__name__)
        return tag, dict(node.attrib), node.text, node.tail, [signature(child) for child in node]

    return Result({"root": 0, "nodes": nodes, "names": "namespace-expanded names"},
                  {"node_count": len(nodes), "element_count": sum(not n["tag"].startswith("#") for n in nodes)},
                  [check("format.structure", True, "Parse DTD-free XML with ordered children and namespace expansion"),
                   check("engineering.values", signature(root) == signature(second),
                         "Serialize/reparse and compare names, attributes, text, tail and children")],
                  ["XML declaration and nodes outside the document element remain in source bytes only; no schema/DTD interpretation."])


def mesh_result(vertices, faces, metadata, options):
    need(bool(vertices) and bool(faces), "Mesh must contain vertices and surface faces")
    need(all(len(face["vertices"]) >= 3 for face in faces), "Mesh face has fewer than three vertices")
    need(all(0 <= index < len(vertices) for face in faces for index in face["vertices"]), "Mesh index out of range")
    points = [v["position"] for v in vertices]
    minima = [min(p[axis] for p in points) for axis in range(3)]
    maxima = [max(p[axis] for p in points) for axis in range(3)]
    extent = [right - left for left, right in zip(minima, maxima)]
    need(all(math.isfinite(x) for x in minima + maxima + extent), "Nonfinite mesh bounds")
    degenerate = 0
    for face in faces:
        positions = [points[index] for index in face["vertices"]]
        # A face must contain at least one non-collinear triangle fan member.
        valid = False
        for i in range(1, len(positions) - 1):
            a = [positions[i][j] - positions[0][j] for j in range(3)]
            b = [positions[i + 1][j] - positions[0][j] for j in range(3)]
            cross = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
            need(all(math.isfinite(x) for x in cross), "Geometry calculation overflow")
            valid |= any(x != 0 for x in cross)
        degenerate += not valid
    checks = [
        check("format.structure", True, "Validate mesh face cardinality and resolved indices"),
        check("engineering.geometry", degenerate == 0, "Check finite bounds and non-collinear triangle fan",
              {"degenerate_faces": degenerate}, {"degenerate_faces": 0}),
        check("engineering.units", bool(options["length_unit"]) or not options["require_unit"],
              "Require explicit length unit when requested; never infer STL/OBJ units",
              options["length_unit"], "declared unit" if options["require_unit"] else "unknown explicitly permitted"),
    ]
    limits = []
    if not options["length_unit"]:
        limits.append("Length unit unknown; coordinates and bounds are in the source's raw coordinate system.")
    if metadata.get("material_directives"):
        limits.append("Material directives are retained as source declarations; material/texture dependencies are not interpreted in geometry-only scope.")
    return Result({"vertices": vertices, "faces": faces, "metadata": metadata,
                   "coordinate_system": "source axes, no transform", "length_unit": options["length_unit"],
                   "unit_basis": "caller declaration" if options["length_unit"] else "unknown"},
                  {"vertex_count": len(vertices), "face_count": len(faces),
                   "bbox": {"min": minima, "max": maxima, "extent": extent, "unit": options["length_unit"],
                            "method": "extrema of parsed vertices; binary64 arithmetic"}},
                  checks, limits)


def parse_stl(raw, fmt, options):
    vertices, faces = [], []
    count = struct.unpack_from("<I", raw, 80)[0] if len(raw) >= 84 else None
    binary = count is not None and len(raw) == 84 + 50 * count
    if binary:
        need(count <= options["max_items"], "STL facet limit exceeded")
        for i in range(count):
            offset = 84 + i * 50
            values = struct.unpack_from("<12fH", raw, offset)
            need(all(math.isfinite(x) for x in values[:12]), "Nonfinite binary STL value")
            indices = []
            for j in range(3):
                indices.append(len(vertices))
                vertices.append({"position": list(values[3 + 3*j:6 + 3*j]),
                                 "locator": {"byte_offset": offset + 12 + 12*j, "facet": i}})
            faces.append({"vertices": indices, "declared_normal": list(values[:3]),
                          "attribute_word": values[12], "locator": {"byte_offset": offset, "facet": i}})
        metadata = {"encoding": "binary", "header_hex": raw[:80].hex()}
    else:
        try:
            text = decoded(raw, options)
        except ParseError as exc:
            raise ParseError("STL binary size/count mismatch or invalid text encoding") from exc
        lines = [(i, line.strip()) for i, line in enumerate(text.splitlines(), 1) if line.strip()]
        need(len(lines) >= 2 and lines[0][1].split()[0] == "solid", "Invalid/truncated STL header")
        need(lines[-1][1].split()[0] == "endsolid", "Missing STL endsolid")
        cursor = 1
        while cursor < len(lines) - 1:
            need(len(faces) < options["max_items"], "STL facet limit exceeded")
            chunk = lines[cursor:cursor + 7]
            need(len(chunk) == 7, "Truncated STL facet")
            first = chunk[0][1].split()
            need(len(first) == 5 and first[:2] == ["facet", "normal"], "Invalid facet normal")
            normal = [coordinate(x, options) for x in first[2:]]
            need(chunk[1][1] == "outer loop" and chunk[5][1] == "endloop" and chunk[6][1] == "endfacet", "Invalid facet structure")
            indices = []
            for line, value in chunk[2:5]:
                tokens = value.split()
                need(len(tokens) == 4 and tokens[0] == "vertex", "Invalid STL vertex")
                indices.append(len(vertices))
                vertices.append({"position": [coordinate(x, options) for x in tokens[1:]],
                                 "locator": {"line": line, "line_base": 1}, "source_numbers": tokens[1:]})
            faces.append({"vertices": indices, "declared_normal": normal, "locator": {"line": chunk[0][0], "line_base": 1}})
            cursor += 7
        need(cursor == len(lines) - 1, "Trailing or unsupported ASCII STL content")
        metadata = {"encoding": "ascii", "solid_name": lines[0][1][5:].strip()}
    result = mesh_result(vertices, faces, metadata, options)
    result.checks.append(check("engineering.values", True, "STL count/byte layout or complete facet grammar; preserve declared normals and source values"))
    return result


def parse_obj(raw, fmt, options):
    text = decoded(raw, options)
    vertices, normals, uv, pending, metadata = [], [], [], [], []
    for line, original in enumerate(text.splitlines(), 1):
        tokens = original.split("#", 1)[0].split()
        if not tokens:
            continue
        kind, values = tokens[0], tokens[1:]
        need(len(vertices) + len(normals) + len(uv) + len(pending) + len(metadata) < options["max_items"],
             "OBJ item limit exceeded")
        if kind == "v":
            need(len(values) in {3, 4}, "OBJ supports v x y z [w], not implicit vertex-colour extensions")
            point = [coordinate(value, options) for value in values]
            if len(point) == 4:
                need(point[3] != 0, "Zero homogeneous coordinate")
                point = [value / point[3] for value in point[:3]]
            need(all(math.isfinite(x) for x in point), "Homogeneous coordinate overflow")
            vertices.append({"position": point, "source_numbers": values, "locator": {"line": line, "line_base": 1}})
        elif kind in {"vn", "vt"}:
            need(len(values) == 3 if kind == "vn" else 1 <= len(values) <= 3, "Invalid OBJ normal/UV")
            (normals if kind == "vn" else uv).append([coordinate(value, options) for value in values])
        elif kind == "f":
            need(len(values) >= 3, "OBJ face has fewer than three vertices")
            pending.append((values, (len(vertices), len(uv), len(normals)), line))
        elif kind in {"o", "g", "s", "mtllib", "usemtl"}:
            metadata.append({"kind": kind, "values": values, "line": line})
        else:
            raise Unsupported(f"Unsupported OBJ record '{kind}' at line {line}; no silent geometry loss")
    faces = []

    def index(value, total, at_line):
        need(bool(re.fullmatch(r"-?[0-9]+", value)), "Invalid OBJ index")
        number = int(value)
        need(number != 0, "OBJ indices are not zero-based")
        resolved = number - 1 if number > 0 else at_line + number
        need(0 <= resolved < total, "OBJ index out of range")
        return resolved

    for values, counts, line in pending:
        refs = []
        for value in values:
            parts = value.split("/")
            need(1 <= len(parts) <= 3 and bool(parts[0]), "Invalid OBJ face reference")
            need(len(parts) == 1 or bool(parts[-1]), "Empty trailing OBJ reference")
            vertex = index(parts[0], len(vertices), counts[0])
            tex = index(parts[1], len(uv), counts[1]) if len(parts) > 1 and parts[1] else None
            normal = index(parts[2], len(normals), counts[2]) if len(parts) > 2 and parts[2] else None
            refs.append({"vertex": vertex, "uv": tex, "normal": normal})
        faces.append({"vertices": [ref["vertex"] for ref in refs], "references": refs,
                      "locator": {"line": line, "line_base": 1}})
    result = mesh_result(vertices, faces, {"normals": normals, "uv": uv, "records": metadata,
                                          "material_directives": [m for m in metadata if m["kind"] in {"mtllib", "usemtl"}]}, options)
    result.checks.append(check("engineering.values", True, "Resolve positive/negative OBJ references; retain original coordinate tokens and declaration lines"))
    return result


ADAPTERS = {"csv": parse_table, "tsv": parse_table, "json": parse_json, "jsonl": parse_json,
            "xml": parse_xml, "stl": parse_stl, "obj": parse_obj}


def parse(raw, fmt, options):
    if fmt not in ADAPTERS:
        raise Unsupported(f"No implemented adapter for {fmt}")
    need(len(raw) <= options["max_bytes"], "Input byte limit exceeded")
    need(options["max_items"] > 0, "Invalid item limit")
    if fmt not in {"csv", "tsv"}:
        need(options["header"], "Header options require a table adapter")
        need(options["time_column"] is None and options["time_unit"] is None,
             "Time options require a table adapter")
    need(options["time_unit"] is None or options["time_column"] is not None, "time_unit requires time_column")
    if fmt not in MESH_FORMATS:
        need(options["length_unit"] is None and not options["require_unit"], "Length-unit options require a mesh adapter")
    return ADAPTERS[fmt](raw, fmt, options)
