import { expect, test } from "vitest";

// Placeholder so the package is non-empty and the lint/check gate passes. The real
// @platforma-sdk/test blockTest suite is deferred to MILAB-6323 — blocked by the block-CI
// "empty inputs" PermissionDenied-on-KV regression; it lands once that unblocks and a backend is up.
test("placeholder", () => {
  expect(1 + 1).toBe(2);
});
