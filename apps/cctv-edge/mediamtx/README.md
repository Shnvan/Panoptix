# mediamtx Configuration

Placeholder for gateway-side `mediamtx` configuration.

Configuration must be pinned, reviewed, and kept aligned with the security invariants before pilot use.

No production runtime configuration is included yet.

## Local synthetic RTSP source

The edge agent can now build a dev/test FFmpeg command for a synthetic RTSP source using `testsrc` video and `sine` audio.

Default local output:

```text
rtsp://127.0.0.1:8554/synthetic-camera-1
```

For manual testing, run `mediamtx` separately and keep its HTTP API disabled or bound to loopback only.

Security expectations:

- do not expose local `mediamtx` to WAN
- do not bind the `mediamtx` HTTP API to `0.0.0.0`
- do not put camera credentials in synthetic RTSP URLs
- do not use browser, webcam, or phone publishing paths

Real `mediamtx` process supervision remains a later milestone.
