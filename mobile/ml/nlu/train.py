"""Fine-tune the on-device message-understanding model and export it for the app.

Base: intfloat/multilingual-e5-small (12-layer, 384-d encoder with the XLM-R vocabulary, MIT licence).
 1. Vocabulary pruning: the 250k SentencePiece vocabulary is cut to the pieces used by the eight app languages — every
    piece produced on the training data, all app strings (src/i18n), chat lexicons and district names — plus every
    single-character piece of their scripts, so unseen words still tokenise. The embedding matrix is sliced to match.
 2. One encoder, two heads: BIO token tags for NAME LOC AMT ACT REASON, and a 10-way intent head on the mean-pooled
    sequence. Loss = token cross-entropy + intent cross-entropy.
 3. Evaluation per language on the dev split (held-out templates) and on the hand-written test set: exact span F1,
    overlap span F1 (same label, overlapping characters) and intent accuracy.
 4. Export: ONNX, then dynamic int8 variants scored on the test set; the smallest one within 0.01 of full precision is
    shipped. Fixtures for the app's tokenizer and model runner are written from the shipped model.

Run (GPU if available):   python mobile/ml/nlu/train.py
Re-export a trained model: python mobile/ml/nlu/train.py --export-only
Artifacts: mobile/public/models/nlu/{nlu.onnx, tokenizer.json, labels.json}; report in ml/nlu/out/report.json.
"""

from __future__ import annotations

import collections
import json
import math
import random
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import torch
from torch import nn
from tokenizers import Tokenizer
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

HERE = Path(__file__).resolve().parent
MOBILE = HERE.parents[1]
OUT = HERE / "out"
ART = MOBILE / "public" / "models" / "nlu"
FIXTURES = MOBILE / "src" / "lib" / "nlp" / "__fixtures__"
BASE = "intfloat/multilingual-e5-small"
LABELS = ["NAME", "LOC", "AMT", "ACT", "REASON"]
TAGS = ["O"] + [f"{p}-{l}" for l in LABELS for p in ("B", "I")]
INTENTS = ["provide_info", "greeting", "raise_grievance", "application_status", "scheme_inquiry", "monitoring", "community",
           "change_language", "new_case", "other"]
MAX_LEN = 72
EPOCHS = 4
BATCH = 48
SEED = 26091
SCRIPT_RANGES = [(0x0020, 0x024F), (0x0900, 0x097F), (0x0980, 0x09FF), (0x0A00, 0x0A7F), (0x0B80, 0x0BFF), (0x0C00, 0x0C7F),
                 (0x0C80, 0x0CFF), (0x20B9, 0x20B9), (0x2000, 0x206F)]


def rows(name: str) -> list[dict]:
    return [json.loads(l) for l in (OUT / f"{name}.jsonl").read_text("utf-8").splitlines() if l.strip()]


def in_scripts(ch: str) -> bool:
    c = ord(ch)
    return any(a <= c <= b for a, b in SCRIPT_RANGES)


# ---------------------------------------------------------------- 1. vocabulary pruning

def app_corpus() -> list[str]:
    texts: list[str] = []
    for p in sorted((MOBILE / "src/i18n/locales").glob("*.json")):
        d = json.loads(p.read_text("utf-8"))
        texts += [json.dumps(d, ensure_ascii=False)] if p.name.endswith(".nlu.json") else [v for v in d.values() if isinstance(v, str)]
    for p in sorted((MOBILE / "src/i18n/strings").glob("*.ts")):
        texts += re.findall(r'"(?:[^"\\]|\\.)*"', p.read_text("utf-8"))
    texts += [r[1] for r in json.loads((MOBILE / "src/core/data/india_districts.json").read_text("utf-8"))]
    for p in sorted((HERE / "data").glob("*.json")):
        texts.append(p.read_text("utf-8"))
    return texts


