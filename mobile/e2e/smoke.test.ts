import { by, device, element, expect, waitFor } from "detox";

describe("Smoke: launch, tab navigation, and CRUD", () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true });
  });

  it("shows exactly 5 tab buttons", async () => {
    await expect(element(by.id("tabs.pantry"))).toBeVisible();
    await expect(element(by.id("tabs.meals"))).toBeVisible();
    await expect(element(by.id("tabs.plan"))).toBeVisible();
    await expect(element(by.id("tabs.shop"))).toBeVisible();
    await expect(element(by.id("tabs.settings"))).toBeVisible();
  });

  it("navigates to each tab", async () => {
    await element(by.id("tabs.meals")).tap();
    await expect(element(by.text("Meals"))).toBeVisible();

    await element(by.id("tabs.plan")).tap();
    await expect(element(by.text("This Week"))).toBeVisible();

    await element(by.id("tabs.shop")).tap();
    await expect(element(by.text("Shopping List"))).toBeVisible();

    await element(by.id("tabs.settings")).tap();
    await expect(element(by.text("Settings"))).toBeVisible();

    await element(by.id("tabs.pantry")).tap();
    await expect(element(by.id("pantry.heading"))).toBeVisible();
  });

  it("adds an item via manual entry and verifies it in pantry", async () => {
    await element(by.id("tabs.pantry")).tap();
    await element(by.id("pantry.fab")).tap();

    await expect(element(by.text("Manual Entry"))).toBeVisible();
    await element(by.text("Manual Entry")).tap();

    await waitFor(element(by.id("manualEntry.nameInput")))
      .toBeVisible()
      .withTimeout(5000);
    await element(by.id("manualEntry.nameInput")).typeText("test chicken");
    await element(by.id("manualEntry.quantityInput")).typeText("500");
    await element(by.id("manualEntry.saveButton")).tap();

    await waitFor(element(by.id("pantry.heading")))
      .toBeVisible()
      .withTimeout(5000);
    await expect(element(by.text("test chicken"))).toBeVisible();
  });
});
