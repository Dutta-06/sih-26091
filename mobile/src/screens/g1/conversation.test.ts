import { describe, expect, it } from "vitest";
import { EMPTY_PROFILE, SAMPLE_PROFILE, type ChatMessage } from "../../state/store";
import { advance, missingSlots, opening, profileComplete, respond, sampleText, type ConvInput, type ConvResult, type PendingSlot } from "./conversation";

function apply(input: ConvInput, text: string, r: ConvResult): ConvInput {
  const user: ChatMessage = { id: String(input.chat.length), from: "user", text, literal: true, vars: r.userVars };
  return { ...input, profile: { ...input.profile, ...r.profilePatch }, pendingSlot: r.pendingSlot, chat: [...input.chat, user, ...r.messages], chatLang: r.chatLang ?? input.chatLang };
}

const start = (): ConvInput => {
  const o = opening({ profile: EMPTY_PROFILE, pendingSlot: null, chat: [], chatLang: "en" });
  return { profile: EMPTY_PROFILE, pendingSlot: o.pendingSlot, chat: o.messages, chatLang: "en" };
};

describe("profiling conversation", () => {
  it("opens with the optional name question and records a name", () => {
    let s = start();
    expect(s.pendingSlot).toBe("name");
    const r = respond("My name is Rekha", s);
    expect(r.userVars.name).toBe("Rekha");
    s = apply(s, "My name is Rekha", r);
    expect(s.pendingSlot).toBe("location");
  });

  it("accepts several slots at once, out of order", () => {
    let s: ConvInput = { ...start(), pendingSlot: "location" };
    const text = "I have 1 lakh and want dairy in Jaunpur";
    const r = respond(text, s);
    s = apply(s, text, r);
    expect(s.profile.capital).toBe(100_000);
    expect(s.profile.activityId).toBe("dairy_farming");
    expect(s.profile.locationText).toBe("Jaunpur");
    expect(s.pendingSlot).toBe("reason");
    expect(r.messages.some((m) => m.text === "u1.cap.ok")).toBe(true);
  });

  it("asks the user to choose between repeated village names", () => {
    const s = { ...start(), pendingSlot: "location" };
    const r = respond("Gopiganj", s);
    expect(r.pendingSlot).toBe("location_choice");
    expect(r.messages.some((m) => m.card === "loc_choice")).toBe(true);
    const picked = advance(apply(s, "Gopiganj", r), { locationCode: "186233" }, ["location"]);
    expect(picked.messages[0].text).toBe("u1.loc.village");
    expect(picked.pendingSlot).toBe("capital");
  });

  it("is honest about unknown places and savings above the scheme", () => {
    const s = { ...start(), pendingSlot: "location" };
    expect(respond("Atlantis", s).messages[0].text).toBe("u1.loc.notFound");
    const cap = respond("I have 60 lakh", { ...s, pendingSlot: "capital" });
    expect(cap.messages[0].text).toBe("u1.cap.above");
  });

  it("explains an unaffordable idea with ranked suggestions", () => {
    const s = { ...start(), profile: { ...EMPTY_PROFILE, capital: 4_000 }, pendingSlot: "activity" };
    const r = respond("I want a flour mill", s);
    expect(r.messages.map((m) => m.text)).toContain("u1.act.tooBig");
  });

  it("routes intents with a jump card and re-asks the pending slot", () => {
    const s = { ...start(), pendingSlot: "capital" };
    const r = respond("I want to file a complaint", s);
    expect(r.messages.find((m) => m.card === "jump")?.vars?.intent).toBe("grievance");
    expect(r.messages.at(-1)?.text).toBe("u1.ask.capital");
  });

  it("the presenter sample goes through the same pipeline to a complete profile", () => {
    let s = start();
    s = apply(s, "skip", { userVars: { answered: "name" }, messages: [], profilePatch: {}, pendingSlot: "location", events: [], changedCore: false });
    for (let i = 0; i < 12 && s.pendingSlot; i++) {
      const text = sampleText(SAMPLE_PROFILE, s.pendingSlot as PendingSlot);
      if (!text) break;
      s = apply(s, text, respond(text, s));
    }
    expect(missingSlots(s.profile, new Set())).toEqual([]);
    expect(profileComplete(s.profile, s.chat)).toBe(true);
    expect(s.profile).toMatchObject({ capital: SAMPLE_PROFILE.capital, activityId: SAMPLE_PROFILE.activityId, locationCode: SAMPLE_PROFILE.locationCode, skills: SAMPLE_PROFILE.skills, premises: "home", category: "obc", shgMember: false });
    expect(s.chat.at(-1)?.card).toBe("profile_summary");
  });
});
