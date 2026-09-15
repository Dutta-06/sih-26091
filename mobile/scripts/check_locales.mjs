// Validates src/i18n/locales/<lang>*.json against the English table exported to <en.json>.
// Usage: node scripts/check_locales.mjs <en.json> <lang> [...]
// Checks: every key present, no extra keys, identical {placeholders}, non-empty values, and that most values use the
// language's script (brand names, numbers and codes may stay Latin).
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const here = path.dirname(fileURLToPath(import.meta.url));
const dir = path.join(here, "..", "src", "i18n", "locales");
const [enPath, ...langs] = process.argv.slice(2);
const en = JSON.parse(fs.readFileSync(enPath, "utf8"));
const SCRIPT = { bn: /[ঀ-৿]/, ta: /[஀-௿]/, te: /[ఀ-౿]/, pa: /[਀-੿]/, kn: /[ಀ-೿]/, mr: /[ऀ-ॿ]/ };
const holes = (s) => [...s.matchAll(/\{[a-zA-Z0-9_]+\}/g)].map((m) => m[0]).sort().join(",");
let failed = false;
for (const lang of langs) {
  const table = {};
  for (const f of fs.readdirSync(dir).filter((f) => f.startsWith(`${lang}.`) && f.endsWith(".json") && !f.includes(".nlu."))) {
    Object.assign(table, JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));
  }
  const missing = Object.keys(en).filter((k) => !(k in table));
  const extra = Object.keys(table).filter((k) => !(k in en));
  const empty = Object.keys(table).filter((k) => !String(table[k]).trim());
  const badHoles = Object.keys(en).filter((k) => k in table && holes(en[k]) !== holes(String(table[k])));
  const latinOnly = Object.keys(en).filter((k) => k in table && /[a-z]{3,}/i.test(en[k]) && !SCRIPT[lang].test(String(table[k])) && table[k] !== en[k]);
  const untouched = Object.keys(en).filter((k) => k in table && table[k] === en[k] && /[a-z]{4,}\s+[a-z]{3,}/i.test(en[k]));
  const nlu = fs.existsSync(path.join(dir, `${lang}.nlu.json`));
  console.log(`${lang}: ${Object.keys(table).length}/${Object.keys(en).length} keys · missing ${missing.length} · extra ${extra.length} · empty ${empty.length} · placeholder mismatches ${badHoles.length} · untranslated sentences ${untouched.length} · wrong script ${latinOnly.length} · lexicon ${nlu ? "yes" : "NO"}`);
  for (const [label, list] of [["missing", missing], ["extra", extra], ["placeholders", badHoles], ["untranslated", untouched], ["script", latinOnly]]) {
    if (list.length) console.log(`  ${label}: ${list.slice(0, 12).join(", ")}${list.length > 12 ? " …" : ""}`);
  }
  if (missing.length || extra.length || empty.length || badHoles.length || !nlu) failed = true;
}
process.exit(failed ? 1 : 0);
