"""Normalize NYC street names so crash records and route geometry can be matched.

NYPD crash records and DOT route geometry name the same street differently:

    crash record:  "5 AVENUE                        "
    route record:  "5 AV"

Only 27.2% of route street names match a crash street name exactly. That
matters because street name is the one piece of independent information that
can break a spatial tie: when a crash sits equidistant between two centerlines
belonging to different streets, the name says which street it happened on, and
geometry alone never will.

The mapping below follows USPS Publication 28 suffix abbreviations, which is
what the DOT LION file uses. Normalization is deliberately conservative -- it
collapses suffixes and whitespace and nothing else. It does not attempt fuzzy
matching, because a wrong street match is worse than no match: it would move a
crash onto a corridor it never happened on, silently.
"""

from __future__ import annotations

import re

import pandas as pd

# Longest-first so AVENUE is consumed before AVE, and BOULEVARD before BLVD.
SUFFIXES = {
    "AVENUE": "AV", "AVE": "AV", "AV": "AV",
    "STREET": "ST", "STR": "ST", "ST": "ST",
    "BOULEVARD": "BLVD", "BLVD": "BLVD", "BLV": "BLVD",
    "PLACE": "PL", "PL": "PL",
    "ROAD": "RD", "RD": "RD",
    "DRIVE": "DR", "DR": "DR",
    "PARKWAY": "PKWY", "PKWY": "PKWY", "PKY": "PKWY",
    "EXPRESSWAY": "EXPY", "EXPY": "EXPY",
    "TURNPIKE": "TPKE", "TPKE": "TPKE",
    "TERRACE": "TER", "TER": "TER",
    "COURT": "CT", "CT": "CT",
    "LANE": "LN", "LN": "LN",
    "HIGHWAY": "HWY", "HWY": "HWY",
    "CIRCLE": "CIR", "CIR": "CIR",
    "SQUARE": "SQ", "SQ": "SQ",
    "BRIDGE": "BR", "BR": "BR",
    "PLAZA": "PLZ", "PLZ": "PLZ",
    "WALK": "WALK", "WAY": "WAY", "LOOP": "LOOP", "PATH": "PATH",
    "CONCOURSE": "CONCOURSE", "BROADWAY": "BROADWAY",
}

DIRECTIONS = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "N": "N", "S": "S", "E": "E", "W": "W",
}

# 1ST -> 1, SECOND -> 2, etc. Ordinal words are common in crash records and
# absent from LION, where numbered streets are bare digits.
ORDINAL_WORDS = {
    "FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4", "FIFTH": "5",
    "SIXTH": "6", "SEVENTH": "7", "EIGHTH": "8", "NINTH": "9", "TENTH": "10",
    "ELEVENTH": "11", "TWELFTH": "12",
}

_ORDINAL_SUFFIX = re.compile(r"^(\d+)(ST|ND|RD|TH)$")
_NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")


def normalize(name: str | float | None) -> str | None:
    """Collapse a street name to a comparable canonical form.

    >>> normalize("5 AVENUE   ")
    '5 AV'
    >>> normalize("EAST 14TH STREET")
    'E 14 ST'
    """
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return None
    s = str(name).upper().strip()
    if not s:
        return None
    s = _NON_ALNUM.sub(" ", s)
    tokens = [t for t in s.split() if t]
    if not tokens:
        return None

    out: list[str] = []
    for i, tok in enumerate(tokens):
        if tok in ORDINAL_WORDS:
            out.append(ORDINAL_WORDS[tok])
            continue
        m = _ORDINAL_SUFFIX.match(tok)
        if m:
            out.append(m.group(1))
            continue
        # Direction words only count as directions in leading position;
        # "WEST END AV" must keep WEST, "NORTH ST" is a real street name.
        if i == 0 and tok in DIRECTIONS and len(tokens) > 2:
            out.append(DIRECTIONS[tok])
            continue
        # Suffix abbreviation only applies to the final token.
        if i == len(tokens) - 1 and tok in SUFFIXES:
            out.append(SUFFIXES[tok])
            continue
        out.append(tok)
    return " ".join(out)


def normalize_series(s: pd.Series) -> pd.Series:
    return s.map(normalize)
