"""Training data for the on-device message-understanding model (spans + intent), eight languages.

Inputs (ml/nlu/data/<lang>.json, written per language from ml/nlu/BRIEF.md): templates with {NAME} {LOC} {AMT} {ACT}
{REASON} slots, slot fillers, intent examples, and a separately written test set with inline [LABEL text] markup.
Extra fillers come from the app: all Census 2011 district names (src/core/data/india_districts.json) and the number
words of the chat lexicons (src/i18n/locales/<lang>.nlu.json).

Outputs (ml/nlu/out/): train.jsonl, dev.jsonl (generated; dev uses held-out templates), test.jsonl (the hand-written
test set, never used for training). Each row: {"lang", "text", "spans": [[start, end, label]], "intent"}.

Run: python mobile/ml/nlu/build_dataset.py
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOBILE = HERE.parents[1]
DATA = HERE / "data"
OUT = HERE / "out"
LANGS = ["en", "hi", "bn", "ta", "te", "pa", "kn", "mr"]
LABELS = ["NAME", "LOC", "AMT", "ACT", "REASON"]
INTENTS = ["provide_info", "greeting", "raise_grievance", "application_status", "scheme_inquiry", "monitoring", "community",
           "change_language", "new_case", "other"]
PER_TEMPLATE = 14          # filled variants per template
INTENT_REPEAT = 6          # noisy variants per intent example
SEED = 26091

SLOT = re.compile(r"\{(NAME|LOC|AMT|ACT|REASON)\}")
MARK = re.compile(r"\[(NAME|LOC|AMT|ACT|REASON) ([^\[\]]+?)\]")


def load(lang: str) -> dict | None:
    p = DATA / f"{lang}.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def numbers(rng: random.Random) -> str:
    n = rng.choice([500, 1000, 2000, 2500, 3000, 5000, 7500, 8000, 10000, 12000, 15000, 18000, 20000, 25000, 30000, 40000,
                    50000, 60000, 75000, 80000, 100000, 125000, 150000, 200000, 250000, 300000, 500000, rng.randint(1, 99) * 1000])
    style = rng.random()
    if style < 0.4:
        return str(n)
    if style < 0.7:
        return f"{n:,}"
    if n % 100000 == 0 or n >= 100000:
        return str(round(n / 100000, 1)).rstrip("0").rstrip(".")
    return str(n // 1000)


def fill_amount(pattern: str, rng: random.Random) -> str:
    return pattern.replace("{n}", numbers(rng)) if "{n}" in pattern else pattern


def noisy(text: str, spans: list[list], rng: random.Random) -> tuple[str, list[list]]:
    """Voice-typing style noise that keeps span offsets valid: lower-casing, dropped punctuation, doubled spaces."""
    chars = list(text)
    keep = [True] * len(chars)
    r = rng.random()
    if r < 0.35:  # drop most punctuation outside digits
        for i, c in enumerate(chars):
            if c in ",.!?।" and not (0 < i < len(chars) - 1 and chars[i - 1].isdigit() and chars[i + 1].isdigit()):
                keep[i] = rng.random() < 0.2
    out, mapping = [], []
    for i, c in enumerate(chars):
        mapping.append(len(out))
        if keep[i]:
            out.append(c)
    mapping.append(len(out))
    new = "".join(out)
    new_spans = [[mapping[s], mapping[e], l] for s, e, l in spans]
    if rng.random() < 0.3:
        new = new.lower()
    # collapse whitespace while tracking offsets
    final, remap = [], []
    prev_space = False
    for c in new:
        remap.append(len(final))
        if c.isspace():
            if prev_space:
                continue
            prev_space = True
            final.append(" ")
        else:
            prev_space = False
            final.append(c)
    remap.append(len(final))
    text2 = "".join(final)
    spans2 = []
    for s, e, l in new_spans:
        s2, e2 = remap[s], remap[e]
        while s2 < e2 and text2[s2] == " ":
            s2 += 1
        while e2 > s2 and text2[e2 - 1] == " ":
            e2 -= 1
        if e2 > s2:
            spans2.append([s2, e2, l])
    lead = len(text2) - len(text2.lstrip())
    text3 = text2.strip()
    return text3, [[s - lead, e - lead, l] for s, e, l in spans2 if e - lead <= len(text3) and s - lead >= 0]


def render(template: str, fillers: dict[str, str]) -> tuple[str, list[list]]:
    text, spans, pos = "", [], 0
    for m in SLOT.finditer(template):
        text += template[pos:m.start()]
        value = fillers[m.group(1)]
        spans.append([len(text), len(text) + len(value), m.group(1)])
        text += value
        pos = m.end()
    text += template[pos:]
    return text, spans


def parse_markup(s: str) -> tuple[str, list[list]]:
    text, spans, pos = "", [], 0
    for m in MARK.finditer(s):
        text += s[pos:m.start()]
        value = m.group(2).strip()
        spans.append([len(text), len(text) + len(value), m.group(1)])
        text += value
        pos = m.end()
    text += s[pos:]
    return unicodedata.normalize("NFC", text), spans


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(exist_ok=True)
    districts = json.loads((MOBILE / "src/core/data/india_districts.json").read_text("utf-8"))
    district_names = [re.sub(r"\s*\(.*\)", "", r[1]) for r in districts]
    states = sorted({r[2] for r in districts})
    train, dev, test = [], [], []
    for lang in LANGS:
        d = load(lang)
        if not d:
            print(f"{lang}: no data yet")
            continue
        lex_path = MOBILE / f"src/i18n/locales/{lang}.nlu.json"
        lex = json.loads(lex_path.read_text("utf-8")) if lex_path.exists() else {}
        num_words = list((lex.get("numberWords") or {}).keys())
        lakh = (lex.get("lakh") or ["lakh"])[0]
        thousand = (lex.get("thousand") or ["thousand"])[0]
        places = d["places"] + [rng.choice(district_names) + rng.choice(["", f", {rng.choice(states)}"]) for _ in range(len(d["places"]))]
        acts = [(aid, p) for aid, ps in d["activities"].items() for p in ps]
        amounts = d["amounts"] + [f"{w} {lakh}" for w in num_words[:12]] + [f"{w} {thousand}" for w in num_words[:20]]
        templates = d["templates"][:]
        rng.shuffle(templates)
        n_dev = max(10, len(templates) // 10)
        for split, temps in (("dev", templates[:n_dev]), ("train", templates[n_dev:])):
            target = dev if split == "dev" else train
            reps = 4 if split == "dev" else PER_TEMPLATE
            for t in temps:
                for _ in range(reps):
                    fillers = {"NAME": rng.choice(d["names"]), "LOC": rng.choice(places), "AMT": fill_amount(rng.choice(amounts), rng),
                               "ACT": rng.choice(acts)[1], "REASON": rng.choice(d["reasons"])}
                    text, spans = render(t, fillers)
                    text, spans = noisy(unicodedata.normalize("NFC", text), spans, rng)
                    target.append({"lang": lang, "text": text, "spans": spans, "intent": "provide_info"})
            # bare slot answers ("Coimbatore", "15000") as replies to a question
            if split == "train":
                for _ in range(60):
                    label = rng.choice(["LOC", "AMT", "NAME", "ACT"])
                    value = {"LOC": rng.choice(places), "AMT": fill_amount(rng.choice(amounts), rng), "NAME": rng.choice(d["names"]), "ACT": rng.choice(acts)[1]}[label]
                    target.append({"lang": lang, "text": value, "spans": [[0, len(value), label]], "intent": "provide_info"})
        for intent, examples in d["intents"].items():
            if intent not in INTENTS:
                continue
            ex = examples[:]
            rng.shuffle(ex)
            cut = max(3, len(ex) // 8)
            for e in ex[:cut]:
                dev.append({"lang": lang, "text": unicodedata.normalize("NFC", e), "spans": [], "intent": intent})
            for e in ex[cut:]:
                for _ in range(INTENT_REPEAT):
                    text, _ = noisy(unicodedata.normalize("NFC", e), [], rng)
                    train.append({"lang": lang, "text": text, "spans": [], "intent": intent})
        for s in d["test"]:
            text, spans = parse_markup(s)
            test.append({"lang": lang, "text": text, "spans": spans, "intent": "provide_info" if spans else None})
        for text, intent in d["testIntents"]:
            if intent in INTENTS:
                clean, spans = parse_markup(text)
                test.append({"lang": lang, "text": clean, "spans": spans, "intent": intent})
        print(f"{lang}: templates {len(d['templates'])}, test {len(d['test'])} + {len(d['testIntents'])}")
    rng.shuffle(train)
    for name, rows in (("train", train), ("dev", dev), ("test", test)):
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"train {len(train)}, dev {len(dev)}, test {len(test)}")


if __name__ == "__main__":
    main()
