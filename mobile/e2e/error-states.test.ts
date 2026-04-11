import { by, device, element, expect, waitFor } from "detox";

describe("Error States: offline banner and API error handling", () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true });
  });

  it("shows offline banner when airplane mode is enabled", async () => {
    await device.disableSynchronization();
    await device.executeShellCommand("cmd connectivity airplane-mode enable");

    await waitFor(element(by.id("offlineBanner")))
      .toBeVisible()
      .withTimeout(10000);

    await expect(element(by.text("You're offline. Some features need internet."))).toBeVisible();

    await device.executeShellCommand("cmd connectivity airplane-mode disable");

    await waitFor(element(by.id("offlineBanner")))
      .not.toBeVisible()
      .withTimeout(10000);

    await device.enableSynchronization();
  });

  it("shows error state on search when API is unreachable", async () => {
    await element(by.id("tabs.meals")).tap();
    // Navigate to search - tap Discover tab then search button
    await element(by.text("Discover")).tap();
    await element(by.text("Search recipes →")).tap();

    // Disconnect and attempt search
    await device.disableSynchronization();
    await device.executeShellCommand("cmd connectivity airplane-mode enable");

    // Type in the search box and submit
    const searchInput = element(by.type("android.widget.EditText")).atIndex(0);
    await searchInput.typeText("chicken\n");

    await waitFor(element(by.id("search.error")))
      .toBeVisible()
      .withTimeout(10000);

    await expect(element(by.text("Try again"))).toBeVisible();

    // Restore connectivity
    await device.executeShellCommand("cmd connectivity airplane-mode disable");
    await device.enableSynchronization();
  });
});
