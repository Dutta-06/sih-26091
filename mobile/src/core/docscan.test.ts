import { describe, expect, it } from "vitest";
import { classify, findIfsc, findPan, nameSimilarity, readDocument } from "./docscan";
import { verhoeffDigit } from "./documents";

const aadhaarNo = (base: string) => base + verhoeffDigit(base);
const valid = aadhaarNo("23456789012");
const spaced = `${valid.slice(0, 4)} ${valid.slice(4, 8)} ${valid.slice(8)}`;

const AADHAAR = [
  "भारत सरकार",
  "GOVERNMENT OF INDIA",
  "सुनीता देवी",
  "Sunita Devi",
  "जन्म तिथि/DOB: 12/08/1989",
  "महिला/ FEMALE",
  spaced,
  "मेरा आधार, मेरी पहचान",
];

const PAN = [
  "आयकर विभाग INCOME TAX DEPARTMENT",
  "GOVT. OF INDIA",
  "SUNITA DEVI",
  "RAMESH PRASAD",
  "12/08/1989",
  "Permanent Account Number",
  "ABCPD1234F",
];

const PASSBOOK = [
  "BANK OF BARODA",
  "Branch: GOPIGANJ",
  "IFSC Code : BARBOGOPIGA",
  "Name: SUNITA DEVI",
  "A/c No. 3456 7890 1234",
  "Address: Ward 4, Gopiganj, Bhadohi",
  "PIN 221303",
  "SAVINGS BANK PASSBOOK",
];

describe("document reading", () => {
  it("reads an Aadhaar card, keeps only the masked number and checks it", () => {
    const r = readDocument(AADHAAR, "identity_proof", "Sunita Devi");
    expect(r.kind).toBe("aadhaar");
    expect(r.matchesRequest).toBe(true);
    expect(r.fields.name).toBe("Sunita Devi");
    expect(r.fields.dob).toBe("12/08/1989");
    expect(r.fields.gender).toBe("female");
    expect(r.fields.aadhaarMasked).toBe(`XXXX-XXXX-${valid.slice(8)}`);
    expect(r.fields.aadhaarChecksumOk).toBe(true);
    expect(JSON.stringify(r)).not.toContain(valid.slice(0, 8));
    expect(r.issues).toEqual([]);
  });

  it("flags an Aadhaar number that fails the checksum (misread digit)", () => {
    const bad = spaced.slice(0, -1) + ((+spaced.slice(-1) + 1) % 10);
    const r = readDocument(AADHAAR.map((l) => (l === spaced ? bad : l)), "identity_proof");
    expect(r.fields.aadhaarChecksumOk).toBe(false);
    expect(r.issues.map((i) => i.key)).toContain("c3.scan.issue.aadhaarChecksum");
  });

  it("reads a PAN card and repairs O/0 mix-ups by position", () => {
    expect(findPan("ABCPD I234F")).toBeUndefined();
    expect(findPan("ABCPDI234F")).toBe("ABCPD1234F");
    expect(findPan("A8CPD1234F")).toBe("ABCPD1234F");
    const r = readDocument(PAN, "identity_proof", "Sunita Devi");
    expect(r.kind).toBe("pan");
    expect(r.fields.pan).toBe("ABCPD1234F");
    expect(r.fields.name).toBe("Sunita Devi");
  });

  it("reads a passbook: IFSC, masked account, name and PIN", () => {
    expect(findIfsc("IFSC: SBIN0OO1234")).toBe("SBIN0OO1234");
    const r = readDocument(PASSBOOK, "bank_passbook", "Sunita Devi");
    expect(r.kind).toBe("bank_passbook");
    expect(r.fields.ifsc).toBe("BARB0GOPIGA");
    expect(r.fields.accountMasked).toBe("XXXXXXXX1234");
    expect(r.fields.name).toBe("Sunita Devi");
    expect(r.fields.pincode).toBe("221303");
    expect(r.issues).toEqual([]);
  });

  it("says when the wrong document is scanned or the name differs", () => {
    const wrong = readDocument(PAN, "bank_passbook");
    expect(wrong.matchesRequest).toBe(false);
    expect(wrong.issues[0]).toEqual({ key: "c3.scan.issue.wrongDoc", vars: { found: "pan" } });
    const other = readDocument(PASSBOOK, "bank_passbook", "Kavita Kumari");
    expect(other.issues.map((i) => i.key)).toContain("c3.scan.issue.nameMismatch");
  });

  it("handles blurry or empty scans", () => {
    expect(readDocument([], "identity_proof").issues[0].key).toBe("c3.scan.issue.unreadable");
    expect(readDocument(["~~ ::"], "project_quotation").issues[0].key).toBe("c3.scan.issue.unreadable");
    expect(classify("random words on a page").kind).toBe("other");
  });

  it("matches names despite small recognition errors and initials", () => {
    expect(nameSimilarity("Sunita Devi", "SUNLTA DEVI")).toBe(1);
    expect(nameSimilarity("Sunita Devi", "S. Devi")).toBe(1);
    expect(nameSimilarity("Sunita Devi", "Kavita Kumari")).toBeLessThan(0.5);
  });

  it("reads an Udyam certificate number", () => {
    const r = readDocument(["UDYAM REGISTRATION CERTIFICATE", "UDYAM REGISTRATION NUMBER UDYAM-UP-72-0012345", "NAME OF ENTERPRISE SUNITA TAILORS", "TYPE OF ENTERPRISE MICRO"], "udyam_certificate");
    expect(r.kind).toBe("udyam");
    expect(r.fields.udyam).toBe("UDYAM-UP-72-0012345");
    expect(r.matchesRequest).toBe(true);
  });
});
