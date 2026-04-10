import { by, device, element, expect, waitFor } from "detox";

describe("Animations: list changes and check-off don't break interactions", () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true });
  });

  it("adds pantry item with smooth animation", async () => {
    await element(by.id("tabs.pantry")).tap();
    await element(by.id("pantry.fab")).tap();
    await element(by.text("Manual Entry")).tap();

    await element(by.id("manualEntry.nameInput")).typeText("animated item");
    await element(by.id("manualEntry.quantityInput")).typeText("250");
    await element(by.id("manualEntry.saveButton")).tap();

    await waitFor(element(by.text("animated item")))
      .toBeVisible()
      .withTimeout(5000);
  });

  it("toggles shopping list item without animation blocking interaction", async () => {
    await element(by.id("tabs.shop")).tap();

    // Add a manual item via the add input
    const addInput = element(by.type("android.widget.EditText"));
    await addInput.typeText("animation test\n");

    await waitFor(element(by.text("animation test")))
      .toBeVisible()
      .withTimeout(3000);

    // Tap checkbox to toggle check-off
    await element(by.text("☐")).atIndex(0).tap();

    // Item should still be visible (now checked)
    await waitFor(element(by.text("animation test")))
      .toBeVisible()
      .withTimeout(3000);
  });
});
