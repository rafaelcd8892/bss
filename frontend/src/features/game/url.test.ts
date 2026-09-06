import { beforeEach, describe, expect, it } from "vitest";
import { DEFAULT_PARAMS, paramsToQuery, readParams, shareUrl, syncUrl } from "./url";

function visit(search: string) {
  window.history.replaceState(null, "", `/game${search}`);
}

beforeEach(() => visit(""));

describe("readParams", () => {
  it("falls back to defaults with no query", () => {
    expect(readParams()).toEqual({ params: DEFAULT_PARAMS, fromUrl: false });
  });

  it("reads a full replay link", () => {
    visit("?home=147&away=121&seed=1234");
    const { params, fromUrl } = readParams();
    expect(fromUrl).toBe(true);
    expect(params).toMatchObject({ homeTeamId: 147, awayTeamId: 121, seed: 1234 });
  });

  it("only treats a link as a replay when the whole matchup is present", () => {
    visit("?home=147&away=121");
    expect(readParams().fromUrl).toBe(false);
  });

  it("accepts a zero seed but rejects nonsense", () => {
    visit("?home=147&away=121&seed=0");
    expect(readParams().params.seed).toBe(0);
    visit("?home=abc&away=-5&seed=x");
    expect(readParams().params).toEqual(DEFAULT_PARAMS);
  });
});

describe("paramsToQuery", () => {
  it("omits innings when it is the default, keeping shared links short", () => {
    expect(paramsToQuery(DEFAULT_PARAMS)).toBe("home=147&away=121&seed=1234");
  });

  it("includes innings when it differs", () => {
    expect(paramsToQuery({ ...DEFAULT_PARAMS, innings: 12 })).toContain("innings=12");
  });
});

describe("round trip", () => {
  it("survives sync and read, so a shared link reproduces the matchup", () => {
    const params = { homeTeamId: 119, awayTeamId: 111, seed: 77, innings: 9 };
    syncUrl(params);
    expect(readParams()).toEqual({ params, fromUrl: true });
  });

  it("builds an absolute share URL", () => {
    expect(shareUrl(DEFAULT_PARAMS)).toBe(
      `${window.location.origin}/game?home=147&away=121&seed=1234`,
    );
  });
});
