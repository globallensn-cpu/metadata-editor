# Reaboard

> **Clean metadata. Keep the quality. Stay private.**

Reaboard is a production-grade, privacy-first web tool and processing engine to inspect every piece of metadata inside media files (video, image, audio, documents) and download cleaned copies with transparent, verified before-and-after reporting.

---

## Key Features

1. **Lossless Quality by Default**: Video and audio containers (MP4, MOV, MKV, WebM, AVI) are cleaned via lossless stream copy remuxing (`-c copy`, `-fflags +bitexact`). Media streams are never silently re-encoded.
2. **Dual-Pass Verification**: Every cleaned output is re-extracted with ExifTool and FFprobe. The engine computes stream-level packet MD5 hashes to guarantee that audio/video frames are bit-for-bit identical to the original.
3. **Transparent Diffing & Survivor Classification**: The UI displays exactly what tags were stripped (with partial masking for sensitive values) and classifies survivors into `structural` (codecs, dimensions, rotation) vs. `identifying`.
4. **Honest Limits**: Reaboard never makes false claims of "100% clean". Known boundaries (content-level watermarks, sensor PRNU noise, operating system timestamps) are prominently documented.
5. **Privacy First**: Zero permanent storage. Uploaded files live in temporary memory, are purged automatically after 60 minutes, or instantly upon clicking "Delete Now". Download links are HMAC-SHA256 signed with 15-minute expiration tokens.

---

## Monorepo Architecture

```
reaboard/
├── apps/
│   ├── web/           # Next.js 15 (App Router, Tailwind CSS, Lucide icons)
│   ├── api/           # Python 3.12 + FastAPI + Pydantic v2
│   └── worker/        # Asynchronous sandboxed processing worker
├── packages/
│   └── shared/        # OpenAPI 3.1 schema & TypeScript contracts
├── infra/
│   ├── docker-compose.yml  # Multi-service composition (web, api, worker, redis)
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   └── Dockerfile.web
└── tests/             # Pytest test suite with synthetic media fixtures
```

---

## Quickstart

### Prerequisites
- Python 3.12+
- Node.js 20+
- FFmpeg 6+ & FFprobe
- ExifTool 12+

### Running the Test Suite

```bash
# Run unit and integration tests (asserts lossless remuxing, packet MD5 hashes, and API lifecycle)
python -m pytest tests/ -v
```

### Starting the Services Locally

```bash
# 1. Start the FastAPI backend
python -m uvicorn apps.api.src.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start the Next.js frontend (in apps/web)
cd apps/web
npm install
npm run dev
```

Visit `http://localhost:3000` to access the application.

---

## Security & Confinement

Refer to [SECURITY.md](SECURITY.md) for detailed threat modeling, sandboxing specifications, and vulnerability disclosure policies.
