# Aashaudyami mobile prototype

An Android app (React + Capacitor) that runs the advisory platform **entirely on the phone**, with no network calls and no
external APIs. The Python backend's logic is ported to TypeScript and runs over a bundled data pack, so every result
changes with what the user types or does.

## What runs on the device (`src/core/`)
| Stage | Module | Mirrors (backend) |
|---|---|---|
| Understanding messages: amounts, places, activities, reasons, intents; English, Hindi, Hinglish and, through vocabulary files, Bangla, Tamil, Telugu, Punjabi, Kannada and Marathi | `nlu.ts`, `lexicon.ts` | `orchestrator/router.py`, `language.py` |
| Location lookup with official-code disambiguation | `geo.ts` | `data_connectors/geocoding.py`, `census.py` |
| Retrieval over sector reports, risk taxonomy and scheme guidelines (TF-IDF) | `retrieval.ts` | `rag/vector_store.py` |
| Discovery ranking, 6 analyses, SWOT, red-team review, bounded rejection loop | `discovery.ts`, `intel/*`, `swot.ts`, `review.ts`, `feasibility.ts` | `module1_feasibility/*` |
| Loan engine, earnings build-up, stress tests, budget, scheme explanation | `../engine/finance.ts`, `financial.ts` | `module2_financial/*` |
| Document checklist and validators, application state machine | `documents.ts`, `tracker.ts` | `documentation_agent.py`, `application_tracker.py` |
| SMS alert parsing, health score, early warning, outcomes, grievances, launch roadmap, group buying | `sms.ts`, `health.ts`, `outcomes.ts`, `grievance.ts`, `launch.ts`, `procurement.ts` | `module3_monitoring/*`, `sms_parser.py` |
| Sales forecast (learned level vs plan, seasonal, 80% ranges, instalment cover chance, back-tested accuracy) | `forecast.ts` | — |
| Unusual activity in bank alerts (double charges, outlier amounts, sales gaps, mid-month slowdown) | `anomalies.ts` | — |
| Document scanning: camera + ML Kit text recognition (bundled Latin and Devanagari models, `DocumentTextPlugin.java`), then document type, fields, checksums and name match | `docscan.ts`, `../lib/scanner.ts` | — |
| Whole case from inputs | `session.ts` (`computeCase`) | `orchestrator/graph.py` |
| Lender portfolio over a synthetic applicant cohort | `portfolio.ts` | — |

The saved state (`src/state/store.tsx`) holds only what the user entered and did. `useCase()` recomputes everything
else. Parity tests compare the TypeScript port with outputs exported from the Python backend (`scripts/export_parity_*.py`).

## Data pack (`src/core/data/`, built by `scripts/build_datapack.py`)
- **Copied from the repo:** state reference, scheme guidelines, risk taxonomy, sector corpus, the synthetic outcome seed and the health thresholds.
- **Synthetic sample tables** (`_meta.json` → `synthetic_sample: true`), standing in for downloads of Census/LGD, OpenStreetMap, Udyam and Agmarknet: 9 districts, 290 villages (including repeated names), about 6,000 points of interest, enterprise counts and 36-month price series.

The screens carry no sample-data or demo labels; _meta.json and this README record what is synthetic. Outcome counts are shown as aseline (the synthetic seed) and ollow-up (records saved on the phone).

## Languages
Eight app languages: English, Hindi, Bangla, Tamil, Telugu, Punjabi, Kannada and Marathi. English and Hindi strings
are authored in `src/i18n/strings/`. The other six are in `src/i18n/locales/<code>.partN.json`, with the chat vocabulary
in `<code>.nlu.json`. Check a language with
`node scripts/check_locales.mjs <en.json> <code>`, which reports missing keys, placeholders, untranslated text and
script. `en.json` is a flat export of the English dictionary. Retrieved scheme and sector documents stay in English.

## Demo tips
- **Presenter controls:** tap the version line in More 7 times to show them (tap 7 times again to hide). They offer checkpoints that load sample inputs (results are still computed), a "months pass" clock, and a choice of sample SMS inbox (typical year or monsoon disruption).
- **Voice:** uses the phone's own speech recognition and text-to-speech; you can always type.
- **Outcome records:** real records are saved on the phone when the user answers a follow-up; seed records appear as baseline counts.

## Develop and test
```bash
npm install
npm run dev          # http://localhost:5173
npm test             # 342 tests: engine and backend parity, core pipeline, i18n coverage
python scripts/build_datapack.py          # rebuild the data pack (run from mobile/)
python scripts/export_parity_c1.py        # refresh parity fixtures after backend changes (also c2, c3)
```

## Build the APK
```powershell
. "$env:USERPROFILE\.android-toolchain\env.ps1"
npm run build; npx cap sync android
cd android; .\gradlew.bat assembleRelease
```
Zipalign and sign `android/app/build/outputs/apk/release/app-release-unsigned.apk` with your keystore, using `apksigner`.
The demo keystore lives outside the repo; never commit keystores.

**Install:** copy `release/Aashaudyami-demo.apk` to the phone, open it, allow "install unknown apps", and choose "Install anyway" if Play Protect asks.
