#!/usr/bin/env python3
"""Convert DWG files to DXF with the free ODA File Converter.

This script only calls the ODA File Converter binary if it is already
installed on this machine. It never downloads or installs anything.
If the converter is missing, it prints where to get it and exits.

Why a converter is needed: DWG is a closed binary format. Nothing in this
skill reads a .dwg file directly. The converter turns the DWG into a DXF
(a text format), and dwg_analyze.py reads the DXF.

ODA File Converter (free): https://www.opendesign.com/guestfiles/oda_file_converter

Usage:
    python3 dwg_convert.py plan.dwg
    python3 dwg_convert.py plan.dwg --out-dir ./converted
    python3 dwg_convert.py plans/ --recurse
    python3 dwg_convert.py plan.dwg --version ACAD2013
    python3 dwg_convert.py --check        # only check if ODA is installed

Exit codes: 0 = every expected DXF was produced, 1 = conversion ran but
some file has no DXF output, 2 = usage error or ODA File Converter not
installed.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"
DEFAULT_VERSION = "ACAD2018"
DEFAULT_FILTER = "*.DWG"

MAC_PATH = "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"
LINUX_PATHS = ("/usr/bin/ODAFileConverter", "/usr/local/bin/ODAFileConverter")


def find_oda(explicit=None):
    """Locate the ODA File Converter binary. Returns a path string or None."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    for name in ("ODAFileConverter", "ODAFileConverter.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    if sys.platform == "darwin":
        candidates.append(MAC_PATH)
    elif sys.platform.startswith("win"):
        for base in (r"C:\Program Files\ODA", r"C:\Program Files (x86)\ODA"):
            for pattern in ("ODAFileConverter.exe", "TeighaFileConverter.exe"):
                candidates.extend(glob.glob(os.path.join(base, "*", pattern)))
    else:
        candidates.extend(LINUX_PATHS)
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def not_found_message():
    """Clear install instructions, printed when ODA is not installed."""
    lines = [
        "ODA File Converter was not found on this machine.",
        "",
        "This skill cannot read DWG files without it. Download it free from:",
        "  " + ODA_DOWNLOAD_URL,
        "",
        "Install it, then run this script again. Nothing is downloaded or",
        "installed automatically.",
        "",
    ]
    if sys.platform == "darwin":
        lines += [
            "macOS: open the downloaded .dmg and drag ODAFileConverter to",
            "  /Applications. The binary lives at:",
            "  /Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter",
        ]
    elif sys.platform.startswith("win"):
        lines += [
            "Windows: run the downloaded installer and accept the default",
            "  location under C:\\Program Files\\ODA.",
        ]
    else:
        lines += [
            "Linux: install the .deb or .rpm package from the download page, e.g.:",
            "  sudo dpkg -i ODAFileConverter_*.deb   (Debian/Ubuntu)",
            "  sudo rpm -i ODAFileConverter_*.rpm    (Fedora/RHEL)",
        ]
    lines += [
        "",
        "Note: ODA offers the converter free for non-commercial use to",
        "non-members. Check the terms on the download page.",
        "If it is installed somewhere unusual, pass its path with --oda.",
    ]
    return "\n".join(lines)


