Type: research
Status: resolved

## Question

The current app declares `android.permission.CAMERA` and `android.permission.RECORD_AUDIO`, uses `expo-camera` for receipt scanning (pantry "scan" flow), and appears to use audio recording in the pantry/shop "describe" screens — confirm what that audio feature actually does by reading `mobile/app/(tabs)/pantry/describe.tsx` and `mobile/app/(tabs)/shop/describe.tsx` before researching (don't assume it's voice-to-text without checking).

Research Flutter equivalents as of 2026: camera packages (`camera` vs `image_picker`) for a receipt-scanning use case, and audio-recording packages (`record`, `flutter_sound`, or others) for whatever the describe-screen feature turns out to be. Cover cross-platform permission handling (iOS/Android) and any maintenance-status concerns. Write findings to `.scratch/flutter-port/research/camera-audio.md`, citing official docs and package repos.

## Answer

The "describe" screens (`pantry/describe.tsx`, `shop/describe.tsx`) are **not** an audio feature today — they're plain multiline text-input screens that POST typed free text to an NLP-parsing endpoint and route to a review screen with structured items. There is no audio/microphone code anywhere in the current codebase (confirmed via repo-wide grep for `expo-av`, `Audio.`, `microphone`, `speech`, `transcri*`, `RECORD_AUDIO`, plus `package.json`). The shop screen's own subtitle confirms intent: *"Type what you need now. Dictation can feed the same text later."* So `RECORD_AUDIO` in `app.json` is a forward-declared/vestigial permission for a not-yet-built voice-dictation feature, not something currently exercised.

Package recommendations:
- **Camera (receipt scan)**: `camera`, not `image_picker` — `scan.tsx` needs a live in-app preview with a custom framing overlay and programmatic still capture, which `image_picker` (OS camera app launcher only) can't do.
- **Future voice-dictation feature**: `speech_to_text` (on-device, text-out) fits the stated "dictation feeds the text box" intent better than a raw recorder. If the design instead becomes "upload a voice memo for server-side transcription," `record` is the better-maintained raw-audio-capture option. `flutter_sound` is not recommended: the maintainer has posted a public staffing warning, release cadence has slowed (~7-8 months since last push vs. ~1 month for `record`/`camera`), and its successor has a pending GPL-v3 relicense.
- **Permissions**: `permission_handler` for both camera and microphone, paired with `Info.plist` strings (`NSCameraUsageDescription`, `NSMicrophoneUsageDescription`, and `NSSpeechRecognitionUsageDescription` if `speech_to_text` is adopted) and the existing Android `CAMERA`/`RECORD_AUDIO` manifest entries.

Full findings + citations (pub.dev pages, GitHub repo metadata): `.scratch/flutter-port/research/camera-audio.md` on branch `worktree-agent-aad5cf94ca4603b74` (worktree `/home/ruaridh/glean/.claude/worktrees/agent-aad5cf94ca4603b74`, commit `0591ddf`) — not yet merged into `flutter-port`.
