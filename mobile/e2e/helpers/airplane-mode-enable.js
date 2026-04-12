var proc = java.lang.Runtime.getRuntime().exec(
  ["adb", "shell", "cmd", "connectivity", "airplane-mode", "enable"]
);
proc.waitFor();