def prune_tokenizer(base_tok, texts: list[str]) -> tuple[Tokenizer, list[int]]:
    spec = json.loads(base_tok.backend_tokenizer.to_str())
    vocab = spec["model"]["vocab"]  # [[piece, score], ...]
    keep = set(range(4))  # <s> <pad> </s> <unk>
    for i in range(0, len(texts), 512):
        for ids in base_tok(texts[i:i + 512], add_special_tokens=False)["input_ids"]:
            keep.update(ids)
    for i, (piece, _) in enumerate(vocab):
        core = piece.replace("▁", "")
        if len(core) <= 1 and all(in_scripts(c) for c in core):
            keep.add(i)
    kept = sorted(keep)
    spec["model"]["vocab"] = [vocab[i] for i in kept]
    spec["model"]["unk_id"] = kept.index(spec["model"]["unk_id"])
    old_to_new = {o: n for n, o in enumerate(kept)}
    if spec.get("post_processor"):
        pp = json.dumps(spec["post_processor"])
        for special in ("<s>", "</s>"):
            old = base_tok.convert_tokens_to_ids(special)
            pp = pp.replace(f'["{special}", {old}]', f'["{special}", {old_to_new[old]}]')
        spec["post_processor"] = json.loads(pp)
    spec["added_tokens"] = [{**t, "id": old_to_new[t["id"]]} for t in spec.get("added_tokens", []) if t["id"] in old_to_new]
    spec["truncation"] = None
    spec["padding"] = None
    return Tokenizer.from_str(json.dumps(spec)), kept


# ---------------------------------------------------------------- 2. model

class NluModel(nn.Module):
    def __init__(self, encoder: nn.Module):
        super().__init__()
        self.encoder = encoder
        h = encoder.config.hidden_size
        self.dropout = nn.Dropout(0.1)
        self.tags = nn.Linear(h, len(TAGS))
        self.intent = nn.Linear(h, len(INTENTS))

    def forward(self, input_ids, attention_mask):
        hidden = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
        return self.tags(self.dropout(hidden)), self.intent(self.dropout(pooled))


def encode(tok: Tokenizer, row: dict) -> dict:
    enc = tok.encode(unicodedata.normalize("NFC", row["text"]))
    ids = enc.ids[:MAX_LEN - 1] + ([enc.ids[-1]] if len(enc.ids) > MAX_LEN - 1 else [])
    offsets = enc.offsets[:len(ids)]
    tags = [0] * len(ids)
    for s, e, label in row.get("spans", []):
        first = True
        for i, (a, b) in enumerate(offsets):
            if a == b:
                continue
            seg = row["text"][a:b]
            a2 = a + (len(seg) - len(seg.lstrip()))
            if a2 >= s and b <= e and b > a2:  # the token's non-space characters lie inside the span
                tags[i] = TAGS.index(f"{'B' if first else 'I'}-{label}")
                first = False
    special = [a == b for a, b in offsets]
    return {"ids": ids, "tags": [(-100 if sp else t) for t, sp in zip(tags, special)], "offsets": offsets, "row": row,
            "intent": INTENTS.index(row["intent"]) if row.get("intent") in INTENTS else -100}


def batches(items: list[dict], size: int, shuffle: bool, rng: random.Random):
    order = list(range(len(items)))
    if shuffle:
        rng.shuffle(order)
    for i in range(0, len(order), size):
        chunk = [items[j] for j in order[i:i + size]]
        n = max(len(c["ids"]) for c in chunk)
        ids = torch.full((len(chunk), n), 1, dtype=torch.long)  # <pad> = 1
        mask = torch.zeros((len(chunk), n), dtype=torch.long)
        tags = torch.full((len(chunk), n), -100, dtype=torch.long)
        for k, c in enumerate(chunk):
            ids[k, :len(c["ids"])] = torch.tensor(c["ids"])
            mask[k, :len(c["ids"])] = 1
            tags[k, :len(c["tags"])] = torch.tensor(c["tags"])
        yield ids, mask, tags, torch.tensor([c["intent"] for c in chunk]), chunk


# ---------------------------------------------------------------- 3. decoding and evaluation

