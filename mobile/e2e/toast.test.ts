import { by, device, element, expect, waitFor } from "detox";

describe("Toast: shows success message after pantry item added", () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true });
  });

  it("shows toast after adding a pantry item via manual entry", async () => {
    await element(by.id("tabs.pantry")).tap();
    await element(by.id("pantry.fab")).tap();

    await expect(element(by.text("Manual Entry"))).toBeVisible();
    await element(by.text("Manual Entry")).tap();

    await waitFor(element(by.id("manualEntry.nameInput")))
      .toBeVisible()
      .withTimeout(5000);
    await element(by.id("manualEntry.nameInput")).typeText("toast test item");
    await element(by.id("manualEntry.quantityInput")).typeText("100");
    await element(by.id("manualEntry.saveButton")).tap();

    await waitFor(element(by.text("Added to pantry")))
      .toBeVisible()
      .withTimeout(5000);
  });
});
