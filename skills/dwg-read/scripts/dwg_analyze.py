#!/usr/bin/env python3
"""Analyze a DXF file (converted from DWG) and write a readable report.

This script reads a .dxf file with ezdxf and reports what is in it:
layers, entity types and counts, text, dimensions, blocks, extents and
units. It never modifies any file. It never invents a number: anything
it cannot determine is reported as unknown.

Install the dependency first (this script never installs anything):
    pip install ezdxf

Usage:
    python3 dwg_analyze.py plan.dxf
    python3 dwg_analyze.py plan.dxf --out plan-report.md
    python3 dwg_analyze.py plan.dxf --json plan.json
    python3 dwg_analyze.py plan.dxf --text-limit 20

Exit codes: 0 = report written, 1 = the DXF could not be read,
2 = usage error or ezdxf not installed.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

try:
    import ezdxf
    from ezdxf import bbox as ezdxf_bbox
except ImportError:
    print(
        "ezdxf is not installed. Install it first "
        "(this script never installs anything):\n"
        "  pip install ezdxf",
        file=sys.stderr,
    )
    sys.exit(2)


# DXF $INSUNITS codes, as defined by the DXF reference.
INSUNITS = {
    0: "unitless",
    1: "inches",
    2: "feet",
    3: "miles",
    4: "millimetres",
    5: "centimetres",
    6: "metres",
    7: "kilometres",
    8: "microinches",
    9: "mils",
    10: "yards",
    11: "angstroms",
    12: "nanometres",
    13: "microns",
    14: "decimetres",
    15: "decametres",
    16: "hectometres",
    17: "gigametres",
    18: "astronomical units",
    19: "light-years",
    20: "parsecs",
    21: "US survey feet",
    22: "US survey inches",
    23: "US survey yards",
    24: "US survey miles",
}

# DXF DIMENSION type codes (group code 70, low bits).
DIMTYPE_NAMES = {
    0: "rotated / horizontal / vertical",
    1: "aligned",
    2: "angular",
    3: "diameter",
    4: "radius",
    5: "angular, 3 points",
    6: "ordinate",
}


class AnalysisError(Exception):
    """The DXF file could not be read."""


def header_value(doc, tag, default=None):
    try:
        return doc.header[tag]
    except Exception:
        return default


def layer_status(layer):
    flags = []
    for check, label in ((layer.is_off, "off"),
                         (layer.is_frozen, "frozen"),
                         (layer.is_locked, "locked")):
        try:
            if check():
                flags.append(label)
        except Exception:
            pass
    return ", ".join(flags) if flags else "on"


def analyze(path):
    """Read the DXF and return a plain data dict. Raises AnalysisError."""
    try:
        doc = ezdxf.readfile(str(path))
        recovered = False
    except Exception:
        # Try the recovery reader, which tolerates damaged files.
        try:
            from ezdxf import recover
            doc, _auditor = recover.readfile(str(path))
            recovered = True
        except Exception as exc:
            raise AnalysisError("could not read %s: %s" % (path, exc))

    msp = doc.modelspace()
    entities = list(msp)
    counts = collections.Counter(e.dxftype() for e in entities)

    per_layer = collections.Counter()
    for entity in entities:
        try:
            per_layer[entity.dxf.layer] += 1
        except Exception:
            per_layer["<unknown>"] += 1

    layers = []
    for layer in doc.layers:
        try:
            name = layer.dxf.name
        except Exception:
            continue
        try:
            color = layer.dxf.color
        except Exception:
            color = None
        layers.append({
            "name": name,
            "color": color,
            "status": layer_status(layer),
            "entities": per_layer.get(name, 0),
        })

    text_entries = []
    for entity in entities:
        entity_type = entity.dxftype()
        if entity_type == "TEXT":
            try:
                content = entity.dxf.text
                insert = entity.dxf.insert
                text_entries.append({
                    "text": content,
                    "layer": entity.dxf.layer,
                    "x": round(float(insert.x), 4),
                    "y": round(float(insert.y), 4),
                })
            except Exception:
                continue
        elif entity_type == "MTEXT":
            try:
                content = entity.plain_text()
            except Exception:
                try:
                    content = entity.dxf.text
                except Exception:
                    continue
            try:
                insert = entity.dxf.insert
                x, y = round(float(insert.x), 4), round(float(insert.y), 4)
            except Exception:
                x, y = None, None
            try:
                layer_name = entity.dxf.layer
            except Exception:
                layer_name = "<unknown>"
            text_entries.append({
                "text": content,
                "layer": layer_name,
                "x": x,
                "y": y,
            })

    dimensions = []
    for entity in entities:
        if entity.dxftype() != "DIMENSION":
            continue
        raw_type = entity.dxf.get("dimtype")
        base_type = (raw_type & 7) if isinstance(raw_type, int) else None
        try:
            measurement = entity.get_measurement()
            measurement = round(float(measurement), 4)
        except Exception:
            measurement = None
        try:
            style = entity.dxf.get("dimstyle", "?")
        except Exception:
            style = "?"
        try:
            layer_name = entity.dxf.layer
        except Exception:
            layer_name = "<unknown>"
        dimensions.append({
            "type": DIMTYPE_NAMES.get(base_type, "unknown"),
            "raw_type": raw_type,
            "style": style,
            "layer": layer_name,
            "measurement": measurement,
        })

    blocks = []
    for block in doc.blocks:
        try:
            name = block.name
        except Exception:
            try:
                name = block.block_record.dxf.name
            except Exception:
                continue
        if not name or name.startswith("*"):
            continue
        try:
            types = collections.Counter(e.dxftype() for e in block)
        except Exception:
            types = {}
        blocks.append({
            "name": name,
            "entities": sum(types.values()),
            "types": dict(types),
        })

    inserts = collections.Counter()
    insert_layers = collections.defaultdict(set)
    for entity in entities:
        if entity.dxftype() != "INSERT":
            continue
        try:
            inserts[entity.dxf.name] += 1
            insert_layers[entity.dxf.name].add(entity.dxf.layer)
        except Exception:
            continue

    extents = None
    try:
        low, high = ezdxf_bbox.extents(msp)
        extents = {
            "min": [round(float(v), 4) for v in low],
            "max": [round(float(v), 4) for v in high],
            "width": round(float(high.x - low.x), 4),
            "height": round(float(high.y - low.y), 4),
        }
    except Exception:
        extents = None

    insunits = header_value(doc, "$INSUNITS")
    if insunits is None:
        try:
            insunits = doc.units
        except Exception:
            insunits = 0
    try:
        insunits = int(insunits)
    except Exception:
        insunits = 0

    dxf_version = header_value(doc, "$ACADVER")
    if not dxf_version:
        try:
            dxf_version = doc.dxfversion
        except Exception:
            dxf_version = "unknown"

    return {
        "file": path.name,
        "dxf_version": dxf_version,
        "recovered": recovered,
        "units_code": insunits,
        "units": INSUNITS.get(insunits, "unknown"),
        "measurement": header_value(doc, "$MEASUREMENT"),
        "extents": extents,
        "total_entities": len(entities),
        "layers": layers,
        "entity_counts": dict(counts),
        "text": text_entries,
        "dimensions": dimensions,
        "blocks": blocks,
        "inserts": [
            {"block": name, "count": count,
             "layers": sorted(insert_layers[name])}
            for name, count in sorted(inserts.items())
        ],
    }


def render_markdown(data, text_limit):
    """Turn the analysis dict into a readable Markdown report."""
    lines = []
    lines.append("# Drawing report: %s" % data["file"])
    lines.append("")
    lines.append("This report describes the DXF file (the converted copy). "
                 "The original DWG was not modified.")
    if data["recovered"]:
        lines.append("")
        lines.append("> Note: this DXF had structural problems and was read "
                     "with the recovery reader. Some content may be missing.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| item | value |")
    lines.append("| --- | --- |")
    lines.append("| DXF version | %s |" % data["dxf_version"])
    lines.append("| Units | %s |" % data["units"])
    measurement = data["measurement"]
    if measurement == 0:
        lines.append("| Measurement | imperial |")
    elif measurement == 1:
        lines.append("| Measurement | metric |")
    else:
        lines.append("| Measurement | unknown |")
    extents = data["extents"]
    if extents:
        lines.append("| Extents min | %s |" % extents["min"])
        lines.append("| Extents max | %s |" % extents["max"])
        lines.append("| Width | %s %s |" % (extents["width"], data["units"]))
        lines.append("| Height | %s %s |" % (extents["height"], data["units"]))
    else:
        lines.append("| Extents | could not be computed |")
    lines.append("| Total entities (model space) | %d |" % data["total_entities"])
    lines.append("| Layers | %d |" % len(data["layers"]))
    lines.append("| Block definitions | %d |" % len(data["blocks"]))
    lines.append("| Text entries | %d |" % len(data["text"]))
    lines.append("| Dimensions | %d |" % len(data["dimensions"]))
    lines.append("")

    lines.append("## Layers")
    lines.append("")
    if data["layers"]:
        lines.append("| layer | color | status | entities |")
        lines.append("| --- | --- | --- | --- |")
        for layer in data["layers"]:
            color = layer["color"] if layer["color"] is not None else "?"
            lines.append("| %s | %s | %s | %d |" % (
                layer["name"], color, layer["status"], layer["entities"]))
    else:
        lines.append("No layers found.")
    lines.append("")

    lines.append("## Entity counts (model space)")
    lines.append("")
    if data["entity_counts"]:
        lines.append("| entity type | count |")
        lines.append("| --- | --- |")
        for entity_type, count in sorted(
                data["entity_counts"].items(), key=lambda item: -item[1]):
            lines.append("| %s | %d |" % (entity_type, count))
    else:
        lines.append("No entities in model space.")
    lines.append("")

    lines.append("## Text")
    lines.append("")
    total_text = len(data["text"])
    if total_text:
        shown = data["text"][:text_limit]
        lines.append("| text | layer | x | y |")
        lines.append("| --- | --- | --- | --- |")
        for entry in shown:
            text = entry["text"].replace("|", "\\|").replace("\n", " ")
            x = entry["x"] if entry["x"] is not None else "?"
            y = entry["y"] if entry["y"] is not None else "?"
            lines.append("| %s | %s | %s | %s |" % (
                text, entry["layer"], x, y))
        if total_text > text_limit:
            lines.append("")
            lines.append("%d more text entries not shown "
                         "(use --text-limit to show more)." %
                         (total_text - text_limit))
    else:
        lines.append("No TEXT or MTEXT entities found.")
    lines.append("")

    lines.append("## Dimensions")
    lines.append("")
    if data["dimensions"]:
        lines.append("| type | style | layer | measurement |")
        lines.append("| --- | --- | --- | --- |")
        for dim in data["dimensions"]:
            measurement = (dim["measurement"] if dim["measurement"] is not None
                           else "not computed")
            lines.append("| %s | %s | %s | %s |" % (
                dim["type"], dim["style"], dim["layer"], measurement))
    else:
        lines.append("No DIMENSION entities found.")
    lines.append("")

    lines.append("## Blocks")
    lines.append("")
    if data["blocks"]:
        lines.append("| block | entities | contents |")
        lines.append("| --- | --- | --- |")
        for block in data["blocks"]:
            contents = ", ".join("%s (%d)" % (t, c)
                                 for t, c in sorted(block["types"].items()))
            lines.append("| %s | %d | %s |" % (
                block["name"], block["entities"], contents or "-"))
    else:
        lines.append("No user block definitions found.")
    lines.append("")
    if data["inserts"]:
        lines.append("Block references in model space:")
        lines.append("")
        lines.append("| block | times inserted | layers |")
        lines.append("| --- | --- | --- |")
        for insert in data["inserts"]:
            lines.append("| %s | %d | %s |" % (
                insert["block"], insert["count"], ", ".join(insert["layers"])))
        lines.append("")
    else:
        lines.append("No block references in model space.")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- Entity and layer counts cover model space only, unless "
                 "stated otherwise.")
    lines.append("- Anything this script could not determine is reported as "
                 "unknown or not computed, never guessed.")
    lines.append("- DWG to DXF conversion can drop proxy objects, "
                 "dynamic-block details and some 3D solid data. If something "
                 "is missing here, the conversion may have dropped it.")
    lines.append("- Text inside images or scanned raster drawings is not "
                 "readable from a DXF.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze a DXF file and write a readable report.")
    parser.add_argument("dxf", help="the .dxf file to analyze")
    parser.add_argument("--out", default=None,
                        help="write the Markdown report to this file "
                             "(default: print it)")
    parser.add_argument("--json", default=None,
                        help="also write the analysis data as JSON to this file")
    parser.add_argument("--text-limit", type=int, default=100,
                        help="maximum text entries shown (default: 100)")
    args = parser.parse_args(argv)

    path = Path(args.dxf).expanduser()
    if not path.is_file():
        print("File not found: %s" % path, file=sys.stderr)
        return 2
    if path.suffix.lower() != ".dxf":
        print("Warning: %s does not end in .dxf; trying anyway." % path,
              file=sys.stderr)

    try:
        data = analyze(path)
    except AnalysisError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    report = render_markdown(data, args.text_limit)
    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.write_text(report, encoding="utf-8")
        print("Report written: %s" % out_path)
    else:
        print(report, end="")
    if args.json:
        json_path = Path(args.json).expanduser()
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        print("JSON written: %s" % json_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
