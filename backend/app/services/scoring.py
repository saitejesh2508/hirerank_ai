import json
import re

import httpx

from app.core.config import settings

WEIGHTS = {
    "Must-have skills": 45,
    "Experience": 25,
    "Preferred skills": 10,
    "Notice period": 10,
    "Location": 5,
    "CTC compatibility": 5,
}


def _evidence(text: str, patterns: list[str]) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if candidate and any(re.search(pattern, candidate, re.I) for pattern in patterns):
            return candidate[:500]
    return "Insufficient evidence"


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", value.casefold()).strip()


def evidence_is_valid(quotation: str, resume_text: str) -> bool:
    if quotation == "Insufficient evidence":
        return True
    return _normalized(quotation) in _normalized(resume_text)


def deterministic_score(requisition, candidate, resume_text: str) -> dict:
    skill_set = {candidate_skill.skill.casefold() for candidate_skill in candidate.skills}
    required = requisition.required_skills or []
    preferred = requisition.preferred_skills or []
    must_count = sum(skill.casefold() in skill_set for skill in required)
    preferred_count = sum(skill.casefold() in skill_set for skill in preferred)
    must_score = 100 if not required else round(100 * must_count / len(required))
    preferred_score = 100 if not preferred else round(100 * preferred_count / len(preferred))
    experience_score = 0
    if candidate.experience_years is not None:
        low, high = requisition.min_experience or 0, requisition.max_experience
        experience_score = 100 if candidate.experience_years >= low and (high is None or candidate.experience_years <= high) else max(0, 100 - round(abs(candidate.experience_years - (low if candidate.experience_years < low else high or low)) * 20))
    notice_score = 100 if requisition.max_notice_days is None else 0 if candidate.notice_days is None else (100 if candidate.notice_days <= requisition.max_notice_days else max(0, 100 - (candidate.notice_days - requisition.max_notice_days)))
    location_score = 100 if not requisition.location else 0 if not candidate.location else (100 if requisition.location.casefold() in candidate.location.casefold() else 0)
    ctc_score = 100 if requisition.max_ctc is None else 0
    if candidate.expected_ctc is not None and requisition.max_ctc is not None:
        ctc_score = 100 if candidate.expected_ctc <= requisition.max_ctc and (requisition.min_ctc is None or candidate.expected_ctc >= requisition.min_ctc) else 25
    raw_scores = {
        "Must-have skills": must_score,
        "Experience": experience_score,
        "Preferred skills": preferred_score,
        "Notice period": notice_score,
        "Location": location_score,
        "CTC compatibility": ctc_score,
    }
    criteria = []
    skill_patterns = [re.escape(skill) for skill in required + preferred] or ["(?!)"]
    skill_lines = [line.strip() for line in resume_text.splitlines() if re.search(r"\b(skills?|technologies|technical stack|competencies)\b", line, re.I)]
    skill_quote = next((line[:500] for line in skill_lines if any(re.search(pattern, line, re.I) for pattern in skill_patterns)), None)
    skill_quote = skill_quote or _evidence(resume_text, skill_patterns)
    exp_quote = _evidence(resume_text, [r"\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)"])
    notice_quote = _evidence(resume_text, [r"notice", r"available\s+in"])
    location_quote = _evidence(resume_text, [r"location", r"based\s+in"])
    ctc_quote = _evidence(resume_text, [r"(?:expected|current)\s+ctc"])
    quotes = {
        "Must-have skills": skill_quote, "Experience": exp_quote,
        "Preferred skills": skill_quote, "Notice period": notice_quote,
        "Location": location_quote, "CTC compatibility": ctc_quote,
    }
    for name, value in raw_scores.items():
        quote = quotes[name]
        not_configured = (name == "Notice period" and requisition.max_notice_days is None) or (name == "Location" and not requisition.location) or (name == "CTC compatibility" and requisition.max_ctc is None)
        criteria.append({
            "criterion": name,
            "status": "not_applicable" if not_configured else "match" if value >= 70 else "partial" if value >= 40 else "no_match" if quote != "Insufficient evidence" else "insufficient_evidence",
            "score": value,
            "quotation": quote,
            "explanation": f"No {name.lower()} requirement was configured; neutral points were applied." if not_configured else f"{value}% criterion fit based on the requisition and parsed resume facts.",
            "confidence": 1.0 if not_configured else 0.85 if quote != "Insufficient evidence" else 0.35,
        })
    overall = round(sum(raw_scores[key] * weight for key, weight in WEIGHTS.items()) / 100, 1)
    return _validated_result({
        "overall_score": overall,
        "category": "Strong match" if overall >= 85 else "Good match" if overall >= 70 else "Partial match" if overall >= 50 else "Low match",
        "criteria": criteria,
        "scoring_method": "rule-based",
        "missing_information": candidate.missing_information or [],
        "warnings": ["Rule-based fallback scoring; no configured AI provider was used."],
    }, resume_text, requisition)


