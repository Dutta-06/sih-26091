import { describe, expect, it } from "vitest";
import { pickLanguageTag } from "../lib/speechLang";
import { layerDim, layerShadow, layerX, releaseVelocity, sheetDismisses, swipeCompletes } from "./motion";

describe("swipe-back decision", () => {
  it("completes past 40% of the width", () => {
    expect(swipeCompletes(170, 0, 400)).toBe(true);
    expect(swipeCompletes(150, 0, 400)).toBe(false);
  });
  it("completes on a quick flick even when short", () => {
    expect(swipeCompletes(40, 900, 400)).toBe(true);
  });
  it("cancels when flicked back", () => {
    expect(swipeCompletes(300, -400, 400)).toBe(false);
  });
  it("never completes with zero width", () => {
    expect(swipeCompletes(10, 2000, 0)).toBe(false);
  });
});

describe("sheet dismissal", () => {
  it("dismisses on distance or downward flick, not on upward flick", () => {
    expect(sheetDismisses(200, 0, 500)).toBe(true);
    expect(sheetDismisses(30, 800, 500)).toBe(true);
    expect(sheetDismisses(200, -500, 500)).toBe(false);
    expect(sheetDismisses(40, 100, 500)).toBe(false);
  });
});

describe("layer geometry", () => {
  it("maps position to translate, dim and shadow", () => {
    expect(layerX(0)).toBe("0%");
    expect(layerX(1)).toBe("100%");
    expect(layerX(-1)).toBe("-28%");
    expect(layerDim(0)).toBe(0);
    expect(layerDim(-1)).toBeCloseTo(0.16);
    expect(layerShadow(0)).toBe(0);
    expect(layerShadow(0.5)).toBeCloseTo(0.5);
  });
  it("computes release velocity from recent samples", () => {
    const v = releaseVelocity([
      { x: 0, t: 0 },
      { x: 10, t: 50 },
      { x: 30, t: 100 },
    ]);
    expect(v).toBeCloseTo(300);
    expect(releaseVelocity([{ x: 1, t: 1 }])).toBe(0);
  });
});

describe("voice language tags", () => {
  it("prefers the Indian locale, then any regional variant", () => {
    expect(pickLanguageTag("hi", ["en-US", "hi-IN"])).toBe("hi-IN");
    expect(pickLanguageTag("en", ["en-US", "en_IN"])).toBe("en-IN");
    expect(pickLanguageTag("en", ["en-GB"])).toBe("en-GB");
    expect(pickLanguageTag("ta", ["en-US", "hi-IN"])).toBeNull();
  });
});
