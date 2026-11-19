# Changelog

All notable changes to the Reaboard project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-19

### Added
- **Real Worker Architecture & ARQ Job Dispatch**: API delegates resource-intensive media processing to background ARQ workers; job state tracked via Redis hashes with TTL and real-time progress broadcast over Redis pub/sub.
- **Strict State Machine**: Validates transitions (`created -> uploaded -> queued -> analyzing -> cleaning -> verifying -> completed | completed_with_warnings | failed | expired`) and rejects illegal transitions with `409 Conflict` (`INVALID_STATE`).
- **Comprehensive Format Pipelines**:
  - **PDF Dual-Pass**: ExifTool `-all=` followed by QPDF linearization and orphaned object dropping; verifies raw bytes scan for unrecoverable author/producer strings.
  - **Office OOXML (DOCX/XLSX/PPTX)**: XML sanitization of `docProps/core.xml`, `docProps/app.xml`, `custom.xml`, and Word `rsid` tracking attributes with deterministic timestamps (`1980-01-01`).
  - **Audio (MP3/M4A/FLAC/WAV/OGG)**: Stream copy remuxing and ExifTool tag stripping.
  - **Video (MP4/MOV/MKV/WebM/AVI)**: Multi-stream packet MD5 hashing across all video/audio streams, duration tolerance validation, and track handler blanking.
- **Re-encode Confirmation Dialog**: Explicit user consent required before fallback re-encoding (CRF 18) if stream copy remuxing fails.
- **Dual-Pass Verification & Honest Reporting**: Survivor classification into `structural`, `identifying`, and `unknown`; status sets `completed_with_warnings` if identifying survivors persist through secondary passes; reports `stream_copy: null` ("N/A") on images and documents.
- **Security & Limits**:
  - Magic byte detection reading 64 KB with exact ISO Base Media File Format `ftyp` brand mapping; strict rejection of hostile executables (PE/ELF/Mach-O) and scripts disguised with media extensions.
  - OOXML zip bomb constraints (max 500 entries, max 200 MB uncompressed, max 10:1 ratio).
  - RFC 6266 `Content-Disposition` header formatting with UTF-8 encoding.
  - HMAC-SHA256 download URL signing bound to `job_id`, `expires_at`, and `dl_name`.
  - Dynamic secret key enforcement (raises in production if <32 characters, ephemeral in development).
  - Rate limiting on upload endpoint (30 uploads/hour default).
  - Isolated temporary storage with strict UUID path traversal checks.
  - Background cleanup scheduler sweeping expired Redis jobs and orphaned disk directories.
- **Frontend Enhancements**:
  - Full camelCase wire format compatibility.
  - `completed_with_warnings` visual amber badge and explanatory banner.
  - Re-encoding confirmation modal.
  - Next.js 15 standalone output and dynamic internal API rewrites (`API_INTERNAL_URL`).
- **Infrastructure**:
  - Internal Docker network (`internal: true`) for `redis`, `worker`, and `api` with zero internet egress from the worker container.
  - Multi-stage Dockerfiles running as non-root users with healthchecks.
  - GitHub Actions CI workflow for linting, typing, testing, and Docker Compose validation.

### Changed
- Standardized wire protocol to camelCase while maintaining snake_case internally in Python.
- Removed synchronous subprocess executions in async contexts in favor of secure subprocess runners with process group termination on timeouts.
