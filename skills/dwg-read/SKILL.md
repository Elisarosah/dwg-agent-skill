---
name: dwg-read
description: >-
  Read and analyze a DWG drawing in Claude Code: converts the DWG to DXF
  with the free ODA File Converter, then analyzes the DXF with Python and
  ezdxf and returns a readable Markdown report (layers, entity counts,
  text, dimensions, blocks, extents, units). Use whenever the user wants
  to read, inspect, list or understand a DWG or DXF drawing, or asks what
  is inside a CAD file. Never modifies the original file.
---

# dwg-read

Read a DWG drawing and tell the user what is in it. Two steps, both honest
about what they can and cannot do.

## The honest pipeline

DWG is a closed binary format. No skill, no Python library in this pack,
and no prompt reads a .dwg file directly. The pipeline is:

1. **Convert** DWG to DXF with the free ODA File Converter (Open Design
   Alliance). DXF is the same drawing in a text format.
2. **Analyze** the DXF with Python and ezdxf. The report describes the
   converted copy. The original DWG is never modified, moved or deleted.

If either step is impossible, say so and stop. Never guess what a drawing
contains.

## Prerequisites (install once, by hand)

**1. ODA File Converter (free)** — https://www.opendesign.com/guestfiles/oda_file_converter

- macOS: open the downloaded .dmg and drag ODAFileConverter to
  /Applications. The binary lives at:
  `/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter`
- Windows: run the downloaded installer and accept the default location
  under `C:\Program Files\ODA`.
- Linux: install the .deb or .rpm package from the download page.
- ODA offers the converter free for non-commercial use to non-members.
  Check the terms on the download page.
- Check it is found: `python3 scripts/dwg_convert.py --check`

**2. Python 3.9+ and ezdxf**

- `pip install ezdxf` (ezdxf 1.4 or newer)
- The scripts never install anything themselves. If ezdxf is missing,
  dwg_analyze.py prints the install command and stops.

## The flow

Run the commands from this skill folder (`skills/dwg-read/`).

**1. Locate the drawing.** Ask for the .dwg file (or a folder of them) if
the user has not given one. Work on the file they point at; never go
looking for drawings on your own.

**2. Convert.**

```bash
python3 scripts/dwg_convert.py plan.dwg
python3 scripts/dwg_convert.py plan.dwg --out-dir ./converted
python3 scripts/dwg_convert.py plans/ --recurse
python3 scripts/dwg_convert.py plan.dwg --version ACAD2013
```

- Default output is DXF at ACAD2018 into `./converted`.
- If ODA is not installed, the script prints the download link and the
  install steps and stops. Do not download or install it for the user.
- ODA works on folders, not single files: for one file the script stages
  a copy in a temporary folder and converts that. The original is untouched.
- ODA returns exit code 0 even when a single file fails, so the script
  checks that every expected .dxf actually exists and reports any missing
  file instead of pretending it worked.

**3. Analyze.**

```bash
python3 scripts/dwg_analyze.py converted/plan.dxf
python3 scripts/dwg_analyze.py converted/plan.dxf --out plan-report.md
python3 scripts/dwg_analyze.py converted/plan.dxf --json plan.json
python3 scripts/dwg_analyze.py converted/plan.dxf --text-limit 20
```

**4. Report.** Give the user the Markdown report (or the file path if they
asked for a file). The report contains:

- summary: DXF version, units, extents, totals
- layers: name, color, on/off/frozen/locked, entity count
- entity counts by type (LINE, CIRCLE, ARC, TEXT, MTEXT, DIMENSION,
  INSERT, HATCH, ...)
- text found in the drawing, with layer and position
- dimensions found, with style, type and measured value when computable
- block definitions and where each block is inserted
- anything the script could not determine, marked as unknown

**5. Answer the question.** The report is the evidence. Quote numbers from
it, never from memory. If the user asked a specific question ("how many
doors?", "what is the overall size?"), answer from the report and say
which section it came from.

## Rules

- **Never modify the original DWG.** Conversion reads it; analysis reads
  the DXF copy. Nothing in this skill writes to a .dwg file.
- **Never invent a number, a measurement or a piece of content.** If a
  figure would help and it is not in the file, say it is not in the file
  or mark it as uncertain. Never fill a gap with a plausible value.
- **Say what the conversion may have lost.** ODA conversion can drop
  proxy objects, dynamic-block details and some 3D solid data. If the
  user asks about something that is not in the DXF, say the conversion
  may have dropped it rather than claiming it was never there.
- **Counts are model space only**, unless the report says otherwise.
- **DXF version:** if ezdxf refuses a DXF newer than ACAD2018,
  re-convert with `--version ACAD2018`.
- **No rendering, no preview, no editing.** This skill reads and reports.
  It does not draw the plan, export an image or change the drawing.

## Limitations, stated plainly

- DWG files are never read directly. A conversion step is always needed,
  and the ODA File Converter must be installed by the user first.
- Text is extracted as stored in the file. Text inside images, scanned
  raster drawings or proxy objects is not readable.
- Dimensions are reported as stored; a measured value is included only
  when ezdxf can compute it.
- Very large drawings can be slow to convert and to analyze. Convert one
  file first before batching a whole folder.

## The gate

Nothing here publishes or modifies the original file. This skill reads and
reports, you decide what to do next.
