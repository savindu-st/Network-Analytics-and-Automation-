# Network Automation Internship – Evaluation Assignment

Solution for the Dialog Enterprise network automation assignment.

- **Task 01:** Reads Cisco and Huawei router configurations, detects the vendor automatically, extracts sub-interface service details, and writes them to a single Excel workbook.
- **Task 02:** A prompt for an ISP network troubleshooting AI agent.

## Project structure

```
.
├── README.md
├── requirements.txt
├── task01_extract_config.py     # Task 01 script
├── task02_prompt.md             # Task 02 prompt
├── configs/
│   ├── router_a.txt             # Cisco sample configuration
│   └── router_b.txt             # Huawei sample configuration
└── output/
    └── service_details.xlsx     # Generated Excel output
```

## Requirements

- Python 3.9 or newer
- `openpyxl` (see `requirements.txt`)

## Setup and run

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python task01_extract_config.py
```

The script uses these defaults:

- Input directory: `configs/`
- Output file: `output/service_details.xlsx`

Both can be overridden:

```bash
python task01_extract_config.py --configs /path/to/configs --output /path/to/report.xlsx
```

Supported input extensions are `.txt`, `.cfg`, and `.conf`. Every supported file in the input directory is processed and all records are written to one workbook.

## Expected output

Sheet name: `Service Details`

| Main Interface | Description | VRF | Vendor |
|---|---|---|---|
| GigabitEthernet0/0/0.100 | CUST_ALPHA_SERVICE_455023849 | CUSTOMER_ALPHA | Cisco |
| GigabitEthernet0/0/0.200 | CUST_BETA_SERVICE_452397680 | CUSTOMER_BETA | Cisco |
| GigabitEthernet0/0/1.300 | CUST_GAMMA_SERVICE_298765432 | CUSTOMER_GAMMA | Huawei |
| GigabitEthernet0/0/1.400 | CUST_DELTA_SERVICE_099876543 | CUSTOMER_DELTA | Huawei |

## How vendor detection works

The vendor is derived from the configuration content, never from the filename. The script counts distinctive CLI markers for each vendor and selects the highest score:

- **Cisco:** `show running-config`, `Building configuration`, `vrf definition`, `vrf forwarding`, `encapsulation dot1Q`
- **Huawei:** `display current-configuration`, `sysname`, `ip vpn-instance`, `ip binding vpn-instance`, `vlan-type dot1q`

Matching the command prompt alone would be fragile; combining the prompt with vendor-specific configuration keywords makes the detection reliable. If the score is zero or tied, the file is reported as unrecognisable and skipped with a warning instead of being mislabelled.

## Parsing assumptions

- Only **sub-interfaces** are extracted. An interface counts as a sub-interface when its name ends in `.` followed by digits (for example `GigabitEthernet0/0/0.100`). Physical and loopback interfaces are ignored.
- An interface block consists of a top-level `interface ...` line followed by indented configuration lines, as in both sample configurations.
- **Description** comes from `description <text>`.
- **VRF** comes from:
  - Cisco: `vrf forwarding <name>` (legacy `ip vrf forwarding <name>` is also supported)
  - Huawei: `ip binding vpn-instance <name>`
- If a sub-interface has no description or no VRF, the value `N/A` is written so that the row is not lost.
- Blank lines, comments, unknown keywords, and non-interface sections are ignored safely.

## Error handling

The script handles bad input without crashing:

- Missing input directory → clear error message, exit code 1.
- Empty or unreadable file → warning, file skipped.
- Unknown vendor → warning, file skipped.
- No sub-interfaces in a recognised file → warning; the workbook is still generated.
- No extractable records at all → a valid workbook containing only the header row is generated.

## Task 02

The troubleshooting-agent prompt is in [`task02_prompt.md`](task02_prompt.md). It defines the agent's role, scope, protocol expertise, vendor command equivalents, troubleshooting methodology, safety rules, and response format. It includes input placeholders for vendor/platform, topology, symptoms, recent changes, and available evidence.

## Notes

- The sample configuration files were copied from the assignment appendix.
- The generated workbook is included in `output/` and can be regenerated with the command above.
- No network devices are contacted; the script works entirely from configuration files on disk.
