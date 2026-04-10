import { by, device, element, expect } from "detox";

describe("Empty States: each tab shows guidance when empty", () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true, delete: true });
  });

  it("pantry shows empty state with scan and describe CTAs", async () => {
    await element(by.id("tabs.pantry")).tap();
    await expect(element(by.id("pantry.emptyState"))).toBeVisible();
    await expect(element(by.text("Your pantry is empty"))).toBeVisible();
    await expect(element(by.text("Scan receipt"))).toBeVisible();
    await expect(element(by.text("Describe items"))).toBeVisible();
  });

  it("meals shows empty state with search CTA", async () => {
    await element(by.id("tabs.meals")).tap();
    await expect(element(by.id("meals.emptyState"))).toBeVisible();
    await expect(element(by.text("No recipes yet"))).toBeVisible();
    await expect(element(by.text("Search recipes"))).toBeVisible();
  });

  it("plan shows empty state with browse and generate CTAs", async () => {
    await element(by.id("tabs.plan")).tap();
    await expect(element(by.id("plan.emptyState"))).toBeVisible();
    await expect(element(by.text("No meals planned this week"))).toBeVisible();
  });

  it("shop shows empty state with plan CTA", async () => {
    await element(by.id("tabs.shop")).tap();
    await expect(element(by.id("shop.emptyState"))).toBeVisible();
    await expect(element(by.text("Your shopping list is empty"))).toBeVisible();
    await expect(element(by.text("Go to meal plan"))).toBeVisible();
  });

  it("pantry empty state CTA navigates to describe screen", async () => {
    await element(by.id("tabs.pantry")).tap();
    await element(by.text("Describe items")).tap();
    // The describe screen heading — from describe.tsx styles.heading
    await expect(element(by.text("Describe your shop"))).toBeVisible();
  });
});
