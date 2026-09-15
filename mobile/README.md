# Aashaudyami mobile prototype

An Android app (React + Capacitor) that runs the advisory platform **entirely on the phone**, with no network calls and no
external APIs. The Python backend's logic is ported to TypeScript and runs over a bundled data pack, so every result
changes with what the user types or does.

## What runs on the device (`src/core/`)
| Stage | Module | Mirrors (backend) |
|---|---|---|
| Understanding messages: amounts, places, activities, reasons, intents; English, Hindi, Hinglish and, through vocabulary files, Bangla, Tamil, Telugu, Punjabi, Kannada and Marathi | `nlu.ts`, `lexicon.ts` | `orchestrator/router.py`, `language.py` |
| On-device message model (multilingual-e5-small fine-tuned, int8 ONNX in a worker): name, place, amount, business and reason spans plus intent, merged with the rules | `nluModel.ts`, `../lib/nlp/*`, trained by `ml/nlu/` | — |
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

**All of India:** `india_districts.json` (built by `scripts/build_india_districts.py` from the Census 2011 district abstract and
district boundaries) lists all 639 Census 2011 districts with real names, state, centre, population and area; 63 are placed
approximately because they were created after the boundary data. The nine detailed districts keep their tables. Every
other district gets local tables generated on the phone from its own figures (`src/core/localgen.ts`, names and regional
rural banks from `regions.json`, known craft clusters as density factors). A location typed anywhere in India resolves to
its district headquarters.

The screens carry no sample-data or demo labels; _meta.json and this README record what is synthetic. Outcome counts are shown as `baseline` (the synthetic seed) and `follow-up` (records saved on the phone).

## Open data (`public/data/`, no keys)
Bundled gzip files (named `.dat`, because Android packaging unpacks and renames `.gz` assets), loaded at start-up (about 18 MB); if a file fails to load the app falls back to the generated tables.

| File | Source | Licence | What it adds |
|---|---|---|---|
| `villages.dat` | Census of India 2011 village directory with coordinates, via [datameet](https://github.com/datameet) / ramSeraph | CC0 | 645,805 villages for place matching; 116 post-2011 districts added to `india_districts.json` |
| `places.dat` | [Overture Maps](https://overturemaps.org) places | CDLA-Permissive-2.0 | 432,975 mapped shops, banks, schools and services; competitor density vs the state |
| `pincodes.dat` | India Post PIN directory (data.gov.in) | CC0 / GODL | PIN code → area centre and district, in chat and forms |
| `ifsc.dat` | [Razorpay IFSC](https://github.com/razorpay/ifsc) | MIT | IFSC → bank and branch check in the loan form |

Rebuild: `python scripts/build_open_villages.py` then `python scripts/build_open_places.py` (input paths at the top of each script).

**Online, optional, no key** (`src/lib/online.ts`); every call has a timeout and the app works without it:
- [Open-Meteo](https://open-meteo.com) historical weather (ERA5, CC BY 4.0): ten years of daily rain at the location → rainfall risk for rain-fed businesses.
- [Photon](https://photon.komoot.io) (komoot), then [Nominatim](https://nominatim.org) — OpenStreetMap data © OpenStreetMap contributors (ODbL): only for a place the bundled tables do not know; the result is snapped to the nearest Census village or district.

Keyed sources for later: data.gov.in (Agmarknet prices, Udyam), Bhuvan, Mappls, Bhashini.

## Message model (ml/nlu)
- **Data:** per-language patterns, fillers and a separate hand-written test set in `ml/nlu/data/<lang>.json` (brief in
  `ml/nlu/BRIEF.md`); `python ml/nlu/build_dataset.py` fills them with names, all districts, amounts and businesses.
- **Training:** `python ml/nlu/train.py` (GPU optional) prunes the multilingual-e5-small vocabulary to the app's scripts
  (~17.5k pieces), trains span tags + intent, exports ONNX and ships the smallest int8 variant within 0.01 of full
  precision (`public/models/nlu/`, ~28 MB). The app tokenizer and runner are checked against Python in `src/lib/nlp/nlp.test.ts`.
- **Result on the held-out hand-written messages (8 languages, 935 messages)** — what the chat keeps, rules alone vs rules + model:
  place 13% → 89%, name 0% → 93%, intent 54% → 87%, reason 27% → 87% (`src/core/nluModel.test.ts`). Amounts and business
  types stay rule-parsed. The rules remain the fallback when the model is slow or unavailable.

## Languages
Eight app languages: English, Hindi, Bangla, Tamil, Telugu, Punjabi, Kannada and Marathi. English and Hindi strings
are authored in `src/i18n/strings/`. The other six are in `src/i18n/locales/<code>.partN.json`, with the chat vocabulary
in `<code>.nlu.json`. Check a language with
`node scripts/check_locales.mjs <en.json> <code>`, which reports missing keys, placeholders, untranslated text and
script. `en.json` is a flat export of the English dictionary. Retrieved scheme and sector documents stay in English.

## Demo tips
- **Presenter controls:** tap the version line in More 7 times to show them (tap 7 times again to hide). Pick one of six example people (Bhadohi, Tiruppur, Murshidabad, Ludhiana, Nashik, Gaya); the controls offer checkpoints that load sample inputs (results are still computed), a "months pass" clock, and a choice of sample SMS inbox (typical year or monsoon disruption).
- **Voice:** uses the phone's own speech recognition and text-to-speech; you can always type.
- **Outcome records:** real records are saved on the phone when the user answers a follow-up; seed records appear as baseline counts.

## Develop and test
```bash
npm install
npm run dev          # http://localhost:5173
npm test             # 353 tests: engine and backend parity, core pipeline, i18n coverage
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
