# -*- coding: utf-8 -*-
"""
Module 10 — Post-Load Geological Sanity Checks
===============================================
After drill data is loaded, checks whether the selected deposit preset
matches the detected rock type distribution. Flags mismatches for user review.
Pure Python, no QGIS imports.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class SanityWarning:
    severity: str    # 'info' | 'warning' | 'critical'
    category: str    # 'lithology' | 'geometry' | 'data'
    message: str     # what was detected
    suggestion: str  # what the user should do
    actions: List[str] = None  # suggested UI actions

    def __post_init__(self):
        if self.actions is None:
            self.actions = []


def check_deposit_type_match(cfg, litho_df) -> List[SanityWarning]:
    """
    Check if the selected deposit_type matches the lithology composition.
    Returns list of warnings (empty if data looks consistent with preset).
    """
    warnings = []
    if litho_df is None or len(litho_df) == 0:
        return warnings

    # Compute lithology fractions
    if 'lcode' not in litho_df.columns:
        return warnings
    counts = litho_df['lcode'].value_counts(normalize=True)

    deposit = cfg.deposit_type or ''

    if 'SEDEX' in deposit.upper() or 'Pb-Zn' in deposit:
        # Expect >40% host (code 1 QMS) + (code 4 CSR)
        host_frac = counts.get(1, 0) + counts.get(4, 0)
        felsic_frac = counts.get(5, 0)
        volcanic_mafic = counts.get(2, 0)

        if host_frac < 0.30:
            warnings.append(SanityWarning(
                severity='warning',
                category='lithology',
                message=f"Your drill data shows {100*host_frac:.0f}% sediment host rocks "
                        f"(QMS/CSR). SEDEX deposits typically have >60% sediment host.",
                suggestion="Your deposit may not be SEDEX — consider a different preset, "
                           "or check your rock code mapping.",
                actions=['Switch preset', 'Remap rock codes', 'Continue anyway'],
            ))
        if felsic_frac > 0.40:
            warnings.append(SanityWarning(
                severity='warning',
                category='lithology',
                message=f"Your data contains {100*felsic_frac:.0f}% felsic volcanic rocks — "
                        f"SEDEX deposits are hosted in sediments, not volcanics.",
                suggestion="This looks more like VMS. Consider switching to the VMS Cu-Zn preset.",
                actions=['Switch to VMS preset', 'Continue anyway'],
            ))

    elif 'VMS' in deposit.upper() or 'Cu-Zn' in deposit:
        # Expect >20% felsic volcanic (code 5)
        felsic_frac = counts.get(5, 0)
        host_frac = counts.get(1, 0) + counts.get(4, 0)

        if felsic_frac < 0.15:
            warnings.append(SanityWarning(
                severity='warning',
                category='lithology',
                message=f"Only {100*felsic_frac:.0f}% felsic volcanic detected. "
                        f"VMS deposits are typically hosted in felsic-dominated "
                        f"volcanic sequences.",
                suggestion="Check rock code mapping — felsic volcanic should map to code 5. "
                           "If your deposit is not VMS, consider a different preset.",
                actions=['Remap rock codes', 'Switch preset', 'Continue anyway'],
            ))
        if host_frac > 0.60:
            warnings.append(SanityWarning(
                severity='warning',
                category='lithology',
                message=f"Your data is {100*host_frac:.0f}% sediment — unusual for VMS.",
                suggestion="This might be a SEDEX deposit. Consider the SEDEX Pb-Zn preset.",
                actions=['Switch to SEDEX preset', 'Continue anyway'],
            ))

    elif 'EPITHERMAL' in deposit.upper() or 'Au' in deposit:
        # Epithermal expects silicified zone (code 3) or veins
        struct_frac = counts.get(3, 0)
        if struct_frac < 0.10:
            warnings.append(SanityWarning(
                severity='info',
                category='lithology',
                message=f"Only {100*struct_frac:.0f}% silicified/structural zone detected. "
                        f"Epithermal deposits typically have obvious silicification or vein material.",
                suggestion="Check that your vein/silicified rocks are mapped to code 3, "
                           "or that they are logged in your drill database.",
                actions=['Remap rock codes', 'Continue anyway'],
            ))

    elif 'PORPHYRY' in deposit.upper():
        # Porphyry expects intrusive body (code 3)
        intrusive_frac = counts.get(3, 0)
        if intrusive_frac < 0.10:
            warnings.append(SanityWarning(
                severity='warning',
                category='lithology',
                message=f"Only {100*intrusive_frac:.0f}% intrusive rock detected. "
                        f"Porphyry deposits require a mineralised intrusive body.",
                suggestion="Check that your intrusive/porphyry is logged and mapped to code 3.",
                actions=['Remap rock codes', 'Switch preset', 'Continue anyway'],
            ))

    return warnings


def check_unknown_rock_fraction(cfg, litho_df, threshold: float = 0.10) -> List[SanityWarning]:
    """Warn if a significant fraction of litho intervals have unknown rock codes (lcode=0)."""
    warnings = []
    if litho_df is None or len(litho_df) == 0 or 'lcode' not in litho_df.columns:
        return warnings

    unknown = (litho_df['lcode'] == 0).sum()
    total = len(litho_df)
    frac = unknown / total if total > 0 else 0

    if frac > threshold:
        warnings.append(SanityWarning(
            severity='warning',
            category='lithology',
            message=f"{100*frac:.0f}% of litho intervals have unknown rock codes ({unknown} of {total}). "
                    f"These will get default scores (0.25), reducing map accuracy.",
            suggestion="Check your rock_codes dict in the config. Every rock type in your CSV "
                       "should be listed.",
            actions=['Edit rock codes', 'Continue anyway'],
        ))

    return warnings


def run_all_sanity_checks(cfg, litho_df) -> List[SanityWarning]:
    """Run all sanity checks. Returns combined list."""
    warnings = []
    warnings.extend(check_deposit_type_match(cfg, litho_df))
    warnings.extend(check_unknown_rock_fraction(cfg, litho_df))
    return warnings
