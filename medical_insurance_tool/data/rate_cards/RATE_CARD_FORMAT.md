# Rate Card Excel Format Guide

Place insurer Excel rate card files (`.xlsx` or `.xls`) in this folder.
The tool auto-detects the layout on load.

## Supported Layouts

### Layout 1 – Age-Band Matrix (most common)

| | Basic | Basic | Enhanced | Enhanced |
|---|---|---|---|---|
| **Age Band** | **Male** | **Female** | **Male** | **Female** |
| 0-17 | 650 | 750 | 900 | 1050 |
| 18-24 | 700 | 800 | 950 | 1100 |
| 25-29 | 750 | 870 | 1000 | 1160 |
| ... | | | | |

- Row 1: Plan names
- Row 2: Gender labels + "Age Band" in column A
- Remaining rows: age band in col A, premiums following

### Layout 2 – Member List

| Age | Gender | Plan | Annual Premium |
|---|---|---|---|
| 25 | Male | Basic | 720 |
| 35 | Female | Enhanced | 1150 |

- Header row with "age", "gender", "plan", "premium" columns (case-insensitive)

## Tips

- All premiums should be in AED (annual)
- File name is used as insurer name if not specified on upload
- Multiple plans can be in separate sheets — upload each sheet separately
- Run `python create_sample_rates.py` to generate sample files for testing
