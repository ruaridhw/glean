import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("mobile CI auth bypass", () => {
  it("builds the E2E APK with explicit auth bypass instead of live Cognito tokens", () => {
    const workflow = readFileSync(
      resolve(__dirname, "../../../.github/workflows/mobile-ci.yml"),
      "utf8",
    );

    expect(workflow).not.toContain("Get CI auth tokens");
    expect(workflow).not.toContain("aws cognito-idp initiate-auth");
    expect(workflow).toContain("EXPO_PUBLIC_APP_VARIANT: e2e");
    expect(workflow).toContain('EXPO_PUBLIC_AUTH_BYPASS: "true"');
    expect(workflow).toContain("EXPO_PUBLIC_AUTH_BYPASS_USER_SUB: ci-e2e-user-sub");
  });
});
