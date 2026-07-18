#!/usr/bin/env node
// Guardrail: forbid raw react-native `Text` / `TextInput` value imports under app/ and src/.
// In React Native the font weight is chosen by the family NAME, so a bare <Text> styled with
// only fontWeight/fontSize silently renders the system font. Routing all text through
// AppText / AppTextInput (which always apply a Plus Jakarta Sans family) makes that impossible.
// Runs in `npm run check`.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOTS = ["app", "src"];
const ALLOW = new Set(["src/components/ui/AppText.tsx", "src/components/ui/AppTextInput.tsx"]);
const BANNED = new Set(["Text", "TextInput"]);
const RN_IMPORT = /import\s+(?:type\s+)?\{([\s\S]*?)\}\s+from\s+["']react-native["']/g;

const violations = [];
for (const root of ROOTS) {
  let entries;
  try {
    entries = readdirSync(root, { recursive: true, withFileTypes: true });
  } catch {
    continue;
  }
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (!entry.name.endsWith(".ts") && !entry.name.endsWith(".tsx")) continue;
    if (entry.name.includes(".test.")) continue;
    const rel = join(entry.parentPath, entry.name).replaceAll("\\", "/");
    if (rel.includes("/__tests__/") || ALLOW.has(rel)) continue;

    const source = readFileSync(rel, "utf8");
    for (const match of source.matchAll(RN_IMPORT)) {
      for (const raw of match[1].split(",")) {
        const name = raw.trim();
        if (!name || name.startsWith("type ")) continue; // type-only imports are fine
        const base = name.split(/\s+as\s+/)[0].trim();
        if (BANNED.has(base)) violations.push(`${rel}: imports \`${base}\` from "react-native"`);
      }
    }
  }
}

if (violations.length > 0) {
  console.error(
    "✗ Raw react-native Text/TextInput imports are banned — use AppText/AppTextInput from @/components/ui:",
  );
  for (const v of violations) console.error(`  ${v}`);
  console.error(`\n${violations.length} violation(s). Why: see src/components/ui/AppText.tsx.`);
  process.exit(1);
}
console.log("✓ guard-text-imports: no raw Text/TextInput imports (AppText/AppTextInput enforced).");
