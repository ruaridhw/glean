import { readFileSync } from "node:fs";
import { join } from "node:path";
import { AUTH_REDIRECT_URI } from "@/auth/google";

describe("auth redirect URI", () => {
  it("matches the native callback configured in Cognito", () => {
    const template = readFileSync(join(__dirname, "../../../backend/template.yaml"), "utf8");

    expect(AUTH_REDIRECT_URI).toBe("glean://auth/callback");
    expect(template).toContain(`- ${AUTH_REDIRECT_URI}`);
  });
});
