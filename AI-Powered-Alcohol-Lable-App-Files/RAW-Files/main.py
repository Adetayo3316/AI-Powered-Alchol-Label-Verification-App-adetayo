"""
AI-Powered Alcohol Label Verification App
-------------------------------------------
Single FastAPI app that serves:
  - A static HTML/JS frontend (in /static)
  - /verify        : verify a single label image against expected fields
  - /verify-batch  : verify multiple label images against a JSON list of expected applications

Approach:
  - OCR via Tesseract (pytesseract) — local, free, fast (<5s typical)
  - Rule-based + fuzzy matching for field comparison
  - No external/cloud APIs required (works behind restrictive firewalls)
"""

import io
import json
import re
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image
import pytesseract
from fuzzywuzzy import fuzz

app = FastAPI(title="Alcohol Label Verification API")

# Allow the frontend (served from same app, but CORS open for local dev/testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

# Official TTB Government Warning text (must appear, with this exact wording,
# and "GOVERNMENT WARNING:" must be in all caps per Jenny's feedback).
GOVERNMENT_WARNING_TEXT = (
    "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT "
    "DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE OF THE RISK OF BIRTH "
    "DEFECTS. (2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO "
    "DRIVE A CAR OR OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS."
)

FUZZY_MATCH_THRESHOLD = 90  # 0-100, used for brand name / class-type matching


# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation noise for fuzzy comparisons."""
    text = text.replace("\n", " ")
    text = re.sub(r"[^a-zA-Z0-9%./ ]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def extract_text(image_bytes: bytes) -> str:
    """Run OCR on the uploaded image and return raw extracted text."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Convert to RGB to avoid mode issues (e.g. PNGs with alpha channel)
        if image.mode != "RGB":
            image = image.convert("RGB")
        text = pytesseract.image_to_string(image)
        return text
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read image: {exc}")


def fuzzy_field_match(expected: str, ocr_text: str, threshold: int = FUZZY_MATCH_THRESHOLD) -> dict:
    """
    Check whether `expected` appears in `ocr_text` using fuzzy matching.
    Handles cases like 'STONE'S THROW' vs 'Stone's Throw' (case differences),
    minor OCR noise, etc.
    """
    norm_expected = normalize_text(expected)
    norm_ocr = normalize_text(ocr_text)

    if not norm_expected:
        return {"expected": expected, "found_in_label": None, "score": 0, "match": False}

    # 1) Direct substring check (fast path, handles exact/near-exact matches)
    if norm_expected in norm_ocr:
        return {"expected": expected, "found_in_label": expected, "score": 100, "match": True}

    # 2) Fuzzy partial-ratio match against sliding windows of OCR text
    #    (helps when OCR text has extra characters / line breaks around the field)
    best_score = 0
    words = norm_ocr.split()
    expected_word_count = len(norm_expected.split())

    for i in range(len(words)):
        window = " ".join(words[i:i + expected_word_count + 2])  # small buffer
        score = fuzz.partial_ratio(norm_expected, window)
        if score > best_score:
            best_score = score

    # Also compare against the whole OCR text as a fallback
    whole_score = fuzz.partial_ratio(norm_expected, norm_ocr)
    best_score = max(best_score, whole_score)

    return {
        "expected": expected,
        "found_in_label": ocr_text.strip()[:200],  # snippet for agent review
        "score": best_score,
        "match": best_score >= threshold,
    }


def extract_abv_values(text: str) -> List[float]:
    """Find all percentage-like ABV values in text, e.g. '45% Alc./Vol.' -> 45.0"""
    matches = re.findall(r"(\d{1,2}(?:\.\d{1,2})?)\s*%", text)
    return [float(m) for m in matches]


def check_abv(expected_abv: str, ocr_text: str, tolerance: float = 0.5) -> dict:
    """
    Compare expected ABV (e.g. '45%' or '45') against ABV values found via OCR.
    Allows a small tolerance for OCR misreads.
    """
    expected_match = re.search(r"(\d{1,2}(?:\.\d{1,2})?)", expected_abv or "")
    if not expected_match:
        return {"expected": expected_abv, "found_in_label": None, "match": False, "note": "Could not parse expected ABV"}

    expected_value = float(expected_match.group(1))
    found_values = extract_abv_values(ocr_text)

    for val in found_values:
        if abs(val - expected_value) <= tolerance:
            return {
                "expected": expected_abv,
                "found_in_label": f"{val}%",
                "match": True,
            }

    return {
        "expected": expected_abv,
        "found_in_label": ", ".join(f"{v}%" for v in found_values) if found_values else "Not found",
        "match": False,
    }


def check_net_contents(expected: str, ocr_text: str) -> dict:
    """
    Compare expected net contents (e.g. '750 mL', '12 fl oz') against OCR text.
    Normalizes units and spacing for comparison.
    """
    norm_expected = normalize_text(expected)
    norm_ocr = normalize_text(ocr_text)

    # Extract number + unit pairs from both
    pattern = r"(\d+(?:\.\d+)?)\s*(ml|l|floz|fl oz|oz|gal|cl)"
    expected_matches = re.findall(pattern, norm_expected)
    ocr_matches = re.findall(pattern, norm_ocr)

    if not expected_matches:
        # fall back to simple substring/fuzzy check
        return fuzzy_field_match(expected, ocr_text, threshold=85)

    exp_num, exp_unit = expected_matches[0]
    for num, unit in ocr_matches:
        if num == exp_num and unit.replace(" ", "") == exp_unit.replace(" ", ""):
            return {"expected": expected, "found_in_label": f"{num} {unit}", "match": True}

    found_str = ", ".join(f"{n} {u}" for n, u in ocr_matches) if ocr_matches else "Not found"
    return {"expected": expected, "found_in_label": found_str, "match": False}


def check_government_warning(ocr_text: str) -> dict:
    """
    Verify the Government Warning is present, with 'GOVERNMENT WARNING:' in all caps
    (a common rejection reason per agent feedback), and that the required text matches.
    """
    # Check for the exact all-caps header
    header_present_caps = "GOVERNMENT WARNING:" in ocr_text

    # Check for a case-insensitive version, to flag "title case" type rejections
    header_present_any_case = "government warning" in ocr_text.lower()

    # Fuzzy-check the full required text body
    norm_expected = normalize_text(GOVERNMENT_WARNING_TEXT)
    norm_ocr = normalize_text(ocr_text)
    body_score = fuzz.partial_ratio(norm_expected, norm_ocr)

    if header_present_caps and body_score >= 85:
        return {
            "expected": "GOVERNMENT WARNING (required text, all caps header)",
            "found_in_label": "Present and matches required format",
            "match": True,
            "score": body_score,
        }

    notes = []
    if not header_present_any_case:
        notes.append("Warning statement not found on label.")
    elif not header_present_caps:
        notes.append("'GOVERNMENT WARNING:' header is present but NOT in required ALL CAPS format.")
    if body_score < 85:
        notes.append(f"Warning text does not closely match required wording (similarity: {body_score}%).")

    return {
        "expected": "GOVERNMENT WARNING (required text, all caps header)",
        "found_in_label": "Issue detected" if notes else "Present",
        "match": False,
        "score": body_score,
        "notes": notes,
    }


def verify_label(
    image_bytes: bytes,
    brand_name: Optional[str] = None,
    class_type: Optional[str] = None,
    alcohol_content: Optional[str] = None,
    net_contents: Optional[str] = None,
) -> dict:
    """Run OCR + all field checks for a single label image. Returns structured result."""
    ocr_text = extract_text(image_bytes)

    results = {}

    if brand_name:
        results["brand_name"] = fuzzy_field_match(brand_name, ocr_text)

    if class_type:
        results["class_type"] = fuzzy_field_match(class_type, ocr_text)

    if alcohol_content:
        results["alcohol_content"] = check_abv(alcohol_content, ocr_text)

    if net_contents:
        results["net_contents"] = check_net_contents(net_contents, ocr_text)

    results["government_warning"] = check_government_warning(ocr_text)

    # Overall pass/fail
    overall_pass = all(field["match"] for field in results.values())

    return {
        "overall_match": overall_pass,
        "fields": results,
        "raw_ocr_text": ocr_text.strip(),
    }


# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/verify")
async def verify_single(
    image: UploadFile = File(...),
    brand_name: Optional[str] = Form(None),
    class_type: Optional[str] = Form(None),
    alcohol_content: Optional[str] = Form(None),
    net_contents: Optional[str] = Form(None),
):
    """Verify a single label image against the provided expected field values."""
    image_bytes = await image.read()
    result = verify_label(
        image_bytes,
        brand_name=brand_name,
        class_type=class_type,
        alcohol_content=alcohol_content,
        net_contents=net_contents,
    )
    result["filename"] = image.filename
    return result


@app.post("/verify-batch")
async def verify_batch(
    images: List[UploadFile] = File(...),
    applications: str = Form(...),
):
    """
    Verify multiple label images against a JSON array of expected applications.

    `applications` should be a JSON string like:
    [
      {"filename": "label1.jpg", "brand_name": "OLD TOM DISTILLERY", "class_type": "Kentucky Straight Bourbon Whiskey", "alcohol_content": "45%", "net_contents": "750 mL"},
      {"filename": "label2.jpg", ...}
    ]

    Each image is matched to its corresponding application by `filename`.
    """
    try:
        applications_data = json.loads(applications)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in 'applications': {exc}")

    if not isinstance(applications_data, list):
        raise HTTPException(status_code=400, detail="'applications' must be a JSON array")

    # Build lookup of filename -> expected fields
    apps_by_filename = {app_data.get("filename"): app_data for app_data in applications_data}

    results = []
    for image in images:
        image_bytes = await image.read()
        app_data = apps_by_filename.get(image.filename, {})

        if not app_data:
            results.append({
                "filename": image.filename,
                "error": "No matching application entry found for this filename",
            })
            continue

        result = verify_label(
            image_bytes,
            brand_name=app_data.get("brand_name"),
            class_type=app_data.get("class_type"),
            alcohol_content=app_data.get("alcohol_content"),
            net_contents=app_data.get("net_contents"),
        )
        result["filename"] = image.filename
        results.append(result)

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.get("overall_match")),
        "failed": sum(1 for r in results if r.get("overall_match") is False),
        "errors": sum(1 for r in results if "error" in r),
    }

    return {"summary": summary, "results": results}


# ----------------------------------------------------------------------------
# Static frontend
# ----------------------------------------------------------------------------

@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