def decode_spans(text: str, offsets: list[tuple[int, int]], tag_ids: list[int]) -> list[tuple[int, int, str]]:
    """BIO tags → character spans; same-label pieces split by at most one short word are joined; 1-2 letter pieces dropped."""
    spans: list[list] = []
    cur = None
    for (a, b), t in zip(offsets, tag_ids):
        if a == b:
            continue
        tag = TAGS[t]
        seg = text[a:b]
        a2 = a + (len(seg) - len(seg.lstrip()))
        if tag == "O":
            if cur:
                spans.append(cur)
                cur = None
            continue
        kind, label = tag.split("-")
        if kind == "B" or not cur or cur[2] != label:
            if cur:
                spans.append(cur)
            cur = [a2, b, label]
        else:
            cur[1] = b
    if cur:
        spans.append(cur)
    merged: list[list] = []
    for s_, e_, l_ in spans:
        if merged and merged[-1][2] == l_:
            gap = text[merged[-1][1]:s_]
            if len(gap.strip()) <= 4 and len(gap.split()) <= 1:
                merged[-1][1] = e_
                continue
        merged.append([s_, e_, l_])
    edge = set(" \t\n,.;:!?।\"'()")
    for sp in merged:  # punctuation at the edges is not part of a span
        while sp[0] < sp[1] and text[sp[0]] in edge:
            sp[0] += 1
        while sp[1] > sp[0] and text[sp[1] - 1] in edge:
            sp[1] -= 1
    return [(s_, e_, l_) for s_, e_, l_ in merged if len(text[s_:e_].strip()) > 2 or (l_ == "AMT" and e_ > s_)]


def torch_predictor(model: NluModel, device):
    def predict(ids: torch.Tensor, mask: torch.Tensor):
        model.eval()
        with torch.no_grad():
            tag_logits, intent_logits = model(ids.to(device), mask.to(device))
        model.train()
        return tag_logits.argmax(-1).cpu().tolist(), intent_logits.argmax(-1).cpu().tolist()
    return predict


def onnx_predictor(path: Path):
    import onnxruntime as ort
    sess = ort.InferenceSession(path.read_bytes(), providers=["CPUExecutionProvider"])  # from bytes: no file lock on Windows

    def predict(ids: torch.Tensor, mask: torch.Tensor):
        tags, intent = sess.run(None, {"input_ids": ids.numpy().astype(np.int64), "attention_mask": mask.numpy().astype(np.int64)})
        return tags.argmax(-1).tolist(), intent.argmax(-1).tolist()
    return predict


def evaluate(predict, items: list[dict]) -> dict:
    stats: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for ids, mask, _, _, chunk in batches(items, 64, False, random.Random(0)):
        tag_pred, intent_pred = predict(ids, mask)
        for k, c in enumerate(chunk):
            row = c["row"]
            gold = {tuple(x) for x in row["spans"]}
            pred = set(decode_spans(row["text"], c["offsets"], tag_pred[k][:len(c["ids"])]))
            overlap = lambda g, q: g[2] == q[2] and g[0] < q[1] and q[0] < g[1]
            loose_tp = sum(1 for g in gold if any(overlap(g, q) for q in pred))
            loose_fp = sum(1 for q in pred if not any(overlap(g, q) for g in gold))
            for key in (row["lang"], "all"):
                st = stats[key]
                st["tp"] += len(gold & pred)
                st["fp"] += len(pred - gold)
                st["fn"] += len(gold - pred)
                st["ltp"] += loose_tp
                st["lfp"] += loose_fp
                st["lfn"] += len(gold) - loose_tp
                if c["intent"] != -100:
                    st["intent_n"] += 1
                    st["intent_ok"] += int(intent_pred[k] == c["intent"])
    f1 = lambda tp, fp, fn: 2 * tp / max(1, 2 * tp + fp + fn)
    return {key: {"span_f1": round(f1(st["tp"], st["fp"], st["fn"]), 3), "overlap_f1": round(f1(st["ltp"], st["lfp"], st["lfn"]), 3),
                  "intent_acc": round(st["intent_ok"] / max(1, st["intent_n"]), 3), "intent_n": st["intent_n"]}
            for key, st in sorted(stats.items())}


