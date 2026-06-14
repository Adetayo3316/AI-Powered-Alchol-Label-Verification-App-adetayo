# AI-Powered Alcohol Label Verification App — File Guide

This package gives you the project in **two formats**. Pick whichever fits
how you want to work with it.

```
AI-Powered-Alcohol-Label-App-Files/
├── README.md                  ← you are here
├── RAW-Files/                  ← zipped project (compressed, for download/upload)
└── label-verification-app/     ← unzipped project (ready to browse/run)
```

---

## Option 1: `label-verification-app/` (recommended — ready to go)

This folder is the **project already unzipped and laid out** for you. Use
this if you just want to look at the code, or run it locally right away.

**No extra steps needed.** Go straight to:

```bash
cd label-verification-app
```

then follow the setup instructions in `label-verification-app/README.md`.

```
label-verification-app/
├── main.py              ← backend (FastAPI: OCR + matching + API)
├── static/index.html    ← frontend (single-page UI)
├── requirements.txt     ← Python dependencies
├── Dockerfile            ← for deployment (Render/Railway/Fly.io)
├── README.md            ← full setup, usage, and design documentation
├── test_label_pass.png  ← sample label (all fields match)
└── test_label_fail.png  ← sample label (3 intentional mismatches)
```

---

## Option 2: `RAW-Files/` (compressed — for upload to GitHub, etc.)

This folder contains the **same project as a `.zip` archive**
(`label-verification-app.zip`). Use this if you need a single compressed file
to:

- upload to GitHub (then extract or push contents directly)
- share via email/Slack
- transfer to another machine before setup

### Extra step required: unzip before use

```bash
cd RAW-Files
unzip label-verification-app.zip
cd label-verification-app
```

After unzipping, you'll have the **identical structure** shown in Option 1
above. From here, follow the same setup instructions in
`label-verification-app/README.md`.

---

## Quick Start (either option, after you're inside `label-verification-app/`)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open `http://localhost:8000`.

---

## Summary: Which do I use?

| You want to... | Use this |
|---|---|
| Run/test the app immediately | `label-verification-app/` |
| Browse the code without extracting anything | `label-verification-app/` |
| Push to GitHub as a clean repo | Unzip `RAW-Files/label-verification-app.zip`, then `git init` inside it |
| Send the project to someone as one file | `RAW-Files/label-verification-app.zip` |

For full setup instructions, API reference, design rationale, assumptions,
and known limitations, see **`label-verification-app/README.md`** (after
unzipping if you started from `RAW-Files/`).
