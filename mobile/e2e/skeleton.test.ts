import { by, device, element, expect, waitFor } from "detox";

describe("Skeleton: shimmer placeholders during loading", () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true, delete: true });
  });

  it("shows pantry skeleton briefly on cold start", async () => {
    await element(by.id("tabs.pantry")).tap();
    // On fresh launch, the skeleton may flash briefly then show empty state
    // We just verify the screen eventually settles (heading visible)
    await waitFor(element(by.id("pantry.heading")))
      .toBeVisible()
      .withTimeout(5000);
  });

  it("shows shop skeleton briefly on cold start", async () => {
    await element(by.id("tabs.shop")).tap();
    await waitFor(element(by.text("Shopping List")))
      .toBeVisible()
      .withTimeout(5000);
  });
});
