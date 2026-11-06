import re
from pathlib import Path

import fitz
from docx import Document

SKILLS = [
    "Java", "Spring Boot", "Microservices", "Hibernate", "REST APIs", "Python",
    "SQL", "Excel", "KYC", "AML Checks", "AWS", "Azure", "React", "TypeScript",
    "Kubernetes", "Docker", "Communication", "Node.js", "PostgreSQL",
]


def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        with fitz.open(stream=content, filetype="pdf") as document:
            return "\n".join(page.get_text() for page in document).strip()
    if suffix == ".docx":
        import io
        document = Document(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    raise ValueError("Only PDF and DOCX resumes are supported")


def _first(pattern: str, text: str, group: int = 1):
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return match.group(group).strip() if match else None


def parse_resume(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email = _first(r"\b([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b", text)
    phone = _first(r"(\+?\d[\d ()-]{7,}\d)", text)
    experience_value = _first(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:total\s+)?experience", text)
    notice_value = _first(r"(?:notice(?:\s+period)?|available\s+in)\s*[:\-]?\s*(\d{1,3})\s*days?", text)
    current_ctc_value = _first(r"(?:current\s+ctc)\s*[:\-]?\s*(?:inr|rs\.?|₹)?\s*([\d.]+)", text)
    expected_ctc_value = _first(r"(?:expected\s+ctc)\s*[:\-]?\s*(?:inr|rs\.?|₹)?\s*([\d.]+)", text)
    role = _first(r"(?:current\s+role|title|position)\s*[:\-]\s*([^\n]+)", text)
    location = _first(r"(?:location|based\s+in)\s*[:\-]\s*([^\n]+)", text)
    education = []
    for line in lines:
        if re.search(r"\b(b\.?tech|b\.?e\.|m\.?tech|mba|bachelor|master|degree|university)\b", line, re.I):
            education.append(line)
    employers = []
    for line in lines:
        match = re.search(r"(?:employer|company|worked\s+at)\s*[:\-]\s*(.+)", line, re.I)
        if match:
            employers.append(match.group(1).strip())
    skills = [skill for skill in SKILLS if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", text, re.I)]
    missing = [field for field, value in {
        "name": lines[0] if lines and "@" not in lines[0] else None,
        "email": email,
        "phone": phone,
        "current_role": role,
        "experience": experience_value,
        "skills": skills or None,
        "education": education or None,
        "employers": employers or None,
        "notice_period": notice_value,
        "current_ctc": current_ctc_value,
        "expected_ctc": expected_ctc_value,
    }.items() if not value]
    return {
        "name": lines[0][:160] if lines and "@" not in lines[0] else None,
        "email": email.lower() if email else None,
        "phone": phone,
        "current_role": role,
        "experience_years": float(experience_value) if experience_value else None,
        "notice_days": int(notice_value) if notice_value else None,
        "current_ctc": float(current_ctc_value) if current_ctc_value else None,
        "expected_ctc": float(expected_ctc_value) if expected_ctc_value else None,
        "location": location,
        "skills": skills,
        "education": education,
        "employers": employers,
        "missing_information": missing,
    }
