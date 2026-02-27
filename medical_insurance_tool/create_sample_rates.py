"""
Script to generate sample Excel rate cards for testing.
Run once: python create_sample_rates.py
"""

import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import RATE_CARDS_DIR

AGE_BANDS = [
    "0-17", "18-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70+",
]


def create_insurer_a():
    """Age-band matrix layout — basic and enhanced plans."""
    # Build the header rows then data rows
    data = []

    # Row 0: Plan names (column headers)
    plan_row = ["", "Basic", "Basic", "Enhanced", "Enhanced", "Comprehensive", "Comprehensive"]
    data.append(plan_row)

    # Row 1: Gender sub-headers + Age band label
    gender_row = ["Age Band", "Male", "Female", "Male", "Female", "Male", "Female"]
    data.append(gender_row)

    # Base rates per band
    base = {
        "Basic":         [650, 700, 750, 820, 900, 1050, 1250, 1600, 2100, 2800, 3700, 5200],
        "Enhanced":      [900, 950, 1000, 1100, 1250, 1450, 1750, 2200, 2900, 3800, 5000, 7000],
        "Comprehensive": [1400, 1500, 1600, 1750, 1950, 2300, 2750, 3500, 4600, 6000, 7800, 10500],
    }
    female_loading = 1.15  # women 15% higher (maternity loading)

    for i, band in enumerate(AGE_BANDS):
        row = [band]
        for plan in ["Basic", "Enhanced", "Comprehensive"]:
            male_p = base[plan][i]
            female_p = round(male_p * female_loading)
            row.extend([male_p, female_p])
        data.append(row)

    df = pd.DataFrame(data)
    path = RATE_CARDS_DIR / "Insurer_A_Rates.xlsx"
    df.to_excel(path, index=False, header=False, sheet_name="Rates")
    print(f"Created: {path}")


def create_insurer_b():
    """Alternative insurer with slightly different layout."""
    data = []

    plan_row = ["", "Economy", "Economy", "Silver", "Silver", "Gold", "Gold", "Platinum", "Platinum"]
    data.append(plan_row)

    gender_row = ["Age Band", "Male", "Female", "Male", "Female", "Male", "Female", "Male", "Female"]
    data.append(gender_row)

    base = {
        "Economy":  [620, 680, 720, 790, 870, 1020, 1200, 1550, 2000, 2650, 3500, 4900],
        "Silver":   [850, 910, 960, 1060, 1200, 1400, 1680, 2100, 2750, 3600, 4750, 6600],
        "Gold":     [1300, 1400, 1500, 1650, 1850, 2180, 2600, 3300, 4350, 5700, 7400, 9900],
        "Platinum": [2000, 2150, 2300, 2500, 2800, 3300, 3950, 5000, 6600, 8700, 11300, 15000],
    }
    female_loading = 1.12

    for i, band in enumerate(AGE_BANDS):
        row = [band]
        for plan in ["Economy", "Silver", "Gold", "Platinum"]:
            m = base[plan][i]
            f = round(m * female_loading)
            row.extend([m, f])
        data.append(row)

    df = pd.DataFrame(data)
    path = RATE_CARDS_DIR / "Insurer_B_Rates.xlsx"
    df.to_excel(path, index=False, header=False, sheet_name="Rates")
    print(f"Created: {path}")


def create_dha_compliant():
    """DHA Basic plan (Abu Dhabi / Dubai minimum compliance)."""
    data = []
    data.append(["", "DHA Basic", "DHA Basic"])
    data.append(["Age Band", "Male", "Female"])

    dha_base = [650, 680, 710, 760, 830, 950, 1100, 1380, 1780, 2350, 3100, 4400]
    fl = 1.18

    for i, band in enumerate(AGE_BANDS):
        m = dha_base[i]
        f = round(m * fl)
        data.append([band, m, f])

    df = pd.DataFrame(data)
    path = RATE_CARDS_DIR / "DHA_Basic_Compliant_Rates.xlsx"
    df.to_excel(path, index=False, header=False, sheet_name="DHA Basic")
    print(f"Created: {path}")


if __name__ == "__main__":
    create_insurer_a()
    create_insurer_b()
    create_dha_compliant()
    print("\nSample rate cards created in:", RATE_CARDS_DIR)
    print("Run `streamlit run main.py` to start the tool.")
