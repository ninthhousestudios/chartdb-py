"""
Computed chart properties — categorical features extracted at import time.

Stored as (chart_id, subject, property, value) rows in an EAV table.
Queryable by exact match and composable via intersection.

Properties extracted per graha:
    sign, house, nakshatra, dignity, retrograde,
    baladi, jagradadi, deeptadi, shayanadi, lajjitaadi

Properties extracted for lagna:
    sign, nakshatra
"""

GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

TRIMSAMSA_BEINGS = ["Gandharva", "Rakshasa", "Rishi", "Yaksha", "Apsara"]
TRIMSAMSA_LORDS_ODD = ["Mars", "Saturn", "Jupiter", "Mercury", "Venus"]
TRIMSAMSA_LORDS_EVEN = ["Venus", "Mercury", "Jupiter", "Saturn", "Mars"]


def _trimsamsa_index(degree_in_sign: float, is_odd: bool) -> int:
    """Return 0-4 index into the trimsamsa being/lord arrays."""
    if is_odd:
        if degree_in_sign < 5: return 0
        if degree_in_sign < 10: return 1
        if degree_in_sign < 18: return 2
        if degree_in_sign < 25: return 3
        return 4
    else:
        if degree_in_sign < 5: return 0
        if degree_in_sign < 12: return 1
        if degree_in_sign < 20: return 2
        if degree_in_sign < 25: return 3
        return 4


def trimsamsa_being(degree_in_sign: float, is_odd: bool) -> str:
    idx = _trimsamsa_index(degree_in_sign, is_odd)
    if is_odd:
        return TRIMSAMSA_BEINGS[idx]
    return TRIMSAMSA_BEINGS[4 - idx]


def trimsamsa_lord(degree_in_sign: float, is_odd: bool) -> str:
    idx = _trimsamsa_index(degree_in_sign, is_odd)
    if is_odd:
        return TRIMSAMSA_LORDS_ODD[idx]
    return TRIMSAMSA_LORDS_EVEN[idx]

SCHEMA_SQL = """
    create table if not exists chart_properties (
        chart_id text not null references charts(id) on delete cascade,
        subject  text not null,
        property text not null,
        value    text not null
    );

    create index if not exists idx_props_lookup
        on chart_properties(property, value);
    create index if not exists idx_props_chart
        on chart_properties(chart_id);
    create index if not exists idx_props_composite
        on chart_properties(property, subject, value);
"""


def extract_properties(chart) -> list[tuple[str, str, str]]:
    """Extract (subject, property, value) triples from a calculated Chart."""
    props = []
    rashi = chart.rashi()
    grahas = rashi.planets().grahas()

    for name in GRAHAS:
        planet = grahas[name]

        props.append((name, "sign", str(planet.sign())))
        props.append((name, "sign_name", planet.sign_name()))

        house = int(rashi.house_position(name))
        props.append((name, "house", str(house)))

        nak = planet.nakshatra()
        props.append((name, "nakshatra", nak.nakshatra()))
        props.append((name, "nakshatra_index", str(nak.index())))

        dignity = planet.attributes.get("dignity", "")
        if dignity:
            props.append((name, "dignity", dignity))

        props.append((name, "retrograde", str(planet.long_speed < 0)))

        for avastha_type in ("baladi_avastha", "jagradadi_avastha", "deeptadi_avastha", "shayanadi_avastha"):
            val = planet.attributes.get(avastha_type, "")
            if val:
                props.append((name, avastha_type, val))

        for avastha_name, sources in planet.attributes.get("lajjitaadi_avasthas", {}).items():
            props.append((name, "lajjitaadi", avastha_name))
            for src in sources:
                causing = src.get("planet", "") or src.get("lord", "")
                if causing:
                    props.append((name, "lajjitaadi_by", f"{avastha_name}:{causing}"))
                source_type = src.get("source", "")
                if source_type and causing:
                    mechanism = source_type
                    if source_type == "aspect":
                        strength = src.get("strength", 0)
                        mechanism = "aspect<30" if strength < 30 else "aspect>=30"
                    props.append((name, "lajjitaadi_via", f"{avastha_name}:{causing}:{mechanism}"))

        degree_in_sign = planet.long % 30
        is_odd = int(planet.sign()) % 2 == 1
        props.append((name, "trimsamsa_being", trimsamsa_being(degree_in_sign, is_odd)))
        props.append((name, "trimsamsa_lord", trimsamsa_lord(degree_in_sign, is_odd)))

    lagna = rashi.cusps().cusps[0]
    props.append(("Lagna", "sign", str(lagna.sign())))
    props.append(("Lagna", "sign_name", lagna.sign_name()))
    props.append(("Lagna", "nakshatra", lagna.nakshatra().nakshatra()))

    return props
