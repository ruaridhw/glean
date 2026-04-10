import { by, device, element, expect } from "detox";

describe("Screens: all main screens render key elements", () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true });
  });

  it("pantry screen shows heading and FAB", async () => {
    await element(by.id("tabs.pantry")).tap();
    await expect(element(by.id("pantry.heading"))).toBeVisible();
    await expect(element(by.id("pantry.fab"))).toBeVisible();
  });

  it("meals screen shows heading and tab toggles", async () => {
    await element(by.id("tabs.meals")).tap();
    await expect(element(by.text("Meals"))).toBeVisible();
    await expect(element(by.text("My Recipes"))).toBeVisible();
    await expect(element(by.text("Discover"))).toBeVisible();
  });

  it("plan screen shows heading and generate button", async () => {
    await element(by.id("tabs.plan")).tap();
    await expect(element(by.text("This Week"))).toBeVisible();
    await expect(element(by.text("Generate week"))).toBeVisible();
  });

  it("shop screen shows heading", async () => {
    await element(by.id("tabs.shop")).tap();
    await expect(element(by.text("Shopping List"))).toBeVisible();
  });

  it("settings screen shows heading", async () => {
    await element(by.id("tabs.settings")).tap();
    await expect(element(by.text("Settings"))).toBeVisible();
  });
});
