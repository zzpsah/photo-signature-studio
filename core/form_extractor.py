from __future__ import annotations

import re
from difflib import SequenceMatcher

FIELDS = [
    ("registration_no_year", "Registration No. & Year", ["registration no", "registration number"]),
    ("bseb_unique_id", "BSEB Unique ID", ["bseb unique id", "unique id"]),
    ("student_category", "Student's Category", ["student category", "category"]),
    ("school_code", "College/+2 School Code", ["school code", "college/+2 school code", "college school code"]),
    ("school_name", "College/+2 School Name", ["school name", "college/+2 school name"]),
    ("district", "District Name", ["district name", "district"]),
    ("name", "Student's Name", ["student's name", "student name", "candidate name"]),
    ("mother_name", "Mother's Name", ["mother's name", "mother name"]),
    ("father_name", "Father's Name", ["father's name", "father name"]),
    ("dob", "Date of Birth", ["date of birth", "dob"]),
    ("passing_board", "Matric/Class X Passing Board", ["passing board", "class x passing board", "matric passing board"]),
    ("board_roll_code", "Matric/Class X Board's Roll Code", ["board's roll code", "roll code"]),
    ("board_roll_number", "Roll Number", ["roll number"]),
    ("passing_year", "Passing Year", ["passing year"]),
    ("gender", "Gender", ["gender"]),
    ("caste_category", "Caste Category", ["caste category", "caste"]),
    ("differently_abled", "Differently Abled", ["differently abled"]),
    ("differently_abled_category", "Differently Abled Category", ["specify", "differently abled category"]),
    ("nationality", "Nationality", ["nationality"]),
    ("religion", "Religion", ["religion"]),
    ("aadhar_no", "Aadhaar Number", ["aadhaar number", "aadhar number", "aadhaar", "aadhar"]),
    ("mobile", "Mobile", ["mobile number", "mobile"]),
    ("email", "Email", ["email id", "email"]),
    ("address", "Address", ["address"]),
    ("pincode", "Pincode", ["pin code", "pincode"]),
]


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _clean_value(value: str) -> str:
    value = re.sub(r"^[\s:|–—-]+|[\s|]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _label_score(line: str, alias: str) -> float:
    return SequenceMatcher(None, normalize(line), normalize(alias)).ratio()


def _value_after_label(line: str, alias: str) -> str | None:
    match = re.search(re.escape(alias), line, re.I)
    if not match:
        return None
    value = _clean_value(line[match.end():])
    value = re.sub(r"^[.:：]+\s*", "", value)
    return value or None


def extract_fields(markdown: str) -> dict[str, str]:
    """Best-effort extraction for BSEB-style printed labels and OCR markdown.

    This is deliberately conservative: an uncertain/missing value is left blank
    rather than being silently invented. Chandra remains the OCR engine; this
    module only maps its output into reviewable application fields.
    """
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    result = {key: "" for key, _, _ in FIELDS}

    # First pass: markdown/plain-text label:value patterns.
    for key, _, aliases in FIELDS:
        for line in lines:
            for alias in aliases:
                value = _value_after_label(line, alias)
                if value:
                    # Avoid swallowing another label when OCR puts several fields on one line.
                    value = re.split(r"\s{2,}(?=[A-Za-z][A-Za-z '/+&.]{2,}:?)", value)[0]
                    result[key] = value
                    break
            if result[key]:
                break

    # Numbered form labels are common in this document family.
    numbered = {
        1: "registration_no_year", 2: "bseb_unique_id", 3: "student_category",
        4: "school_code", 5: "school_name", 6: "district", 7: "name",
        8: "mother_name", 9: "father_name", 10: "dob", 11: "passing_board",
        12: "board_roll_code", 13: "gender", 14: "caste_category",
        15: "differently_abled", 16: "nationality", 17: "religion", 18: "aadhar_no",
    }
    for line in lines:
        match = re.match(r"^(\d{1,2})[.)]\s*(.*)$", line)
        if not match:
            continue
        number, rest = int(match.group(1)), match.group(2)
        key = numbered.get(number)
        if not key or result[key]:
            continue
        # Split on a colon/dash when OCR preserved the handwritten value.
        value = re.split(r"\s*[:：]\s*", rest, maxsplit=1)
        if len(value) == 2 and value[1].strip():
            result[key] = _clean_value(value[1])

    # Normalize a few high-value fields without guessing their contents.
    if result["aadhar_no"]:
        digits = re.sub(r"\D", "", result["aadhar_no"])
        if len(digits) == 12:
            result["aadhar_no"] = digits
    if result["mobile"]:
        digits = re.sub(r"\D", "", result["mobile"])
        if len(digits) == 10:
            result["mobile"] = digits
    if result["pincode"]:
        digits = re.sub(r"\D", "", result["pincode"])
        if len(digits) == 6:
            result["pincode"] = digits
    return result


def extraction_review(rows: dict[str, str]) -> list[dict[str, str]]:
    """Return UI-ready rows with a conservative review status."""
    output = []
    for key, label, _ in FIELDS:
        value = rows.get(key, "")
        output.append({
            "field": label,
            "key": key,
            "value": value,
            "status": "Review" if value else "Missing",
        })
    return output
