var proc = java.lang.Runtime.getRuntime().exec([
  "adb",
  "shell",
  "cmd",
  "connectivity",
  "airplane-mode",
  "disable",
]);
proc.waitFor();
