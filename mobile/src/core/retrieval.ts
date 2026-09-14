/**
 * TF-IDF retrieval over the bundled RAG collections — a port of rag/vector_store.py:
 * sklearn TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True) with sklearn defaults
 * (lowercase, token pattern \b\w\w+\b, smooth idf = ln((1+n)/(1+df)) + 1, L2 norm), ranked by linear kernel
 * (cosine). The document text indexed is `${heading}\n${text}`, as in build_index.
 */
import { docs } from "./pack";
import type { PackDoc } from "./types";
import stopwordsJson from "./data/stopwords.json";

type Collection = PackDoc["collection"];
type SparseVec = Map<number, number>;

interface Index {
  chunks: PackDoc[];
  vocab: Map<string, number>;
  idf: Float64Array;
  rows: SparseVec[];
}

const STOP = new Set(stopwordsJson as string[]);
const TOKEN = /[\p{L}\p{N}_]{2,}/gu;

/** sklearn analyzer: lowercase → tokens (≥ 2 word chars) → drop stop words → unigrams + bigrams. */
export function analyze(text: string): string[] {
  const tokens = (text.toLowerCase().match(TOKEN) ?? []).filter((t) => !STOP.has(t));
  const grams = [...tokens];
  for (let i = 0; i + 1 < tokens.length; i++) grams.push(`${tokens[i]} ${tokens[i + 1]}`);
  return grams;
}

function counts(text: string): Map<string, number> {
  const c = new Map<string, number>();
  for (const g of analyze(text)) c.set(g, (c.get(g) ?? 0) + 1);
  return c;
}

function vectorize(termCounts: Map<string, number>, vocab: Map<string, number>, idf: Float64Array): SparseVec {
  const v: SparseVec = new Map();
  let norm = 0;
  for (const [term, tf] of termCounts) {
    const j = vocab.get(term);
    if (j === undefined) continue;
    const w = (1 + Math.log(tf)) * idf[j];
    v.set(j, w);
    norm += w * w;
  }
  norm = Math.sqrt(norm);
  if (norm > 0) for (const [j, w] of v) v.set(j, w / norm);
  return v;
}

const indexes = new Map<Collection, Index>();

function buildIndex(collection: Collection): Index {
  const chunks = docs(collection);
  const docCounts = chunks.map((c) => counts(`${c.heading}\n${c.text}`));
  const vocab = new Map<string, number>();
  const df: number[] = [];
  for (const dc of docCounts) {
    for (const term of dc.keys()) {
      let j = vocab.get(term);
      if (j === undefined) {
        j = vocab.size;
        vocab.set(term, j);
        df.push(0);
      }
      df[j]++;
    }
  }
  const n = chunks.length;
  const idf = Float64Array.from(df, (d) => Math.log((1 + n) / (1 + d)) + 1);
  const index: Index = { chunks, vocab, idf, rows: docCounts.map((dc) => vectorize(dc, vocab, idf)) };
  indexes.set(collection, index);
  return index;
}

/** Top-k chunks for `query` with cosine similarity ≥ minScore (scores rounded to 4 dp, like the backend). */
export function retrieve(collection: Collection, query: string, topK = 5, minScore = 0.05): (PackDoc & { score: number })[] {
  const index = indexes.get(collection) ?? buildIndex(collection);
  if (!index.chunks.length) return [];
  const q = vectorize(counts(query ?? ""), index.vocab, index.idf);
  const scores = index.rows.map((row) => {
    let s = 0;
    for (const [j, w] of q) s += w * (row.get(j) ?? 0);
    return s;
  });
  const ranked = scores.map((_, i) => i).sort((a, b) => scores[b] - scores[a]).slice(0, topK);
  return ranked
    .filter((i) => scores[i] >= minScore)
    .map((i) => ({ ...index.chunks[i], score: Math.round(scores[i] * 10000) / 10000 }));
}

/** Drop cached indexes (tests). */
export function resetRetrieval(): void {
  indexes.clear();
}
