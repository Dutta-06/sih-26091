/**
 * Transaction-alert (SMS) parser — exact port of data_connectors/sms_parser.py — plus a seeded simulator that
 * writes realistic raw bank / UPI alert strings for a plan (sample data), which the parser then reads back.
 *
 * Python's `re` is Unicode-aware for str patterns (\b and \d see Devanagari letters/digits); JS is not, so
 * patterns are compiled with the `u` flag, \d → \p{Nd} and \b → a Unicode word-boundary assertion.
 */
import catalog from "../../../data/reference/business_catalog.json";
import type { FinancialResult, Transaction } from "./types";

const W = "[\\p{L}\\p{N}_]";
const B = `(?:(?<=${W})(?!${W})|(?<!${W})(?=${W}))`;
/** Compile a Python-flavoured pattern with Unicode \b / \d semantics. */
export function pyRe(src: string, flags = ""): RegExp {
  return new RegExp(src.replace(/\\b/g, B).replace(/\\d/g, "\\p{Nd}"), flags.includes("u") ? flags : flags + "u");
}

const MONTHS: Record<string, number> = Object.fromEntries(
  ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].map((m, i) => [m, i + 1]),
);

const SKIP = pyRe(
  "\\botp\\b|one[\\s-]?time[\\s-]?password|verification code|pre-?approved|apply now|limited period|" +
    "\\boffer\\b|congratulations|\\bwin\\b|lucky draw|will be debited|due on|is due|request(ed)? money|collect request",
  "i",
);
const AMOUNT = "(?:rs\\.?|inr|₹)\\s*([\\d,]+(?:\\.\\d{1,2})?)";
const CREDIT = pyRe("\\bcredited\\b|\\breceived\\b|\\bdeposited\\b|\\bcr\\b", "i");
const DEBIT = pyRe("\\bdebited\\b|\\bwithdrawn\\b|\\bpaid\\b|\\bspent\\b|\\bsent\\b|\\bdr\\b|\\bpurchase\\b|\\btransferred\\b", "i");
const LOAN = pyRe("\\bemi\\b|\\bloan\\b|repayment|\\binstal+ment\\b|\\bnach\\b|\\becs\\b", "i");
const CHANNELS: [Transaction["channel"], RegExp][] = [
  ["upi", pyRe("\\bupi\\b|\\bvpa\\b|@[a-z]{2,}", "i")],
  ["neft_imps", pyRe("\\bneft\\b|\\bimps\\b|\\brtgs\\b", "i")],
  ["cash_deposit", pyRe("cash dep|\\bcdm\\b|cash deposit", "i")],
  ["atm", pyRe("\\batm\\b|withdrawn", "i")],
  ["card", pyRe("\\bcard\\b|\\bpos\\b", "i")],
];
const DATE_NUM = "\\b(\\d{1,2})[-/.](\\d{1,2})[-/.](\\d{4}|\\d{2})\\b";
const DATE_MON = "\\b(\\d{1,2})[-\\s]?([A-Za-z]{3})[a-z]*[-\\s,]*(\\d{4}|\\d{2})\\b";

const ZEROS = [0x30, 0x660, 0x6f0, 0x966, 0x9e6, 0xa66, 0xae6, 0xb66, 0xbe6, 0xc66, 0xce6, 0xd66, 0xff10];
/** int()/float() in Python accept any Unicode decimal digits. */
function asciiDigits(s: string): string {
  return s.replace(/\p{Nd}/gu, (ch) => {
    const c = ch.codePointAt(0)!;
    const z = ZEROS.find((z0) => c >= z0 && c <= z0 + 9);
    return z === undefined ? ch : String(c - z);
  });
}

const year = (t: string) => {
  const y = parseInt(asciiDigits(t), 10);
  return y < 100 ? y + 2000 : y;
};

function validDate(y: number, m: number, d: number): string | null {
  if (y < 1 || y > 9999 || m < 1 || m > 12 || d < 1) return null;
  const max = m === 2 ? (isLeap(y) ? 29 : 28) : [31, 0, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];
  if (d > max) return null;
  return `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}T00:00:00+00:00`;
}
const isLeap = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;

