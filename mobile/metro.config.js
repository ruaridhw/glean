const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// .sql files are inlined as strings by babel-plugin-inline-import (see babel.config.js)
config.resolver.sourceExts.push("sql");

module.exports = config;
