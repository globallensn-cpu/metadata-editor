# Reaboard Security Policy & Threat Model

## 1. Security Architecture Principles

Reaboard is an unauthenticated, privacy-first processing utility that handles untrusted binary media uploads.
The system is built on zero-knowledge guarantees and defensive isolation:

1. **Zero Shell Interpolation**: All external tools (`ffmpeg`, `exiftool`, `qpdf`) are invoked strictly through `subprocess.run(args, shell=False)` with argument arrays. User filenames are never passed into command arguments or path resolutions.
2. **Ephemeral Storage Isolation**: Uploaded files live in temporary isolated mounts (`/tmp/reaboard/{uuid}/`). Original files are never modified in place.
3. **Hard Automated Purge**: An asynchronous cleanup sweeper permanently deletes all job artifacts after 60 minutes. An immediate "Delete Now" endpoint (`DELETE /api/v1/jobs/{id}`) allows instant user-initiated purging.
4. **HMAC-SHA256 Expiring Downloads**: Cleaned files cannot be enumerated or scraped. Downloads require an HMAC-SHA256 signature binding the job ID, an epoch expiration timestamp (15-minute TTL), and a server-side secret key.
5. **Magic Byte Authority**: File extensions and client `Content-Type` headers are treated as untrusted hints. File types are determined exclusively via binary magic bytes. Disguised executables (`MZ`, `ELF`) or script payloads trigger immediate HTTP 415 rejection.
6. **No Metadata Value Logging**: Server application logs record only operational telemetry (job ID, MIME type, size, latency, error code). User filenames, GPS coordinates, author names, and camera serial numbers are strictly excluded from logging.

---

## 2. Worker Container Confinement

In production container environments, worker execution is locked down:
- **Non-Root Execution**: Runs as dedicated UID `10001:10001` (`reaboard`).
- **Read-Only Root Filesystem**: `read_only: true`.
- **Capability Dropping**: `cap_drop: ALL`, with `no-new-privileges: true`.
- **Network Isolation**: `network_mode: none` (worker containers have zero inbound or outbound network access).
- **Execution Limits**: Hard memory ceilings (1024 MB) and process group kill on execution timeouts (300 s).

---

## 3. Reporting a Vulnerability

If you discover a security vulnerability in Reaboard, please contact the maintainers at `security@reaboard.local`.
All verified issues are addressed within 48 hours.
