"""Parity fixtures for role C1 (retrieval, NLU, language detection) from the real backend functions.

Run:  python mobile/scripts/export_parity_c1.py   -> mobile/src/core/__fixtures__/c1.json
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_MODE", "offline")

from common.reference import load_catalog  # noqa: E402
from orchestrator.language import detect_language  # noqa: E402
from orchestrator.router import extract_slots_from_text, parse_intent  # noqa: E402
from rag.vector_store import retrieve  # noqa: E402

QUERIES = [
    "handloom weaving competition in a weaving cluster",
    "tailoring demand school uniforms wedding season",
    "working capital shortage and delayed payments from buyers",
    "documents required for the loan application",
    "interest rate moratorium and repayment schedule for term loan",
    "milk price seasonality and fodder cost",
    "power cuts electricity for flour mill",
    "honey beekeeping litchi flowering",
]

UTTERANCES = [
    ("I want to start tailoring in Gopiganj with 12,000 rupees because I know silai", None),
    ("I have 1 lakh and want a dairy in Bhadohi", None),
    ("1.5 लाख", None),
    ("मेरे पास 50000 रुपये हैं", None),
    ("₹ 12,000", None),
    ("₹12k", None),
    ("50 lakh", None),
    ("2 crore", None),
    ("0", "capital"),
    ("0", None),
    ("-500", None),
    ("500", "capital"),
    ("twelve thousand", "capital"),
    ("", None),
    ("🙂🙏", None),
    ("Gopiganj", "location"),
    ("near Varanasi", None),
    ("Bhadohi mein silai ka kaam", None),
    ("मैं गोपीगंज में सिलाई करना चाहती हूँ", None),
    ("बकरी पालन", None),
    ("I want to open a beauty parlour since women here need one", None),
    ("I have been weaving for years", None),
    ("hotel business", None),
    ("mobile repair shop at Nashik", None),
    ("I want to raise a complaint, my machine is broken", None),
    ("मेरी शिकायत है", None),
    ("what is my application status", None),
    ("tell me about the scheme subsidy", None),
    ("I consent", None),
    ("start over", None),
    ("how is my business doing", None),
    ("hello", None),
    ("20 hazaar hai mere paas", None),
    ("mere paas 30 hajar hai aur Jaunpur mein rehti hoon", None),
    ("I can invest 25,000 in a kirana store in Mirzapur", None),
    ("10000", "capital"),
    ("7,50,000", None),
    ("fish farming in Prayagraj kyunki talab hai", None),
    ("I live at Dharwad and want a flour mill", None),
    ("the loan interest rate for 1 lakh scheme", None),
    ("x" * 300 + " in Gaya with 40000", None),
    ("দুধ বিক্রি করতে চাই", None),
    ("நான் தையல் தொழில் தொடங்க விரும்புகிறேன்", None),
]

catalog_by_category = {a["category"]: a["id"] for a in load_catalog().values()}

INTENT_MAP = {"jump_application": "application_status", "jump_monitoring": "monitoring", "inquire_scheme": "scheme_inquiry",
              "consent_monitoring": "monitoring", "continue": "unknown"}

retrieval = []
for q in QUERIES:
    for collection in ("sector_reports", "risk_taxonomy", "scheme_guidelines"):
        retrieval.append({"collection": collection, "query": q,
                          "results": [{"source": c.source.replace("\\", "/"), "heading": c.heading, "score": c.score}
                                      for c in retrieve(collection, q)]})

nlu = []
for text, pending in UTTERANCES:
    slots = extract_slots_from_text(text, pending)
    pref = slots.get("business_preference")
    nlu.append({
        "text": text, "pending": pending,
        "capital": slots.get("available_capital"),
        "activityId": catalog_by_category.get(pref) if pref else None,
        "rawPreference": pref if pref and pref not in catalog_by_category else None,
        "locationText": slots.get("location_query"),
        "reason": slots.get("preference_reason"),
        "intent": INTENT_MAP.get(parse_intent(text), parse_intent(text)),
        "language": detect_language(text),
    })

out = ROOT / "mobile" / "src" / "core" / "__fixtures__" / "c1.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"retrieval": retrieval, "nlu": nlu}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {out} ({len(retrieval)} retrieval cases, {len(nlu)} utterances)")
