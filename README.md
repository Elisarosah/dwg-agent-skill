# The DWG agent skill

One Claude skill that reads a DWG drawing and tells you what is in it.
Free, MIT, no signup, no API key, nothing to connect.

DWG is a closed binary format, so no skill reads it directly. This one is
honest about that: it converts the DWG to DXF with the free ODA File
Converter, then analyzes the DXF with Python and ezdxf and hands you a
readable Markdown report: layers, entity counts, text, dimensions, blocks,
extents and units.

**Nothing gets modified.** The original DWG is never touched. The skill
reads and reports; you decide what to do next.

## Install

This pack lives in a folder, not on GitHub yet, so install it by copying
the skill into Claude Code:

```bash
cp -r dwg-agent-skill/skills/dwg-read ~/.claude/skills/
```

Project-local instead of global: copy the same folder into your repo's
`.claude/skills/`. No Claude Code at all? Paste `skills/dwg-read/SKILL.md`
at the top of a chat and it runs as a mode. You lose the two Python
scripts, which is most of the point, but the instructions still work.

If the pack gets a GitHub repo later, the plugin files in `.claude-plugin/`
make it installable as a plugin:

```
/plugin marketplace add elisarosah/dwg-agent-skill
/plugin install dwg-agent
```

## Prerequisites (install once, by hand)

**1. ODA File Converter (free)** — https://www.opendesign.com/guestfiles/oda_file_converter

The converter turns DWG into DXF. It runs on macOS, Windows and Linux,
with a graphical interface and a command line. Without it, this skill
cannot read a DWG file at all.

- macOS: open the .dmg and drag ODAFileConverter to /Applications.
- Windows: run the installer and accept the default location.
- Linux: install the .deb or .rpm from the download page.
- ODA offers the converter free for non-commercial use to non-members.
  Check the terms on the download page.

Check it is found:

```bash
python3 skills/dwg-read/scripts/dwg_convert.py --check
```

**2. Python 3.9+ and ezdxf**

```bash
pip install ezdxf
```

The scripts never install anything themselves. If a dependency is
missing, they print the install command and stop.

## The skill

| command | what it does |
| --- | --- |
| `/dwg-read` | One DWG (or a folder of them) into a Markdown report: summary, layers, entity counts, text, dimensions, blocks, extents, units. |

## The two tools

Both live in `skills/dwg-read/scripts/`.

```bash
python3 scripts/dwg_convert.py plan.dwg                          # DWG -> DXF, ./converted/
python3 scripts/dwg_convert.py plans/ --recurse                  # a whole folder
python3 scripts/dwg_analyze.py converted/plan.dxf                # DXF -> report on screen
python3 scripts/dwg_analyze.py converted/plan.dxf --out plan-report.md
python3 scripts/dwg_analyze.py converted/plan.dxf --json plan.json
```

`dwg_convert.py` only calls the ODA binary if it is already installed. If
it is not, it prints the download link and the install steps and stops.
It also verifies that every expected DXF was actually produced, because
ODA returns success even when a single file fails.

## The fine print

- **Nothing here logs in, connects to a service, or publishes anything.**
  The tools run locally; the only network use is you downloading the two
  prerequisites by hand.
- **The original DWG is never modified.** Conversion reads it; analysis
  reads the DXF copy.
- **Never invent a number, a measurement or a piece of content.** If a
  figure is not in the file, the report says so.
- **Conversion can lose data.** Proxy objects, dynamic-block details and
  some 3D solid data may not survive DWG to DXF conversion. If something
  is missing from the report, the conversion may have dropped it.
- **Counts are model space only**, unless the report says otherwise.
- **Text inside images or scanned raster drawings is not readable.**

## Credits

Original work by Ana Elisa (elisarosah), MIT. Built on two free tools:
[ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)
by the Open Design Alliance, and [ezdxf](https://ezdxf.readthedocs.io/)
by Manfred Moitzi (MIT). Neither is bundled here; install both yourself.