function parseDate(text: string): string | null {
  for (const m of text.matchAll(pyRe(DATE_MON, "gi"))) {
    const month = MONTHS[m[2].toLowerCase()];
    if (month) {
      const iso = validDate(year(m[3]), month, parseInt(asciiDigits(m[1]), 10));
      if (iso) return iso;
    }
  }
  for (const m of text.matchAll(pyRe(DATE_NUM, "g"))) {
    // Indian alerts use day-first dates
    const iso = validDate(year(m[3]), parseInt(asciiDigits(m[2]), 10), parseInt(asciiDigits(m[1]), 10));
    if (iso) return iso;
  }
  return null;
}

function amount(text: string): number | null {
  for (const m of text.matchAll(pyRe(AMOUNT, "gi"))) {
    if (/bal|limit/i.test(text.slice(Math.max(0, m.index! - 14), m.index!))) continue; // balance / credit limit
    const value = parseFloat(asciiDigits(m[1].replace(/,/g, "")));
    if (value > 0) return value;
  }
  return null;
}

const r2 = (v: number) => Math.round((v + Number.EPSILON) * 100) / 100;

/** One alert → transaction, or null for OTP / promotional / unrecognised text. `now` stands in for a missing date. */
export function parseOne(message: string, now: Date = new Date()): Transaction | null {
  if (!message || SKIP.test(message)) return null;
  const value = amount(message);
  const credit = CREDIT.exec(message);
  const debit = DEBIT.exec(message);
  if (value === null || !(credit || debit)) return null;
  const direction = credit && (!debit || credit.index < debit.index) ? "credit" : "debit";
  const channel = CHANNELS.find(([, rx]) => rx.test(message))?.[0] ?? "other";
  return {
    at: parseDate(message) ?? now.toISOString().replace("Z", "+00:00"),
    direction,
    amount: r2(value),
    channel,
    isLoanRepayment: direction === "debit" && LOAN.test(message),
  };
}

/** Parse alerts into structured records; unrecognised, OTP and promotional messages are dropped. */
export function parseNotifications(messages: string[], now: Date = new Date()): Transaction[] {
  return messages.map((m) => parseOne(m, now)).filter((t): t is Transaction => t !== null);
}

/* ------------------------------------------------------------------ simulator (sample data) */

