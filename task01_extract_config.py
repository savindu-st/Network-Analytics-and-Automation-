#!/usr/bin/env python3
"""Task 01 - Extract sub-interface service details from Cisco and Huawei configs.

Reads every configuration file in a directory, detects the vendor from the
configuration content, extracts sub-interface details, and writes one Excel
workbook with the columns: Main Interface, Description, VRF, Vendor.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

SUPPORTED_SUFFIXES = {".txt", ".cfg", ".conf"}

# Distinctive keywords found in each vendor's CLI output. A config is
# classified by counting how many of these markers it contains. Using
# multiple markers (including the command prompt) is more reliable than
# relying on a single line.
VENDOR_SIGNATURES = {
    "Cisco": (
        "show running-config",
        "building configuration",
        "vrf definition",
        "vrf forwarding",
        "encapsulation dot1q",
    ),
    "Huawei": (
        "display current-configuration",
        "sysname ",
        "ip vpn-instance",
        "ip binding vpn-instance",
        "vlan-type dot1q",
    ),
}

# The CLI prompt is another strong vendor indicator:
#   Cisco  -> hostname#show ...
#   Huawei -> <hostname>display ...
PROMPT_SIGNATURES = {
    "Cisco": re.compile(r"^\s*[A-Za-z][\w.-]*#\s*\S", re.MULTILINE),
    "Huawei": re.compile(r"^\s*<[A-Za-z][\w.-]*>", re.MULTILINE),
}

INTERFACE_RE = re.compile(r"^interface\s+(\S+)\s*$", re.IGNORECASE)
SUBINTERFACE_RE = re.compile(r"^\S+\.\d+$")
DESCRIPTION_RE = re.compile(r"^description\s+(.+?)\s*$", re.IGNORECASE)
VRF_RE = re.compile(
    r"^(?:vrf forwarding|ip vrf forwarding|ip binding vpn-instance)[ \t]+(\S+)",
    re.IGNORECASE,
)

HEADERS = ("Main Interface", "Description", "VRF", "Vendor")


@dataclass(frozen=True)
class ServiceRecord:
    """One sub-interface row in the Excel report."""

    main_interface: str
    description: str
    vrf: str
    vendor: str


def detect_vendor(config: str) -> str | None:
    """Return 'Cisco' or 'Huawei' based on CLI signatures, or None if unclear."""
    text = config.lower()
    scores = {
        vendor: sum(text.count(marker) for marker in markers)
        + 2 * len(PROMPT_SIGNATURES[vendor].findall(config))
        for vendor, markers in VENDOR_SIGNATURES.items()
    }
    cisco_score = scores["Cisco"]
    huawei_score = scores["Huawei"]

    if cisco_score == huawei_score:
        return None
    return "Cisco" if cisco_score > huawei_score else "Huawei"


def iter_interface_blocks(config: str) -> Iterator[tuple[str, list[str]]]:
    """Yield (interface_name, body_lines) for each top-level interface block.

    Interface bodies are the indented lines that follow an ``interface``
    line. A non-indented line (for example ``!``, ``return`` or the next
    ``interface``) closes the current block.
    """
    current_name: str | None = None
    current_body: list[str] = []

    for line in config.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if line[0].isspace():
            if current_name is not None:
                current_body.append(stripped)
            continue

        # A new top-level line always closes the previous interface block.
        if current_name is not None:
            yield current_name, current_body
            current_name, current_body = None, []

        match = INTERFACE_RE.match(stripped)
        if match:
            current_name = match.group(1)

    if current_name is not None:
        yield current_name, current_body


def first_group(pattern: re.Pattern[str], lines: Iterable[str]) -> str:
    """Return the first captured group matching pattern, or an empty string."""
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1)
    return ""


def parse_config(config: str, vendor: str) -> list[ServiceRecord]:
    """Extract description and VRF from every sub-interface in the config."""
    records: list[ServiceRecord] = []

    for interface, body in iter_interface_blocks(config):
        if not SUBINTERFACE_RE.match(interface):
            continue  # Only sub-interfaces are in scope.

        records.append(
            ServiceRecord(
                main_interface=interface,
                description=first_group(DESCRIPTION_RE, body),
                vrf=first_group(VRF_RE, body),
                vendor=vendor,
            )
        )

    return records


def extract_from_file(path: Path) -> list[ServiceRecord]:
    """Read and parse one config file. Return an empty list if it is skipped."""
    try:
        config = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        print(f"  [WARN] Cannot read {path.name}: {exc}", file=sys.stderr)
        return []

    if not config.strip():
        print(f"  [WARN] Skipping empty file: {path.name}", file=sys.stderr)
        return []

    vendor = detect_vendor(config)
    if vendor is None:
        print(
            f"  [WARN] Skipping {path.name}: vendor is not recognisable as Cisco or Huawei.",
            file=sys.stderr,
        )
        return []

    records = parse_config(config, vendor)
    if not records:
        print(
            f"  [WARN] No sub-interfaces found in {path.name} (vendor: {vendor}).",
            file=sys.stderr,
        )
    return records


def collect_config_files(directory: Path) -> list[Path]:
    """Return supported config files in deterministic (name) order."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def write_workbook(records: list[ServiceRecord], output_path: Path) -> None:
    """Write all records to a formatted .xlsx workbook."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Service Details"

    sheet.append(HEADERS)

    for record in records:
        sheet.append(
            [
                record.main_interface,
                record.description or "N/A",
                record.vrf or "N/A",
                record.vendor,
            ]
        )

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    for column, width in zip("ABCD", (30, 42, 24, 12)):
        sheet.column_dimensions[column].width = width

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract sub-interface details from Cisco/Huawei configs into Excel."
    )
    parser.add_argument(
        "--configs",
        type=Path,
        default=Path("configs"),
        help="Directory containing .txt/.cfg/.conf files (default: configs).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/service_details.xlsx"),
        help="Output .xlsx path (default: output/service_details.xlsx).",
    )
    args = parser.parse_args()

    if not args.configs.is_dir():
        print(f"Error: config directory not found: {args.configs}", file=sys.stderr)
        return 1

    config_files = collect_config_files(args.configs)
    if not config_files:
        print(f"Warning: no supported config files in {args.configs}", file=sys.stderr)

    all_records: list[ServiceRecord] = []
    for path in config_files:
        print(f"Processing {path.name} ...")
        all_records.extend(extract_from_file(path))

    write_workbook(all_records, args.output)
    print(f"\nWrote {len(all_records)} record(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
