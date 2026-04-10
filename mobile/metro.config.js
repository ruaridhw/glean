const path = require("node:path");
const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// .sql files are inlined as strings by babel-plugin-inline-import (see babel.config.js)
config.resolver.sourceExts.push("sql");

// amazon-cognito-identity-js imports @react-native-async-storage/async-storage,
// but installing it causes peer dep conflicts with react-dom/react versions in
// the current SDK 54 dependency tree. Shim it with an in-memory store — auth is
// bypassed in dev mode anyway (see src/auth/storage.ts).
config.resolver.extraNodeModules = {
  "@react-native-async-storage/async-storage": path.resolve(
    __dirname,
    "src/auth/async-storage-shim.ts",
  ),
};

module.exports = config;
