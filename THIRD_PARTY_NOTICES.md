# Third-party components

The main setup script downloads the following components into the Git-ignored
`.runtime/connectors` directory. They remain separate programs and keep their
own licenses.

| Component | Pinned source | License | Local integration |
| --- | --- | --- | --- |
| `douyin-mcp` | `Kuhakucai/douyin-mcp` at `53c888a` | AGPL-3.0-only | The patch in `third_party/patches/douyin-mcp-53c888a.patch` is distributed under AGPL-3.0-only. |
| `opencli-admin` | `usurikey91-ux/opencli-admin` at `b056380` | Apache-2.0 | The patches in `third_party/patches/opencli-admin-b056380.patch` and `opencli-admin-bootstrap.patch` preserve the upstream Apache-2.0 notice. |
| `@jackwener/opencli` | npm version `1.8.6` | Apache-2.0 | Installed locally under `.runtime/tools`; it is not committed to this repository. |
| `video-jiexi` | Bundled local component | Main repository license | Installed into `.runtime/connectors` with a project-local `ffmpeg-static` runtime. |

Downloading or running these tools does not grant access to platform data or
permission to bypass login, verification, terms, or risk controls. Each user
must log in to their own account on the official platform page.