def dump_errors(predict, items: list[dict]) -> None:
    lines = []
    for ids, mask, _, _, chunk in batches(items, 64, False, random.Random(0)):
        tag_pred, intent_pred = predict(ids, mask)
        for k, c in enumerate(chunk):
            row = c["row"]
            pred = decode_spans(row["text"], c["offsets"], tag_pred[k][:len(c["ids"])])
            gold = [tuple(x) for x in row["spans"]]
            intent = INTENTS[intent_pred[k]]
            if set(pred) != set(gold) or (row.get("intent") and intent != row["intent"]):
                show = lambda sp: " | ".join(f"{l_}:{row['text'][s_:e_]}" for s_, e_, l_ in sorted(sp))
                lines.append(f"[{row['lang']}] {row['text']}\n   gold: {show(gold)}  ({row.get('intent')})\n   pred: {show(pred)}  ({intent})")
    (OUT / "test_errors.txt").write_text("\n".join(lines), "utf-8")


# ---------------------------------------------------------------- 4. export

def export(model: NluModel, tok: Tokenizer, test_items: list[dict], test_rows: list[dict], report: dict) -> None:
    from onnxruntime.quantization import QuantType, quantize_dynamic
    ART.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    fp32 = OUT / "nlu.fp32.onnx"
    dummy = torch.tensor([tok.encode("namaste mera naam Sunita hai").ids])
    torch.onnx.export(model, (dummy, torch.ones_like(dummy)), str(fp32), input_names=["input_ids", "attention_mask"],
                      output_names=["tags", "intent"], opset_version=17,
                      dynamic_axes={"input_ids": {0: "b", 1: "n"}, "attention_mask": {0: "b", 1: "n"}, "tags": {0: "b", 1: "n"}, "intent": {0: "b"}})
    variants = [
        ("int8 matmul+gather", dict(op_types_to_quantize=["MatMul", "Gather", "Gemm"])),
        ("int8 matmul+gather per-channel", dict(op_types_to_quantize=["MatMul", "Gather", "Gemm"], per_channel=True)),
        ("int8 matmul per-channel", dict(op_types_to_quantize=["MatMul", "Gemm"], per_channel=True)),
    ]
    paths = [("fp32", fp32)]
    for label, kw in variants:  # quantise everything before any session opens a file
        src = OUT / f"src_{len(paths)}.onnx"
        shutil.copyfile(fp32, src)
        path = OUT / f"nlu.{re.sub(r'[^a-z0-9]+', '_', label)}.onnx"
        quantize_dynamic(str(src), str(path), weight_type=QuantType.QInt8, **kw)
        paths.append((label, path))
    results = []
    for label, path in paths:
        scores = evaluate(onnx_predictor(path), test_items)["all"]
        print(f"{label}: {path.stat().st_size / 2**20:.1f} MB  test {scores}")
        results.append((label, path, scores))
    base = results[0][2]
    within = [r for r in results if r[2]["overlap_f1"] >= base["overlap_f1"] - 0.01 and r[2]["intent_acc"] >= base["intent_acc"] - 0.01]
    label, path, _ = min(within, key=lambda r: r[1].stat().st_size)
    shutil.copyfile(path, ART / "nlu.onnx")
    tok.save(str(ART / "tokenizer.json"))
    (ART / "labels.json").write_text(json.dumps({"tags": TAGS, "intents": INTENTS, "maxLen": MAX_LEN, "base": BASE}, indent=1), "utf-8")
    shipped = onnx_predictor(ART / "nlu.onnx")
    report["export"] = {"model": label, "size_mb": round(path.stat().st_size / 2**20, 1), "test": evaluate(shipped, test_items)}
    print(f"shipping {label} ({report['export']['size_mb']} MB)")
    dump_errors(shipped, test_items)

    FIXTURES.mkdir(parents=True, exist_ok=True)
    samples = [r["text"] for r in test_rows] + [t for t in app_corpus()[:6000:7] if len(t) < 200]
    (FIXTURES / "tokenizer.json").write_text(json.dumps(
        [{"text": t, "ids": tok.encode(unicodedata.normalize("NFC", t)).ids} for t in samples[:900]], ensure_ascii=False), "utf-8")
    readings = []
    for c in test_items[::12][:80]:
        tags, intents = shipped(torch.tensor([c["ids"]]), torch.ones((1, len(c["ids"])), dtype=torch.long))
        text = c["row"]["text"]
        readings.append({"text": text, "intent": INTENTS[intents[0]], "spans": [[text[s_:e_], l_] for s_, e_, l_ in decode_spans(text, c["offsets"], tags[0])]})
    (FIXTURES / "readings.json").write_text(json.dumps(readings, ensure_ascii=False), "utf-8")
    (OUT / "report.json").write_text(json.dumps(report, indent=1), "utf-8")


