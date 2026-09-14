/**
 * SentencePiece Unigram tokenizer for the on-device message model, reading the pruned Hugging Face tokenizer.json
 * written by ml/nlu/train.py (XLM-R style: nmt-NFKC normaliser, Metaspace "▁" pre-tokenizer, Unigram model,
 * <s> … </s> template). Viterbi segmentation per word maximises the summed piece log-probabilities; characters
 * with no piece become <unk> (consecutive unknowns fused), as in the tokenizers library.
 *
 * The precompiled normaliser is approximated by NFKC plus whitespace clean-up, which agrees with the Python tokenizer
 * on the app's scripts (checked in tokenizer.test.ts against ids exported by Python).
 */

export interface TokenizerSpec {
  model: { type: string; vocab: [string, number][]; unk_id: number };
  added_tokens?: { id: number; content: string }[];
}

export interface Encoding {
  ids: number[];
  /** [start, end) character offsets into the input text; [0, 0] for <s> and </s> */
  offsets: [number, number][];
}

const SPACE = "▁";

export class UnigramTokenizer {
  private pieces = new Map<string, [number, number]>(); // piece -> [id, score]
  private maxLen = 1;
  private unkId: number;
  private unkScore: number;
  private bos: number;
  private eos: number;

  constructor(spec: TokenizerSpec) {
    let min = Infinity;
    spec.model.vocab.forEach(([piece, score], id) => {
      this.pieces.set(piece, [id, score]);
      this.maxLen = Math.max(this.maxLen, [...piece].length);
      if (score < min) min = score;
    });
    this.unkId = spec.model.unk_id;
    this.unkScore = min - 10;
    const find = (s: string) => spec.added_tokens?.find((t) => t.content === s)?.id ?? this.pieces.get(s)?.[0] ?? 0;
    this.bos = find("<s>");
    this.eos = find("</s>");
  }

  /** Normalised words with their character offsets in the original text. */
  private words(text: string): { word: string; start: number; end: number }[] {
    const out: { word: string; start: number; end: number }[] = [];
    let cur = "";
    let start = -1;
    let i = 0;
    for (const ch of text) {
      const norm = ch.normalize("NFKC");
      // zero-width (non-)joiners break words, as the precompiled nmt-NFKC normaliser does
      const isSpace = /\s/u.test(ch) || ch === "‌" || ch === "‍" || norm.trim() === "";
      if (isSpace) {
        if (cur) out.push({ word: cur, start, end: i });
        cur = "";
        start = -1;
      } else if (!/\p{Cc}|\p{Cf}/u.test(ch)) {
        if (start < 0) start = i;
        cur += norm;
      }
      i += ch.length;
    }
    if (cur) out.push({ word: cur, start, end: i });
    return out;
  }

  encode(text: string): Encoding {
    const ids = [this.bos];
    const offsets: [number, number][] = [[0, 0]];
    for (const { word, start, end } of this.words(text.normalize("NFC"))) {
      const chars = [...(SPACE + word)];
      const n = chars.length;
      const best = new Array<number>(n + 1).fill(-Infinity);
      const back = new Array<[number, number]>(n + 1);
      best[0] = 0;
      for (let i = 0; i < n; i++) {
        if (best[i] === -Infinity) continue;
        let matched = false;
        let piece = "";
        for (let j = i; j < Math.min(n, i + this.maxLen); j++) {
          piece += chars[j];
          const hit = this.pieces.get(piece);
          if (!hit) continue;
          if (j === i) matched = true;
          const score = best[i] + hit[1];
          if (score > best[j + 1]) {
            best[j + 1] = score;
            back[j + 1] = [i, hit[0]];
          }
        }
        if (!matched && best[i] + this.unkScore > best[i + 1]) {
          best[i + 1] = best[i] + this.unkScore;
          back[i + 1] = [i, this.unkId];
        }
      }
      const seg: [number, number, number][] = [];
      for (let k = n; k > 0; k = back[k][0]) seg.unshift([back[k][0], k, back[k][1]]);
      // fuse consecutive unknowns
      const fused: [number, number, number][] = [];
      for (const s of seg) {
        const last = fused[fused.length - 1];
        if (last && last[2] === this.unkId && s[2] === this.unkId) last[1] = s[1];
        else fused.push([...s]);
      }
      // map piece character ranges (with the leading ▁ at index 0) back to the original word's offsets
      const wordChars = [...word];
      const origLen = end - start;
      for (const [a, b, id] of fused) {
        const ca = Math.max(0, a - 1);
        const cb = Math.max(0, b - 1);
        // proportional mapping when normalisation changed the length (rare for the app's scripts)
        const scale = wordChars.length ? origLen / wordChars.reduce((t, c) => t + c.length, 0) : 1;
        const pre = (k: number) => wordChars.slice(0, k).reduce((t, c) => t + c.length, 0);
        ids.push(id);
        offsets.push([start + Math.round(pre(ca) * scale), start + Math.round(pre(cb) * scale)]);
      }
    }
    ids.push(this.eos);
    offsets.push([0, 0]);
    return { ids, offsets };
  }
}