def run_oda(oda, in_dir, out_dir, version, recurse, audit, file_filter,
            timeout, verbose):
    """Run the ODA converter once. Returns the CompletedProcess, or None on failure.

    ODA takes seven positional arguments:
        inDir outDir outVer outFormat recurse audit [filter]
    """
    args = [
        oda,
        str(in_dir),
        str(out_dir),
        version,
        "DXF",
        "1" if recurse else "0",
        "1" if audit else "0",
        file_filter,
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        print("ODA File Converter timed out after %d seconds." % timeout,
              file=sys.stderr)
        return None
    if verbose:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print("ODA File Converter failed.", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return None
    return result


def convert(input_path, out_dir, version, recurse, audit, file_filter,
            oda, timeout, verbose):
    """Convert one file or a whole folder. Returns the DXF paths produced."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if input_path.is_file():
        # ODA works on folders, not single files, so stage a copy of the
        # one file in a temporary folder and convert that. The original
        # file is never touched.
        with tempfile.TemporaryDirectory(prefix="dwg-convert-") as tmp:
            staged = Path(tmp) / input_path.name
            shutil.copy2(input_path, staged)
            result = run_oda(oda, tmp, out_dir, version, False, audit,
                             input_path.name, timeout, verbose)
        if result is None:
            return []
        return [out_dir / (input_path.stem + ".dxf")]
    result = run_oda(oda, input_path, out_dir, version, recurse, audit,
                     file_filter, timeout, verbose)
    if result is None:
        return []
    return sorted(out_dir.rglob("*.dxf"))


def expected_stems(input_path, recurse):
    """The file stems a successful conversion must produce."""
    if input_path.is_file():
        return {input_path.stem}
    if recurse:
        files = input_path.rglob("*")
    else:
        files = input_path.iterdir()
    return {p.stem for p in files
            if p.is_file() and p.suffix.lower() == ".dwg"}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert DWG files to DXF with the free ODA File Converter.")
    parser.add_argument("input", nargs="?",
                        help="a .dwg file or a folder of .dwg files")
    parser.add_argument("--out-dir", default="converted",
                        help="output folder for the DXF files (default: ./converted)")
    parser.add_argument("--version", default=DEFAULT_VERSION,
                        help="output DXF version, e.g. ACAD2018 (default) or ACAD2013")
    parser.add_argument("--recurse", action="store_true",
                        help="descend into subfolders (folder input only)")
    parser.add_argument("--no-audit", dest="audit", action="store_false",
                        default=True,
                        help="skip the audit/repair pass (audit is on by default)")
    parser.add_argument("--filter", default=DEFAULT_FILTER,
                        help='input file filter (default: "*.DWG")')
    parser.add_argument("--oda", default=None,
                        help="explicit path to the ODAFileConverter binary")
    parser.add_argument("--timeout", type=int, default=600,
                        help="seconds to wait for the converter (default: 600)")
    parser.add_argument("--verbose", action="store_true",
                        help="print the converter's own output")
    parser.add_argument("--check", action="store_true",
                        help="only check whether ODA File Converter is installed")
    args = parser.parse_args(argv)

    oda = find_oda(args.oda)
    if args.check:
        if oda:
            print("ODA File Converter found: %s" % oda)
            return 0
        print(not_found_message(), file=sys.stderr)
        return 2
    if not args.input:
        parser.error("an input file or folder is required (or use --check)")
    if not oda:
        print(not_found_message(), file=sys.stderr)
        return 2

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print("Input not found: %s" % input_path, file=sys.stderr)
        return 2
    if input_path.is_file() and input_path.suffix.lower() != ".dwg":
        print("Input file is not a .dwg file: %s" % input_path, file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir).expanduser()
    if input_path.resolve() == out_dir.resolve():
        print("Input and output folders must be different.", file=sys.stderr)
        return 2

    produced = convert(input_path, out_dir, args.version, args.recurse,
                       args.audit, args.filter, oda, args.timeout, args.verbose)
    existing = [p for p in produced if p.is_file()]
    for path in existing:
        print("  converted: %s" % path)

    # ODA returns exit code 0 even when a single file fails, so verify
    # that every expected DXF actually exists instead of trusting it.
    produced_stems = {p.stem for p in existing}
    missing = sorted(expected_stems(input_path, args.recurse) - produced_stems)
    if missing:
        print("ODA reported success, but these files have no DXF output:",
              file=sys.stderr)
        for stem in missing:
            print("  missing: %s.dwg" % stem, file=sys.stderr)
        print("The file may be corrupt or use features the converter "
              "cannot handle.", file=sys.stderr)
        return 1
    print("Done: %d DXF file(s) in %s" % (len(existing), out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