/** mulberry32 — small seeded PRNG so simulated alerts are reproducible. */
export function prng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Indian digit grouping with two decimals: 108000 → "1,08,000.00". */
export function inr(v: number): string {
  const [int, dec] = v.toFixed(2).split(".");
  const last3 = int.slice(-3);
  const rest = int.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${rest ? rest + "," : ""}${last3}.${dec}`;
}

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const p2 = (n: number) => String(n).padStart(2, "0");
const daysIn = (y: number, m: number) => new Date(Date.UTC(y, m + 1, 0)).getUTCDate(); // m 0-11

function fmtDate(y: number, m: number, d: number, style: number): string {
  switch (style % 4) {
    case 0: return `${p2(d)}-${p2(m + 1)}-${String(y).slice(2)}`;
    case 1: return `${p2(d)}${MON[m]}${String(y).slice(2)}`;
    case 2: return `${p2(d)}-${MON[m]}-${y}`;
    default: return `${p2(d)}/${p2(m + 1)}/${y}`;
  }
}

const PAYERS = ["ramesh.k", "sunitadevi", "pooja12", "anil.verma", "meena.s", "rahulgupta", "kavita88", "suresh.y"];
const HANDLES = ["okaxis", "ybl", "oksbi", "paytm", "okhdfcbank"];
const SUPPLIERS = ["kapdaghar", "shreetraders", "maakirana", "agrosupply"];

/** Split `total` into n positive whole-rupee parts with random weights (last part absorbs rounding). */
function split(total: number, n: number, rnd: () => number): number[] {
  const w = Array.from({ length: n }, () => 0.5 + rnd());
  const s = w.reduce((a, b) => a + b, 0);
  const parts = w.map((x) => Math.max(1, Math.round((total * x) / s)));
  parts[n - 1] = Math.max(1, Math.round(total) - parts.slice(0, -1).reduce((a, b) => a + b, 0));
  return parts;
}

/**
 * Raw alert strings for `months` calendar months from `startMonth` (YYYY-MM, taken as the disbursement month).
 * Revenue per month = base projection × days/365 × catalog/risk seasonal factor (raw, as the monitoring baseline)
 * × seeded noise (±6%); a shock month cuts revenue by revenueDropPct while costs stay at the unshocked level.
 * Loan debits follow the plan schedule: quarter n is debited in month 3n (moratorium quarters pay interest).
 */
export function simulateBankAlerts(
  financial: FinancialResult,
  activityId: string,
  startMonth: string,
  months: number,
  seed: number,
  shock?: { month: string; revenueDropPct: number },
  seasonalIndex?: number[] | null,
): string[] {
  const act = (catalog.activities as { id: string; operating_margin: number; seasonal_profile: number[] }[]).find((a) => a.id === activityId);
  if (!act) throw new Error(`Unknown activity ${activityId}`);
  const index = seasonalIndex?.length === 12 ? seasonalIndex : act.seasonal_profile;
  const { plan } = financial;
  const annual = financial.preview.annualRevenue;
  const rnd = prng(seed);
  const [y0, m0] = startMonth.split("-").map(Number);
  const acct = `XX${1000 + Math.floor(rnd() * 9000)}`;
  const out: string[] = [];
  for (let k = 0; k < months; k++) {
    const t = y0 * 12 + (m0 - 1) + k;
    const y = Math.floor(t / 12);
    const m = t % 12;
    const dim = daysIn(y, m);
    const label = `${y}-${p2(m + 1)}`;
    const planned = (annual * dim) / 365 * index[m] * (0.94 + 0.12 * rnd());
    const drop = shock && shock.month === label ? shock.revenueDropPct / 100 : 0;
    const revenue = planned * (1 - drop);
    if (revenue >= 1) {
      const n = Math.min(40, Math.max(4, Math.round(revenue / 450)));
      split(revenue, n, rnd).forEach((amt, i) => {
        const d = Math.min(dim, 1 + Math.floor(((i + rnd()) * dim) / n));
        const date = fmtDate(y, m, d, i + k);
        if (i % 6 === 5) {
          out.push(`Rs ${inr(amt)} deposited in A/c ${acct} by cash at CDM on ${date}. Avl Bal Rs ${inr(5000 + rnd() * 20000)} -Bank`);
        } else {
          const vpa = `${PAYERS[Math.floor(rnd() * PAYERS.length)]}@${HANDLES[Math.floor(rnd() * HANDLES.length)]}`;
          out.push(`Dear Customer, Rs.${inr(amt)} credited to A/c ${acct} on ${date} by UPI from ${vpa}. UPI Ref ${600000000000 + Math.floor(rnd() * 1e11)}`);
        }
      });
    }
    const expenses = planned * (1 - act.operating_margin);
    if (expenses >= 1) {
      const power = Math.round(Math.min(expenses * 0.08, 900));
      const supplies = split(expenses - power, 2 + Math.floor(rnd() * 3), rnd);
      supplies.forEach((amt, i) => {
        const d = Math.min(dim, 3 + Math.floor((i * dim) / supplies.length));
        const who = SUPPLIERS[(i + k) % SUPPLIERS.length];
        out.push(i % 2 === 0
          ? `A/c ${acct} debited by Rs ${inr(amt)} on ${fmtDate(y, m, d, i + 1)} towards UPI payment to ${who}@ybl. Not you? Call 1800111109`
          : `INR ${inr(amt)} debited from A/c ${acct} on ${fmtDate(y, m, d, 3)} via NEFT to ${who.toUpperCase()} TRADERS. Avl Bal INR ${inr(3000 + rnd() * 9000)}`);
      });
      if (power > 0) out.push(`Rs ${inr(power)} paid from A/c ${acct} on ${fmtDate(y, m, Math.min(dim, 12), 0)} for electricity bill (BBPS). Thank you.`);
    }
    if (plan.eligible && k % 3 === 2) {
      const due = plan.schedule[(k + 1) / 3 - 1];
      if (due) {
        out.push(`Loan EMI of Rs ${inr(due.payment)} debited from A/c ${acct} on ${fmtDate(y, m, Math.min(dim, 28), 0)} via NACH for loan A/c XX${7000 + (seed % 1000)}.`);
      }
    }
  }
  return out;
}
