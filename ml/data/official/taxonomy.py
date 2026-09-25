"""Crime heads exactly as they appear in the official Brihan Mumbai statement.

Each head keeps its printed label (``label_official``) and an expansion of the
official abbreviation (``label``, e.g. "H.B.T.Day" -> "House Breaking Theft - Day").
Codes are stable identifiers used across the platform; they never replace the
official terminology in the UI.

``match`` is a regular expression the extractor uses to confirm that the row it
parsed really is this head, so a change in the PDF layout fails loudly instead of
silently mislabelling numbers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OfficialHead:
    code: str
    section: str
    label_official: str
    label: str
    match: str
    parent: str | None = None
    is_total: bool = False
    legal_reference: str | None = None


@dataclass(frozen=True)
class OfficialSection:
    id: str
    title: str
    page: int
    heads: tuple[OfficialHead, ...]


def _h(code, section, label_official, label, match, **kw) -> OfficialHead:
    return OfficialHead(code, section, label_official, label, match, **kw)


IPC_HEADS: tuple[OfficialHead, ...] = (
    _h("MURDER", "IPC", "Murder", "Murder", r"^Murder$"),
    _h(
        "ATTEMPT_TO_MURDER",
        "IPC",
        "Att.to.C.Murder",
        "Attempt to Commit Murder",
        r"^Att\.?\s*to\.?\s*C\.?\s*Murder",
    ),
    _h("DACOITY", "IPC", "Dacoity", "Dacoity", r"^Dacoity$"),
    _h(
        "PREPARATION_FOR_DACOITY",
        "IPC",
        "Prep.for Dacoity",
        "Preparation for Dacoity",
        r"^Prep\.?\s*for\s*Dacoity",
    ),
    _h("ROBBERY", "IPC", "Robbery", "Robbery", r"^Robbery$"),
    _h(
        "ROBBERY_CHAIN_SNATCHING",
        "IPC",
        "Robbery Chain Snatching",
        "Robbery Chain Snatching",
        r"^Robbery\s+Chain\s+Snatching",
    ),
    _h(
        "ATTEMPT_TO_ROBBERY",
        "IPC",
        "Att.to.C.Robbery",
        "Attempt to Commit Robbery",
        r"^Att\.?\s*to\.?\s*C\.?\s*Robbery",
    ),
    _h("EXTORTION", "IPC", "Extortion", "Extortion", r"^Extortion"),
    _h("HBT_DAY", "IPC", "H.B.T.Day", "House Breaking Theft - Day", r"^H\.?B\.?T\.?\s*Day"),
    _h(
        "HBT_NIGHT", "IPC", "H.B.T.Night.", "House Breaking Theft - Night", r"^H\.?B\.?T\.?\s*Night"
    ),
    _h("THEFT", "IPC", "Thefts.", "Thefts", r"^Thefts?\.?$"),
    _h("MV_THEFT", "IPC", "M.V.Thefts.", "Motor Vehicle Thefts", r"^M\.?V\.?\s*Thefts"),
    _h("SNATCHING", "IPC", "Snatching", "Snatching", r"^Snatching$"),
    _h("HURT", "IPC", "Hurt", "Hurt", r"^Hurt$"),
    _h("RIOTS", "IPC", "Riots.", "Riots", r"^Riots\.?$"),
    _h("RAPE", "IPC", "Rape", "Rape", r"^Rape$"),
    _h(
        "SEXUAL_OFFENCES_SEC69",
        "IPC",
        "Sexual Offences (Sec 69 BNS -only Mejor)",
        "Sexual Offences (Sec 69 BNS, only Major)",
        r"^Sexual\s+Offences",
        legal_reference="Sec 69 BNS",
    ),
    _h("MOLESTATION", "IPC", "Molestation", "Molestation", r"^Molestation$"),
    _h("OTHER_IPC", "IPC", "Other I.P.C.", "Other IPC", r"^Other\s+I\.?P\.?C"),
    _h("TOTAL_IPC", "IPC", "Total IPC", "Total IPC", r"^Total\s+IPC", is_total=True),
)

CAW_HEADS: tuple[OfficialHead, ...] = (
    _h(
        "CAW_RAPE_POCSO_MINOR",
        "CAW",
        "Rape u/s (Sec. 64 (1), 65 (2), 66, 67, 68, 69 70 & 71 BNS R/w POCSO (ii) Minor",
        "Rape r/w POCSO - Minor",
        r"^Rape\s+u/s.*POCSO.*Minor",
        parent="CAW_RAPE_TOTAL",
        legal_reference="Sec. 64(1), 65(2), 66, 67, 68, 69, 70 & 71 BNS r/w POCSO",
    ),
    _h(
        "CAW_RAPE_MAJOR",
        "CAW",
        "(Sec. 64 (1), 65 (2), 66, 67, 68, 69 70 & 71 BNS ) (ii) Major",
        "Rape - Major",
        r"^\(Sec\. 64.*Major",
        parent="CAW_RAPE_TOTAL",
        legal_reference="Sec. 64(1), 65(2), 66, 67, 68, 69, 70 & 71 BNS",
    ),
    _h(
        "CAW_RAPE_TOTAL",
        "CAW",
        "Total Rape Cases",
        "Total Rape Cases",
        r"^Total\s+Rape\s+Cases",
        is_total=True,
    ),
    _h(
        "CAW_SEXUAL_OFFENCES_SEC69",
        "CAW",
        "Sexual Offences (Sec 69 BNS -only Mejor)",
        "Sexual Offences (Sec 69 BNS, only Major)",
        r"^Sexual\s+Offences",
        legal_reference="Sec 69 BNS",
    ),
    _h(
        "CAW_KIDNAPPING_MINOR",
        "CAW",
        "Kidnapping of Women (Sec. 87, 96, 97, 137 (2), 139 (1), (2), 140 (1), (2), (3), (4), "
        "141 & 142 BNS) (i) Minor",
        "Kidnapping of Women - Minor",
        r"^Kidnapping\s+of\s+Women.*Minor",
        parent="CAW_KIDNAPPING_TOTAL",
        legal_reference="Sec. 87, 96, 97, 137(2), 139(1),(2), 140(1)-(4), 141 & 142 BNS",
    ),
    _h(
        "CAW_KIDNAPPING_MAJOR",
        "CAW",
        "(Sec. 87, 96, 97, 137 (2), 139 (1), (2), 140 (1), (2), (3), (4), 141 & 142 BNS) "
        "(ii) Major",
        "Kidnapping of Women - Major",
        r"^\(Sec\. 87.*Major",
        parent="CAW_KIDNAPPING_TOTAL",
        legal_reference="Sec. 87, 96, 97, 137(2), 139(1),(2), 140(1)-(4), 141 & 142 BNS",
    ),
    _h(
        "CAW_KIDNAPPING_TOTAL",
        "CAW",
        "Total Kidnapping Cases",
        "Total Kidnapping Cases",
        r"^Total\s+Kidnapping\s+Cases",
        is_total=True,
    ),
    _h(
        "CAW_OUTRAGING_MODESTY",
        "CAW",
        "Outraging Modesty of Women (u/s 354 IPC /74 , 75, 76, 77, 78 BNS)",
        "Outraging Modesty of Women",
        r"^Outraging\s+Modesty",
        legal_reference="354 IPC / 74, 75, 76, 77, 78 BNS",
    ),
    _h(
        "CAW_INSULT_TO_MODESTY",
        "CAW",
        "Intended insult to Modesty of Women (u/s 509 IPC. / u/s 79 BNS)",
        "Intended Insult to Modesty of Women",
        r"^Intended\s+insult",
        legal_reference="509 IPC / 79 BNS",
    ),
    _h(
        "CAW_DOWRY_PROHIBITION_ACT",
        "CAW",
        "Dowry Prohibition Act.",
        "Dowry Prohibition Act",
        r"^Dowry\s+Prohibition\s+Act",
    ),
    _h(
        "CAW_DOWRY_MURDER",
        "CAW",
        "(a) Dowry related murder (u/s 302 IPC / u/s 103 (1) BNS)",
        "Dowry Related Murder",
        r"^\(a\)\s*Dowry\s+related\s+murder",
        legal_reference="302 IPC / 103(1) BNS",
    ),
    _h(
        "CAW_DOWRY_DEATH",
        "CAW",
        "(b) Dowry Death (u/s 304-B IPC / u/s 80 (2) BNS)",
        "Dowry Death",
        r"^\(b\)\s*Dowry\s+Death",
        legal_reference="304-B IPC / 80(2) BNS",
    ),
    _h(
        "CAW_DOWRY_SUICIDE",
        "CAW",
        "(C) Dowry related suicides (u/s 306 IPC / u/s 108 BNS)",
        "Dowry Related Suicides",
        r"^\(C\)\s*Dowry\s+related\s+suicides",
        legal_reference="306 IPC / 108 BNS",
    ),
    _h(
        "CAW_DOWRY_HARASSMENT",
        "CAW",
        "(D) Dowry related Mental/Phy. Harrasment ( 498-A IPC/ 85 BNS)",
        "Dowry Related Mental/Physical Harassment",
        r"^\(D\)\s*Dowry\s+related\s+Mental",
        legal_reference="498-A IPC / 85 BNS",
    ),
    _h(
        "CAW_MURDER_OTHER_REASONS",
        "CAW",
        "(a) Murder due to other reasons (u/s 302 IPC / u/s 103 (1) BNS)",
        "Murder due to Other Reasons",
        r"^\(a\)\s*Murder\s+due\s+to\s+other",
        legal_reference="302 IPC / 103(1) BNS",
    ),
    _h(
        "CAW_SUICIDE_OTHER_REASONS",
        "CAW",
        "(b) Suicides due to other reasons (u/s 306 IPC / u/s 108 BNS)",
        "Suicides due to Other Reasons",
        r"^\(b\)\s*Suicides\s+due\s+to\s+other",
        legal_reference="306 IPC / 108 BNS",
    ),
    _h(
        "CAW_HARASSMENT_OTHER_REASONS",
        "CAW",
        "(c) Mental/Phy. Harrast. due to other reasons (498-A IPC/85 BNS)",
        "Mental/Physical Harassment due to Other Reasons",
        r"^\(c\)\s*Mental/Phy",
        legal_reference="498-A IPC / 85 BNS",
    ),
    _h(
        "CAW_ACID_ATTACK",
        "CAW",
        "Acid Attack (u/s 326A IPC / u/s 124 (1) BNS))",
        "Acid Attack",
        r"^Acid\s+Attack",
        legal_reference="326A IPC / 124(1) BNS",
    ),
    _h(
        "CAW_POCSO_RAPE",
        "CAW",
        "No of cases registered Rape with POCSO",
        "Cases Registered: Rape with POCSO",
        r"Rape\s+with\s+POCSO",
    ),
    _h(
        "CAW_POCSO_MOLESTATION",
        "CAW",
        "No. of cases registered Molestation with POCSO",
        "Cases Registered: Molestation with POCSO",
        r"Molestation\s+with\s+POCSO",
    ),
    _h(
        "CAW_POCSO_EVE_TEASING",
        "CAW",
        "No. of cases registered Eve-Teasing with POCSO",
        "Cases Registered: Eve-Teasing with POCSO",
        r"Eve-Teasing\s+with\s+POCSO",
    ),
    _h(
        "CAW_POCSO_OTHER_IPC",
        "CAW",
        "Other IPC with POCSO",
        "Other IPC with POCSO",
        r"^Other\s+IPC\s+with\s+POCSO",
    ),
    _h(
        "CAW_PITA_POCSO",
        "CAW",
        "PITA With POCSO (Excluding Rape)",
        "PITA with POCSO (Excluding Rape)",
        r"^PITA\s+With\s+POCSO",
    ),
    _h(
        "CAW_TOTAL",
        "CAW",
        "Total Crime Against Women (excl. col. 9.1,9.2 to 9.4)",
        "Total Crime Against Women (excl. col. 9.1, 9.2 to 9.4)",
        r"^Total\s+Crime\s+Against\s+Women",
        is_total=True,
    ),
)

NDPS_HEADS: tuple[OfficialHead, ...] = (
    _h("NDPS_HEROIN", "NDPS", "Heroin", "Heroin", r"^Heroin$", parent="NDPS_POSSESSION_TOTAL"),
    _h("NDPS_CHARAS", "NDPS", "Charas", "Charas", r"^Charas$", parent="NDPS_POSSESSION_TOTAL"),
    _h("NDPS_COCAINE", "NDPS", "Cocaine", "Cocaine", r"^Cocaine$", parent="NDPS_POSSESSION_TOTAL"),
    _h("NDPS_GANJA", "NDPS", "Ganja", "Ganja", r"^Ganja$", parent="NDPS_POSSESSION_TOTAL"),
    _h("NDPS_MD", "NDPS", "MD", "MD", r"^MD$", parent="NDPS_POSSESSION_TOTAL"),
    _h(
        "NDPS_OTHER_DRUGS",
        "NDPS",
        "Other Drugs",
        "Other Drugs",
        r"^Other\s+Drugs$",
        parent="NDPS_POSSESSION_TOTAL",
    ),
    _h(
        "NDPS_COUGH_SYRUP",
        "NDPS",
        "Cough Syrup (All types)",
        "Cough Syrup (All Types)",
        r"^Cough\s+Syrup",
        parent="NDPS_POSSESSION_TOTAL",
    ),
    _h(
        "NDPS_POSSESSION_TOTAL",
        "NDPS",
        "Total Possession Cases",
        "Total Possession Cases",
        r"^Total\s+Possession\s+Cases",
        parent="NDPS_TOTAL",
        is_total=True,
    ),
    _h(
        "NDPS_CONSUMPTION",
        "NDPS",
        "Consumption Cases",
        "Consumption Cases",
        r"^Consumption\s+Cases",
        parent="NDPS_TOTAL",
    ),
    _h(
        "NDPS_TOTAL",
        "NDPS",
        "Total NDPS Cases",
        "Total NDPS Cases",
        r"^Total\s+NDPS\s+Cases",
        is_total=True,
    ),
)

BROTHEL_HEADS: tuple[OfficialHead, ...] = (
    _h(
        "BROTHEL_CASES",
        "BROTHELS",
        "TOTAL CASES ON BROTHELS",
        "Total Cases on Brothels",
        r"CASES\s+ON\s+BROTHELS",
    ),
    _h(
        "BROTHEL_WOMEN_RESCUED_MAJOR",
        "BROTHELS",
        "WOMEN RESCUED - MAJOR",
        "Women Rescued - Major",
        r"MAJOR",
    ),
    _h(
        "BROTHEL_WOMEN_RESCUED_MINOR",
        "BROTHELS",
        "WOMEN RESCUED - MINOR",
        "Women Rescued - Minor",
        r"MINOR",
    ),
    _h(
        "BROTHEL_ACCUSED_ARRESTED",
        "BROTHELS",
        "ACCUSED ARRESTED",
        "Accused Arrested",
        r"ACCUSED\s+ARRESTED",
    ),
)

EOW_HEADS: tuple[OfficialHead, ...] = (
    _h(
        "EOW_CASES",
        "EOW",
        "EOW CASES",
        "Cases Registered by Economic Offences Wing",
        r"^EOW\s+CASES",
    ),
)

CYBER_HEADS: tuple[OfficialHead, ...] = (
    _h(
        "CYBER_SOURCE_CODE_TAMPERING",
        "CYBER",
        "Tampering of Source Code",
        "Tampering of Source Code",
        r"^Tampering\s+of\s+Source\s+Code",
    ),
    _h(
        "CYBER_PHISHING_MIM_SPOOFING",
        "CYBER",
        "Phishing /MIM Attack/ Spoofing Mail",
        "Phishing / MIM Attack / Spoofing Mail",
        r"^Phishing",
    ),
    _h("CYBER_PORNOGRAPHY", "CYBER", "Pornography", "Pornography", r"^Pornography$"),
    _h(
        "CYBER_OBSCENE_CONTENT",
        "CYBER",
        "Obscene Email / SMS / MMS/Post",
        "Obscene Email / SMS / MMS / Post",
        r"^Obscene\s+Email",
    ),
    _h(
        "CYBER_FAKE_PROFILE_MORPHING",
        "CYBER",
        "Fake Social Media Profile/ Morphing Email/ SMS",
        "Fake Social Media Profile / Morphing Email / SMS",
        r"^Fake\s+Social\s+Media",
    ),
    _h(
        "CYBER_CARD_ONLINE_FRAUD",
        "CYBER",
        "Credit Card / Online Fraud",
        "Credit Card / Online Fraud",
        r"^Credit\s+Card",
    ),
    _h("CYBER_HACKING", "CYBER", "Hacking", "Hacking", r"^Hacking$"),
    _h("CYBER_CHEATING", "CYBER", "Cheating", "Cheating", r"^Cheating$", is_total=True),
    _h(
        "CYBER_CHEATING_CUSTOM_GIFT",
        "CYBER",
        "Custom/Gift Fraud",
        "Custom / Gift Fraud",
        r"^Custom/Gift",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_PURCHASE",
        "CYBER",
        "Purchase fraud",
        "Purchase Fraud",
        r"^Purchase\s+fraud",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_JOB",
        "CYBER",
        "Job Fraud",
        "Job Fraud",
        r"^Job\s+Fraud",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_INSURANCE_PF",
        "CYBER",
        "Insurance/ Provident Fund Fraud",
        "Insurance / Provident Fund Fraud",
        r"^Insurance",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_ADMISSION",
        "CYBER",
        "Admission fraud",
        "Admission Fraud",
        r"^Admission\s+fraud",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_FAKE_WEBSITE",
        "CYBER",
        "Fake Web site",
        "Fake Website",
        r"^Fake\s+Web\s*site",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_SHARE_MARKET",
        "CYBER",
        "Share Market Investment",
        "Share Market Investment",
        r"^Share\s+Market",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_INVESTMENT",
        "CYBER",
        "Investment Fraud",
        "Investment Fraud",
        r"^Investment\s+Fraud",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_MATRIMONIAL",
        "CYBER",
        "Matrimonial Fraud",
        "Matrimonial Fraud",
        r"^Matrimonial",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_CRYPTO",
        "CYBER",
        "Crypto currency Fraud",
        "Cryptocurrency Fraud",
        r"^Crypto",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_LOAN",
        "CYBER",
        "Loan Fraud",
        "Loan Fraud",
        r"^Loan\s+Fraud",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_GOVT_OFFICIAL",
        "CYBER",
        "Pretended as Govt Official",
        "Pretended as Government Official",
        r"^Pretended",
        parent="CYBER_CHEATING",
    ),
    _h(
        "CYBER_CHEATING_OTHER",
        "CYBER",
        "Other Cheating",
        "Other Cheating",
        r"^Other\s+Cheating",
        parent="CYBER_CHEATING",
    ),
    _h("CYBER_DATA_THEFT", "CYBER", "Data Theft", "Data Theft", r"^Data\s+Theft"),
    _h("CYBER_SEXTORTION", "CYBER", "Sextortion", "Sextortion", r"^Sextortion"),
    _h("CYBER_COMMUNAL_POST", "CYBER", "Communal Post", "Communal Post", r"^Communal\s+Post"),
    _h("CYBER_OTHER", "CYBER", "Other", "Other", r"^Other$"),
    _h("CYBER_TOTAL", "CYBER", "Total", "Total", r"^Total$", is_total=True),
)

SECTIONS: tuple[OfficialSection, ...] = (
    OfficialSection("IPC", "Comparative Statement of I.P.C. Crime", 1, IPC_HEADS),
    OfficialSection("CAW", "Comparative Statement of Crime Against Women", 2, CAW_HEADS),
    OfficialSection("NDPS", "Comparative Statement of N.D.P.S. Cases", 3, NDPS_HEADS),
    OfficialSection(
        "BROTHELS",
        "Statement showing zonewise information regarding cases on brothels",
        4,
        BROTHEL_HEADS,
    ),
    OfficialSection("EOW", "Cases Registered by Economic Offences Wing", 5, EOW_HEADS),
    OfficialSection("CYBER", "Cyber Crime Headwise", 6, CYBER_HEADS),
)

HEADS_BY_CODE: dict[str, OfficialHead] = {h.code: h for s in SECTIONS for h in s.heads}
