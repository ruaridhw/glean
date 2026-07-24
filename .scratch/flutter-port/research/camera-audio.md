# Camera & audio-recording: current app behavior and Flutter equivalents

Research for the Flutter big-bang rewrite. Covers what the current Expo/React
Native app actually does with its two native permissions
(`android.permission.CAMERA`, `android.permission.RECORD_AUDIO`), and what
Flutter packages/patterns would replace that functionality.

## 1. What the current app actually does

### Camera — receipt scanning (`mobile/app/(tabs)/pantry/scan.tsx`, `scan-progress.tsx`)

`mobile/app.json` declares `android.permission.CAMERA` and configures the
`expo-camera` plugin with `"cameraPermission": "Allow Glean to scan receipts."`
(`mobile/app.json:19,24-29`).

`scan.tsx` uses `expo-camera`'s `CameraView` + `useCameraPermissions` to show a
**live, full-screen camera preview** with a framing overlay ("Line the receipt
up inside the frame"), a shutter button, and a back button. On shutter press it
calls `cameraRef.current.takePictureAsync({ base64: true, quality: 0.8 })` and
pushes the base64 JPEG to `scan-progress.tsx` via router params
(`mobile/app/(tabs)/pantry/scan.tsx:29-42`).

`scan-progress.tsx` converts the base64 string back into a `Blob`, wraps it in
`FormData`, and POSTs it through `useScanReceipt()` (`mobile/api/hooks`) to a
backend OCR/parsing endpoint, then shows an animated step tracker
("Uploading image" → "Reading receipt" → "Extracting items") before routing to
the pantry review screen with the parsed items
(`mobile/app/(tabs)/pantry/scan-progress.tsx:12-16,40-51,71-87`).

**Requirement this confirms:** the feature needs an **in-app live camera
preview with a custom framing UI and a still-capture-to-file/base64** call —
not just "let the user pick or snap a photo via the OS picker." A gallery-only
picker would lose the framing overlay and the guided "align receipt in frame"
UX.

### Audio — the "describe" screens are text input, not voice (confirmed, not assumed)

`mobile/app/(tabs)/pantry/describe.tsx` and `mobile/app/(tabs)/shop/describe.tsx`
were read in full. **Neither contains any audio/microphone code.** Both are
plain multiline `AppTextInput` forms:

- Pantry `describe.tsx`: user types free text (e.g. "I bought a kilo of mince
  and two tins of tomatoes"), submits via `useDescribeReceipt()`, and is routed
  to the pantry review screen with parsed items
  (`mobile/app/(tabs)/pantry/describe.tsx:21-36`).
- Shop `describe.tsx`: same pattern via `useParseShoppingDescription()`, routed
  to the shop review screen, and it **explicitly names the gap**: the screen's
  subtitle reads *"Type what you need now. Dictation can feed the same text
  later."* (`mobile/app/(tabs)/shop/describe.tsx:43`).

A repo-wide search for `expo-av`, `Audio.`, `microphone`, `dictation`,
`speech`, `transcri*`, and `RECORD_AUDIO` across `mobile/app`, `mobile/src`,
`mobile/components`, `mobile/api`, `mobile/intake`, and `mobile/normalization`
found **no audio-recording implementation anywhere** in the codebase, and no
`expo-av`/audio dependency in `mobile/package.json`. `git log -p` on
`mobile/app.json` shows `RECORD_AUDIO` has been present since the plugin/config
was first committed, alongside `CAMERA`, with no accompanying audio code ever
added.

**Conclusion — confirmed, not assumed:** The "describe" screens are a
**text-based natural-language item parser** (typed description → LLM/NLP
parse → structured pantry/shopping-list items). `RECORD_AUDIO` is a
**vestigial/forward-declared permission** for a **not-yet-built voice-dictation
input** to the same text field — the shop screen's own copy says as much. For
Flutter planning purposes, the real future feature is "speech-to-text
dictation into a text box," not "record and upload an audio clip." This
changes which package family is the right comparison (see §3).

## 2. Camera: `camera` vs `image_picker` for receipt scanning

| | `camera` | `image_picker` |
|---|---|---|
| Live in-app preview widget | Yes — `CameraPreview`/`CameraController`, streaming feed you can overlay custom UI on | No — launches the OS camera app/gallery picker as a separate screen and returns a file |
| Custom framing/overlay UI (needed for the receipt-frame guide) | Yes, straightforward (compose your own widgets over the preview) | Not possible — you don't control the native camera UI |
| Still capture to file/bytes | Yes (`takePicture()`) | Yes, but only after the user leaves your UI to use the OS camera |
| Maintenance | pub.dev: v0.12.0+2, publisher `flutter.dev` (verified, official Flutter team), 160 pub points, 2.59k likes, 621k downloads, last published ~11 days before this research (2026-07-25). Source repo `flutter/packages` (monorepo): 109 open issues repo-wide, last push 2026-07-24, 5,268 stars. Actively maintained by Google/Flutter. | pub.dev: v1.2.3, publisher `flutter.dev` (verified), 160 pub points, 7.7k likes, 3.7M downloads, last published ~24 days before this research. Also official-team maintained. |
| License | BSD-3-Clause | BSD-3-Clause |

**Recommendation:** `camera` is the correct package for the receipt-scan
screen — the current UX (live preview, framing overlay, custom shutter button,
in-app step-progress hand-off) requires a preview widget you can draw over and
programmatic capture, which `image_picker` structurally cannot provide since it
delegates to the OS camera app/gallery UI. `image_picker` remains useful
elsewhere in a Flutter port only for "attach a photo from the gallery"-style
flows, which this app doesn't currently have. Both are official, verified
`flutter.dev`-published packages with strong maintenance signals (recent
releases within the last month, high pub points/likes, active monorepo).

Sources:
- https://pub.dev/packages/camera
- https://pub.dev/packages/image_picker
- https://github.com/flutter/packages (camera lives in this monorepo)

## 3. Audio/dictation: package options for the future "dictation" feature

Since the describe screens are text-entry with a stated intent to add
dictation later, the relevant comparison is between **raw audio recorders**
(record a clip, then send it somewhere) and **on-device speech-to-text**
(directly transcribe speech into the text field, matching "dictation can feed
the same text" from the shop screen's own copy).

### `record` (raw audio capture to file/stream)

- pub.dev: v7.1.1, publisher `cow-level.ovh` (verified), 160 pub points, 885
  likes, 776k downloads, license BSD-3-Clause, last published ~25 days before
  this research.
- GitHub `llfbandit/record`: 316 stars, 302 forks, 623 commits, last push
  2026-07-07, 7 open issues — actively maintained, small but responsive
  single/small-maintainer project.
- Fit: good if the plan is "record audio, upload to a backend STT/LLM
  endpoint" (mirroring how `scan-progress.tsx` uploads the receipt photo for
  server-side processing) — i.e., capture-and-upload rather than on-device
  transcription.

### `flutter_sound` (record + playback, more full-featured audio toolkit)

- pub.dev: v9.30.0, publisher `tau.canardoux.xyz` (verified), 140 pub points,
  1.64k likes, 75.3k weekly downloads, license MPL-2.0 for the 9.x line, last
  published ~7 months before this research (2025-11-27 per GitHub push date).
- **Maintenance concern (from the maintainer directly, on pub.dev):** "I am
  almost alone to maintain and develop three important projects... We
  desperately need at least one other developer." The 9.x branch (MPL-2.0) is
  described by the maintainer as "legacy" and is promised maintenance "for the
  foreseeable future," but the intended successor, **Taudio / Flutter Sound
  10.0**, is Alpha and will ship under **GPL v3** — a licensing change teams
  need to plan around if they intend to upgrade later.
- GitHub `Canardoux/flutter_sound`: 941 stars, 360 open issues, last push
  2025-11-27 — open-issue count is high relative to `record`, and the gap
  since last push (~7-8 months) versus `record`'s ~1 month is a real
  maintenance-cadence difference.
- Fit: overkill for this feature (it's built for full record+playback+audio
  processing pipelines); not recommended given the maintainer's own staffing
  warning and slower cadence.

### `speech_to_text` (on-device dictation — best match for the stated feature)

- pub.dev: v7.4.0 (7.5.0-beta.1 prerelease), publisher `csdcorp.com`
  (verified), 130 pub points, 1.6k likes, 448k weekly downloads, license
  BSD-3-Clause, last published ~2 months before this research.
- GitHub `csdcorp/speech_to_text`: 472 stars, 83 open issues, last push
  2026-07-02 — recent activity, single-maintainer but active.
  Supports Android, iOS, macOS, Web, and (beta) Windows via each platform's
  native/on-device speech recognizer (plus the Web Speech API in browsers);
  no server round-trip needed. Docs explicitly scope it to "commands and short
  phrases, not continuous spoken conversion," which is a reasonable fit for
  short pantry/shopping-list dictation but worth validating against real
  utterance lengths before committing.
- Fit: this is the package family that actually matches "dictation can feed
  the same text [box]" — it produces text directly, so it drops straight into
  the existing `AppTextInput` flow with no backend changes, unlike `record`
  (which would need a new upload + server-side STT endpoint) or `flutter_sound`.

**Recommendation:** If/when dictation is built in Flutter, prefer
`speech_to_text` over `record`/`flutter_sound` — it directly reproduces the
"speech → text box" UX the current app's copy already promises, avoids adding
a new backend endpoint, and has healthier recent-activity signals than
`flutter_sound`. If the product direction instead becomes "record a voice
memo and send it to the backend for transcription" (paralleling the
receipt-photo-upload pattern), `record` is the better-maintained, more
narrowly-scoped choice over `flutter_sound`.

Sources:
- https://pub.dev/packages/record
- https://github.com/llfbandit/record
- https://pub.dev/packages/flutter_sound
- https://github.com/Canardoux/flutter_sound
- https://pub.dev/packages/speech_to_text
- https://github.com/csdcorp/speech_to_text
- https://docs.flutter.dev/cookbook/audio/record

## 4. Cross-platform permission handling

Both `camera` and `speech_to_text`/`record` need explicit platform permission
strings/declarations plus a runtime request flow:

- **iOS (`Info.plist`):** `NSCameraUsageDescription` for camera capture;
  `NSMicrophoneUsageDescription` for any audio recording or speech
  recognition (speech_to_text's docs also call for
  `NSSpeechRecognitionUsageDescription` on iOS since it uses `SFSpeechRecognizer`,
  distinct from the raw mic-access string). Missing an entry causes iOS to
  terminate the app at permission-check/request time, not just deny silently.
- **Android (`AndroidManifest.xml` / runtime):** `<uses-permission
  android:name="android.permission.CAMERA"/>` and
  `android.permission.RECORD_AUDIO"/>` declared in the manifest, plus a
  runtime request (Android 6.0+) — this is the direct Flutter-side counterpart
  of the two permissions already declared in `mobile/app.json`.
- **`permission_handler`** (pub.dev v12.0.3, publisher `baseflow.com`
  verified, 160 pub points, 6,000 likes, 2.98M weekly downloads, MIT license,
  last published ~53 days before this research; GitHub
  `Baseflow/flutter-permission-handler`: 2,169 stars, 156 open issues, last
  push 2026-06-12) is the standard cross-platform way to check/request
  `Permission.camera` and `Permission.microphone` at runtime with one API
  instead of writing separate iOS/Android permission code. It's the
  Flutter-ecosystem equivalent of what `expo-camera`'s
  `useCameraPermissions()` hook does today, generalized to also cover the
  microphone permission the audio feature will need. Widely used alongside
  both `camera` and `record`/`speech_to_text` in their own official examples.
- The `camera` package itself also exposes permission errors
  (`CameraException` with `cameraPermission`-type codes) that must be
  surfaced in the UI, similar to the current `useCameraPermissions()` +
  "Grant Permission" button pattern in `scan.tsx`.

Sources:
- https://pub.dev/packages/permission_handler
- https://pub.dev/packages/camera
- https://pub.dev/packages/speech_to_text

## 5. Summary for the porting plan

- **Camera / receipt scan:** port to the `camera` package (official
  `flutter.dev`, actively maintained), rebuilding the live-preview + framing
  overlay + shutter capture UX from `scan.tsx`, then keep the existing
  upload-and-poll pattern from `scan-progress.tsx` unchanged (still POST
  image bytes to the backend OCR endpoint). `image_picker` is not sufficient
  on its own for this screen because it has no live in-app preview.
- **"Describe" screens:** these are text-input NLP-parsing screens today, not
  audio features — port them as plain text fields calling the existing
  parse-description endpoints. `RECORD_AUDIO` is currently unused code-wise;
  carry the permission forward only if/when dictation ships.
- **Future dictation:** favor `speech_to_text` (on-device, text-out, matches
  the product copy) over `record`/`flutter_sound` unless the design changes
  to "upload a voice memo for server transcription," in which case `record`
  is the better-maintained raw-recording option; avoid `flutter_sound` given
  the maintainer's own staffing warning, slower release cadence, and pending
  GPL-v3 relicensing of its successor.
- **Permissions:** use `permission_handler` for runtime camera/microphone
  checks on both platforms, paired with `NSCameraUsageDescription` /
  `NSMicrophoneUsageDescription` (+ `NSSpeechRecognitionUsageDescription` if
  `speech_to_text` is adopted) in `Info.plist`, and the existing
  `CAMERA`/`RECORD_AUDIO` entries in the Android manifest.
