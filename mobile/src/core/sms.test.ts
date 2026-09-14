import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/c3.json";
import { inr, parseNotifications, parseOne } from "./sms";

const NOW = new Date("2026-09-14T10:00:00Z");

describe("sms parser parity with data_connectors/sms_parser.py", () => {
  it(`has at least 20 exported messages`, () => expect(fixture.sms.length).toBeGreaterThanOrEqual(20));

  it.each(fixture.sms.map((s, i) => ({ i, ...s })))("message $i", ({ message, result }) => {
    const got = parseOne(message, NOW);
    if (result === null) {
      expect(got).toBeNull();
      return;
    }
    expect(got).not.toBeNull();
    expect(got!.direction).toBe(result.direction);
    expect(got!.amount).toBe(result.amount);
    expect(got!.channel).toBe(result.channel);
    expect(got!.isLoanRepayment).toBe(result.isLoanRepayment);
    expect(got!.at).toBe(result.at ?? "2026-09-14T10:00:00.000+00:00");
  });

  it("drops OTP and promotional messages in a batch", () => {
    const txns = parseNotifications(fixture.sms.map((s) => s.message), NOW);
    expect(txns.length).toBe(fixture.sms.filter((s) => s.result).length);
  });

  it("formats rupees with Indian grouping", () => {
    expect(inr(108000)).toBe("1,08,000.00");
    expect(inr(10801)).toBe("10,801.00");
    expect(inr(640.5)).toBe("640.50");
    expect(inr(12345678.9)).toBe("1,23,45,678.90");
  });
});
