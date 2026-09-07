# Browser-first web app

The browser version is in `web_app.py` and is designed for fast testing before packaging Windows/Android builds.

## Run locally

```bat
python -m venv .venv-web
.venv-web\Scripts\activate
python -m pip install -r requirements-web.txt
streamlit run web_app.py
```

Then open the local URL shown by Streamlit, normally:

```text
http://localhost:8501
```

## Current web features

- **Photo** — batch upload, exact portal dimensions, KB-target JPEG, optional face crop, ZIP download.
- **Signature** — batch upload, ink cleanup/cropping, exact dimensions, KB-target JPEG, ZIP download.
- **Student Form / OCR** — upload a scan/photo/PDF and run Chandra through the Datalab API.
- **Reference Match** — search the Supabase `Class_X_reg_2026_2027` reference table.

## Chandra OCR configuration

Set `DATALAB_API_KEY` as a server environment variable or Streamlit secret. Never commit the key to GitHub.

For a quick local test, the page also allows a password-style API-key entry when no server key is configured.

The web app uses Datalab's current `/api/v1/convert` flow and polls the returned request URL until the OCR result is complete.

## Streamlit deployment

Create a Streamlit Cloud app from this repository and select:

```text
Main file path: web_app.py
```

Add `DATALAB_API_KEY` under the app's server-side Secrets. The key is not placed in source code or sent to the browser.

## Important privacy note

The Photo and Signature tabs process uploaded images in the web server session. The Student Form / OCR tab sends the selected document to Datalab/Chandra when OCR is explicitly started. Do not use a hosted web deployment for sensitive student documents unless the data-handling arrangement is acceptable for your use case.

## Next development stage

After the browser workflow is stable:

```text
Hardcopy
  ↓
Chandra OCR
  ↓
Structured student fields
  ↓
Supabase reference match
  ↓
Field-by-field verification
  ↓
Photo + Signature extraction/processing
  ↓
Batch registration preparation
  ↓
BSEB browser automation
  ↓
User review / confirmation
  ↓
Submit
```

The final BSEB submission remains user-controlled.
