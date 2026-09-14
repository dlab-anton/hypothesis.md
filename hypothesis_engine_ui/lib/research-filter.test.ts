import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { hypothesisListParams, pageRange } from "./research-filter.ts";

describe("research list filters", () => {
  it("builds a bounded, trimmed server query", () => {
    assert.deepEqual(hypothesisListParams({
      channel: "geometry",
      search: "  circle packing  ",
      status: "testing",
      offset: 40,
      limit: 40,
    }), {
      channel: "geometry",
      search: "circle packing",
      status: "testing",
      is_archived: false,
      sort_by: "updated_at",
      sort_order: "desc",
      offset: 40,
      limit: 40,
    });
  });

  it("treats archived as storage state and reports honest page ranges", () => {
    assert.deepEqual(hypothesisListParams({
      channel: "",
      search: "",
      status: "archived",
      offset: 0,
      limit: 40,
    }), {
      is_archived: true,
      sort_by: "updated_at",
      sort_order: "desc",
      offset: 0,
      limit: 40,
    });
    assert.deepEqual(pageRange(40, 17, 57), { first: 41, last: 57 });
    assert.deepEqual(pageRange(0, 0, 0), { first: 0, last: 0 });
  });
});
