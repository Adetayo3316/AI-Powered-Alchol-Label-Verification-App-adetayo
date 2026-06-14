# Alcohol Label Verification App

A prototype tool that helps TTB compliance agents verify alcohol label artwork
against application data automatically. Upload a label image, enter the
expected field values (or upload a batch of labels with a JSON manifest), and
get a fast (<1 second) pass/fail breakdown per field.

## Live Demo

`https://<your-deployed-url>` *(replace after deploying — see Deployment section)*

## Features

- **Single label verification** — upload one label image + expected field
  values (brand name, class/type, ABV, net contents). Government Warning is
  always checked automatically.
- **Batch verification** — upload many label images at once along with a JSON
  array describing each application, for peak-season bulk processing.
- **Fast** — OCR + rule-based matching typically completes in under 1 second
  per label, well within the 5-second usability threshold identified during
  discovery.
- **Simple UI** — single page, large buttons, clear ✅ / ❌ indicators, no
  hidden menus. Designed to be usable without training.
- **Fuzzy matching** — handles minor formatting differences (e.g.
  `"STONE'S THROW"` vs `"Stone's Throw"`) without flagging them as errors.
- **Government Warning check** — verifies the required warning text is
  present **and** that the `"GOVERNMENT WARNING:"` header is in the required
  ALL CAPS format (a common real-world rejection reason).
- **No external/cloud AI APIs** — everything runs locally via Tesseract OCR,
  so it works behind restrictive government firewalls and has no per-request
  cost or external data exposure.

## Tech Stack

| Layer    | Choice                                  | Why |
|----------|------------------------------------------|-----|
| Backend  | FastAPI (Python)                        | Fast to build, async, automatic docs at `/docs` |
| OCR      | Tesseract (via `pytesseract`)           | Free, local, no API limits, no firewall issues |
| Matching | Rule-based regex + `fuzzywuzzy`         | Transparent, fast, easy to tune thresholds |
| Frontend | Plain HTML/CSS/JS (served by FastAPI)   | No build step, single deployable unit |
| Hosting  | Docker container (Render/Railway/Fly.io free tier) | Simple single-service deployment |

## Project Structure

```
label-verification-app/
├── main.py              # FastAPI app: OCR, matching logic, API routes
├── static/
│   └── index.html       # Frontend (single page, tabs for single/batch)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container definition (includes Tesseract)
├── test_label_pass.png  # Sample label — all fields match
├── test_label_fail.png  # Sample label — ABV/net contents/warning issues
└── README.md
```

## Setup & Run Locally

### Prerequisites
- Python 3.10+
- Tesseract OCR binary installed on your system:
  - **macOS**: `brew install tesseract`
  - **Ubuntu/Debian**: `sudo apt install tesseract-ocr`
  - **Windows**: install from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

### Steps

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd label-verification-app

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
uvicorn main:app --reload

# 5. Open the app
# Visit http://localhost:8000 in your browser
```

## Running with Docker

```bash
docker build -t label-verification-app .
docker run -p 8000:8000 label-verification-app
```

Then visit `http://localhost:8000`.

## How to Use

### Single Label Tab
1. Upload a label image (JPG/PNG).
2. Enter the expected Brand Name, Class/Type, Alcohol Content, and Net
   Contents from the application.
3. Click **Verify Label**.
4. Review the field-by-field results. Government Warning is checked
   automatically regardless of what else you fill in.

### Batch Tab
1. Select multiple label image files.
2. Provide a JSON array describing each application, matched by `filename`:

```json
[
  {
    "filename": "label1.jpg",
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45%",
    "net_contents": "750 mL"
  },
  {
    "filename": "label2.jpg",
    "brand_name": "RIVER BEND CELLARS",
    "class_type": "Cabernet Sauvignon",
    "alcohol_content": "13.5%",
    "net_contents": "750 mL"
  }
]
```

3. Click **Verify Batch**. A summary count (passed/failed/errors) appears at
   the top, followed by per-label results.

## API Reference (also available at `/docs` via FastAPI Swagger UI)

### `POST /verify`
Form fields:
- `image` (file, required)
- `brand_name`, `class_type`, `alcohol_content`, `net_contents` (text, optional)

### `POST /verify-batch`
Form fields:
- `images` (multiple files, required)
- `applications` (JSON string, array of application objects keyed by `filename`)

## Approach & Design Decisions

- **OCR-first, rule-based matching** was chosen over a full vision-LLM
  approach for three reasons surfaced in discovery: (1) the 5-second response
  requirement ruled out slow cloud vision pipelines, (2) the agency's firewall
  blocks many outbound ML API endpoints, and (3) most of the verification work
  described by agents ("does the number on the form match the number on the
  label") is fundamentally a text-matching problem, not a reasoning problem.
- **Fuzzy matching** for brand name and class/type addresses Dave's
  "STONE'S THROW vs Stone's Throw" example — case and minor formatting
  differences are treated as matches, while real discrepancies are flagged.
- **Strict Government Warning check** addresses Jenny's feedback that the
  `"GOVERNMENT WARNING:"` header must be ALL CAPS and the body text must
  closely match the required statement — the tool explicitly flags
  title-case headers as a distinct issue from a missing warning.
- **Batch endpoint** addresses the peak-season bulk-upload pain point (Janet's
  request) by accepting many images + a JSON manifest in one request.
- **Single-page UI with no nested menus** addresses the requirement for a tool
  usable by agents across a wide range of tech comfort levels.

## Assumptions

- Label images are reasonably legible (in focus, mostly upright, minimal
  glare). Handling heavily skewed/glare-affected images (Jenny's stretch-goal
  request) is noted below as future work.
- The expected field values come from the application data and are entered
  (or provided via JSON for batch) by the agent — this prototype does not
  integrate with COLA.
- "Match" thresholds (90% fuzzy similarity for text fields, ±0.5% tolerance
  for ABV) are reasonable defaults but should be tuned with real label samples
  before any production use.
- This is a standalone prototype with no authentication, database, or
  persistent storage — no PII or application data is retained.

## Known Limitations & Future Work

- **Image quality**: poor lighting, glare, or extreme skew angles can degrade
  OCR accuracy. A production version could add image pre-processing
  (deskew, contrast normalization) or a vision-LLM fallback for difficult
  images.
- **"Judgment" cases**: per Dave's feedback, some mismatches require human
  judgment beyond text similarity (e.g. abbreviations, stylistic variants).
  The fuzzy-match threshold helps, but a future iteration could use an LLM to
  explain *why* a mismatch occurred, giving agents more context for borderline
  cases — without removing the human from the decision.
- **COLA integration**: this prototype is intentionally standalone. Any future
  integration with the live COLA system would require its own security review
  and authorization process per IT's guidance.
- **Net contents unit conversion**: currently compares like-for-like units
  (e.g. mL to mL). Could be extended to convert between units (L ↔ mL ↔ fl oz)
  for more flexible matching.

## Generating Additional Test Labels

Two sample labels are included:
- `test_label_pass.png` — all fields match expected values.
- `test_label_fail.png` — demonstrates an ABV mismatch, net contents mismatch,
  and a Government Warning header in title case instead of ALL CAPS.

Additional labels can be generated quickly with any image tool (Canva,
PowerPoint, or AI image generators) — just include the required text fields
as legible text on the image.
