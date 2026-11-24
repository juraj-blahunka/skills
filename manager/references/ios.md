# iOS projects: what to add to the ground rules

Each of these cost a real run hours.
Copy the ones that apply into the project section of common.md.

## Simulators

- Each agent claims its own simulator through the `simctlhouse` skill and releases it when done.
  If simctlhouse's wrapper commands get flagged by auto mode, plain `xcrun simctl` against the claimed UDID is allowed.
- simctlhouse simulators are slimmed: name the `simslim` profile each brief needs up front.
  Photos, sharing and web: `simslim on <udid> --except photos,web,connectivity`.
  Widgets, controls and intents (linkd): `simslim on <udid> --except widgets,siri,search,other`.
  Restore the standard profile afterwards.
- Erased slim simulators can stay in light mode whatever simctl says; screenshot-check the appearance before trusting a dark-mode result.
- A simulator that ran VoiceOver probes can misreport contrast in later audits until erased.

## Builds and tests

- Always build the workspace, never `-project` (a stray workspace brings its own Package.resolved).
- Pair `test-without-building` with a fresh `build-for-testing` in the same command; a stale build wastes runs.
- No scratch builds into the same DerivedData while a test run uses it; scratch builds get their own `-derivedDataPath`.
- Before DONE: `xcodebuild -configuration Release -destination generic/platform=iOS CODE_SIGNING_ALLOWED=NO build`.
  DEBUG-only helpers used by `#Preview` break the Release archive.
- Two UI test runs in parallel share the Mac-synced simulator pasteboard; never run paste or clipboard journeys concurrently.
- XCTest's idle wait can stall on a UIKit animation that never reports its stop; watch test durations, not only pass or fail.

## Proof

- Record once by wrapping `xcrun simctl io <udid> recordVideo --codec h264 <file>` around a committed UI journey or one short scripted test, not by hand-driving over many takes.
- Extract a few frames with ffmpeg and look at them before reporting.

## Behavior

- Anything that moves focus, scroll or the keyboard: check every way the app can be opened (widgets, URLs, intents, share sheet).
- Controls: an `OpenURLIntent` from a control's intent can be silently dropped; an intent with `supportedModes = .foreground` plus `onAppIntentExecution` in the app works.

## Release builds

- TestFlight "What to Test" written from commit subjects alone can be wrong; feed it the commit bodies or check it before upload.
