# mediamtx Configuration

Gateway-side `mediamtx` configuration scaffolding.

Configuration must be pinned, reviewed, and kept aligned with the security invariants before pilot use.

No production runtime configuration is included yet.

## Local runtime scaffold

`mediamtx.local.yml` is a dev/test scaffold for the synthetic RTSP source. It is intentionally local-only:

```text
rtspAddress: 127.0.0.1:8554
api: no
apiAddress: 127.0.0.1:9997
```

The edge-agent test suite verifies that the checked-in config matches the generated safe defaults and that API bindings are disabled or loopback-only.

## Local process management

The edge agent can build a safe `mediamtx` process argument list and manage a local process through an injectable lifecycle manager.

Default command shape:

```text
mediamtx apps/cctv-edge/mediamtx/mediamtx.local.yml
```

Automated tests use fake process objects. They do not require `mediamtx` to be installed and do not launch media processes.

## Local synthetic RTSP source

The edge agent can now build a dev/test FFmpeg command for a synthetic RTSP source using `testsrc` video and `sine` audio.

Default local output:

```text
rtsp://127.0.0.1:8554/synthetic-camera-1
```

For manual testing, run `mediamtx` separately with `mediamtx.local.yml` and keep its HTTP API disabled or bound to loopback only.

Security expectations:

- do not expose local `mediamtx` to WAN
- do not bind the `mediamtx` HTTP API to `0.0.0.0`
- do not put camera credentials in synthetic RTSP URLs
- do not use browser, webcam, or phone publishing paths

Production Docker/systemd supervision remains a later milestone.