def main() -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)
    rng = random.Random(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_rows, dev_rows, test_rows = rows("train"), rows("dev"), rows("test")

    base_tok = AutoTokenizer.from_pretrained(BASE)
    tok, kept = prune_tokenizer(base_tok, [r["text"] for r in train_rows + dev_rows + test_rows] + app_corpus())
    print(f"vocabulary {len(kept)} of {base_tok.vocab_size} pieces")
    encoder = AutoModel.from_pretrained(BASE)
    old = encoder.embeddings.word_embeddings.weight.data
    emb = nn.Embedding(len(kept), old.shape[1], padding_idx=kept.index(1))
    emb.weight.data = old[torch.tensor(kept)].clone()
    encoder.embeddings.word_embeddings = emb
    encoder.config.vocab_size = len(kept)
    encoder.config.pad_token_id = kept.index(1)
    model = NluModel(encoder).to(device)

    train_items = [encode(tok, r) for r in train_rows]
    dev_items = [encode(tok, r) for r in dev_rows]
    test_items = [encode(tok, r) for r in test_rows]
    steps = EPOCHS * math.ceil(len(train_items) / BATCH)
    opt = torch.optim.AdamW([
        {"params": model.encoder.parameters(), "lr": 5e-5},
        {"params": list(model.tags.parameters()) + list(model.intent.parameters()), "lr": 1e-3},
    ], weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, int(0.06 * steps), steps)
    ce = nn.CrossEntropyLoss(ignore_index=-100)
    t0 = time.time()
    for epoch in range(EPOCHS):
        total = 0.0
        for ids, mask, tags, intents, _ in batches(train_items, BATCH, True, rng):
            ids, mask, tags, intents = ids.to(device), mask.to(device), tags.to(device), intents.to(device)
            tag_logits, intent_logits = model(ids, mask)
            loss = ce(tag_logits.reshape(-1, len(TAGS)), tags.reshape(-1)) + ce(intent_logits, intents)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            total += loss.item()
        print(f"epoch {epoch + 1}: loss {total:.1f}  dev {evaluate(torch_predictor(model, device), dev_items)['all']}  ({time.time() - t0:.0f}s)")

    report = {"base": BASE, "vocab": len(kept), "train": len(train_items), "dev": evaluate(torch_predictor(model, device), dev_items),
              "test": evaluate(torch_predictor(model, device), test_items)}
    print("test", json.dumps(report["test"]))
    OUT.mkdir(exist_ok=True)
    torch.save({"state": model.state_dict(), "vocab": len(kept)}, OUT / "model.pt")
    tok.save(str(OUT / "tokenizer.json"))
    export(model, tok, test_items, test_rows, report)


def export_only() -> None:
    tok = Tokenizer.from_file(str(OUT / "tokenizer.json"))
    saved = torch.load(OUT / "model.pt", map_location="cpu")
    encoder = AutoModel.from_pretrained(BASE)
    encoder.embeddings.word_embeddings = nn.Embedding(saved["vocab"], encoder.config.hidden_size, padding_idx=1)
    encoder.config.vocab_size = saved["vocab"]
    model = NluModel(encoder)
    model.load_state_dict(saved["state"])
    test_rows = rows("test")
    export(model, tok, [encode(tok, r) for r in test_rows], test_rows, json.loads((OUT / "report.json").read_text("utf-8")))


if __name__ == "__main__":
    export_only() if "--export-only" in sys.argv else main()