def _validated_result(result: dict, resume_text: str, requisition) -> dict:
    if not isinstance(result.get("criteria"), list):
        raise ValueError("Scoring output does not contain criterion details")
    expected_names = set(WEIGHTS)
    criteria_by_name = {item.get("criterion"): item for item in result["criteria"] if isinstance(item, dict)}
    if set(criteria_by_name) != expected_names:
        raise ValueError("Scoring output does not match the approved scorecard")
    weighted_total = 0.0
    normalized_criteria = []
    for name in WEIGHTS:
        criterion = criteria_by_name[name]
        if not isinstance(criterion.get("score"), (int, float)):
            raise ValueError("Criterion score must be numeric")
        criterion["score"] = max(0, min(100, float(criterion["score"])))
        criterion["confidence"] = max(0, min(1, float(criterion.get("confidence", 0))))
        if not isinstance(criterion.get("explanation"), str):
            raise ValueError("Criterion explanation must be text")
        quotation = criterion.get("quotation", "Insufficient evidence")
        if not isinstance(quotation, str):
            raise ValueError("Criterion quotation must be text")
        if not evidence_is_valid(quotation, resume_text):
            criterion["quotation"] = "Insufficient evidence"
            criterion["status"] = "insufficient_evidence"
            criterion["confidence"] = 0.0
            criterion["explanation"] = "Evidence could not be verified against the resume text."
        not_configured = (name == "Notice period" and requisition.max_notice_days is None) or (name == "Location" and not requisition.location) or (name == "CTC compatibility" and requisition.max_ctc is None)
        if not_configured:
            criterion["score"] = 100
            criterion["quotation"] = "Insufficient evidence"
            criterion["status"] = "not_applicable"
            criterion["explanation"] = f"No {name.lower()} requirement was configured; neutral points were applied."
            criterion["confidence"] = 1.0
        else:
            quotation_present = criterion["quotation"] != "Insufficient evidence"
            criterion["status"] = "match" if criterion["score"] >= 70 and quotation_present else "partial" if criterion["score"] >= 40 and quotation_present else "no_match" if quotation_present else "insufficient_evidence"
        weighted_total += criterion["score"] * WEIGHTS[criterion["criterion"]]
        normalized_criteria.append(criterion)
    result["criteria"] = normalized_criteria
    result["overall_score"] = round(weighted_total / 100, 1)
    result["category"] = "Strong match" if result["overall_score"] >= 85 else "Good match" if result["overall_score"] >= 70 else "Partial match" if result["overall_score"] >= 50 else "Low match"
    return result


def score_candidate(requisition, candidate, resume_text: str) -> dict:
    if settings.ai_api_key:
        try:
            prompt = {
                "requisition": {
                    "title": requisition.title, "required_skills": requisition.required_skills,
                    "preferred_skills": requisition.preferred_skills, "min_experience": requisition.min_experience,
                    "max_experience": requisition.max_experience, "max_notice_days": requisition.max_notice_days,
                    "location": requisition.location, "min_ctc": requisition.min_ctc, "max_ctc": requisition.max_ctc,
                },
                "resume_text": resume_text[:18000],
                "weights": WEIGHTS,
                "instruction": "Return JSON only. Do not use protected traits. Every quotation must be copied verbatim from resume_text; otherwise use Insufficient evidence.",
                "schema": {"overall_score": "number", "category": "string", "criteria": [{"criterion": "string", "status": "string", "score": "number", "quotation": "string", "explanation": "string", "confidence": "number"}], "missing_information": ["string"], "warnings": ["string"]},
            }
            response = httpx.post(
                f"{settings.ai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                json={"model": settings.ai_model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": json.dumps(prompt)}]},
                timeout=20,
            )
            response.raise_for_status()
            result = json.loads(response.json()["choices"][0]["message"]["content"])
            if not isinstance(result.get("criteria"), list):
                raise ValueError("AI response did not contain criterion details")
            result["scoring_method"] = "llm"
            result.setdefault("missing_information", candidate.missing_information or [])
            result.setdefault("warnings", [])
            return _validated_result(result, resume_text, requisition)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            fallback = deterministic_score(requisition, candidate, resume_text)
            fallback["warnings"].append("Configured AI provider failed or returned invalid output; rule-based fallback was used.")
            return fallback
    return deterministic_score(requisition, candidate, resume_text)
