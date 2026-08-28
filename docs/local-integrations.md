# 本地能力集成

太阳鸟作为主 UI 和主后端，外部项目只作为可替换的本机能力提供方：

## video-jiexi（端口 4200）

- `GET /integrations/video-jiexi/status`：检查解析服务是否在线。
- `POST /integrations/video-jiexi/inspect`：解析公开分享链接。
- `POST /integrations/video-jiexi/download`：创建视频、音频或封面下载任务。
- `GET /integrations/video-jiexi/tasks/{id}`：读取下载进度。
- `POST /integrations/video-jiexi/import`：把已完成的文件复制到太阳鸟 `videoFile` 素材库并登记数据库。

解析服务是可选提供方，默认不连接任何地址。部署时通过环境变量 `VIDEO_JIEXI_BASE_URL` 或运行时设置 `videoJiexiBaseUrl` 指定服务地址。远程服务建议同时配置 `VIDEO_JIEXI_API_TOKEN`（或 `videoJiexiApiToken`），太阳鸟会通过 `Authorization: Bearer …` 调用；未配置 Token 时仅适合同机受限部署。

只有在两个服务明确共享文件系统、且提供方没有文件接口时，才设置 `VIDEO_JIEXI_DOWNLOAD_DIR` 作为兼容回退；它没有默认路径。

提供方应实现 `GET /api/downloads/{id}/file`，这样太阳鸟只通过 HTTP 获取已完成文件，不依赖本机目录结构。

## social-auto-upload

太阳鸟本身已经保留并调用同源的 `uploader` 与发布记录模块，发布中心不再额外启动第二个 5409 服务，也不把 Cookie 发送到外部服务。这样可以避免两个后端争抢同一个端口，并保证发布记录、素材和账号状态都留在太阳鸟数据库中。

原 `social-auto-upload` 项目继续作为参考实现和可替换源，不作为太阳鸟运行时依赖。

## 公开部署配置

太阳鸟前端生产构建默认使用同源 API（`VITE_API_BASE_URL` 留空），因此可以放在 Nginx、Caddy 或其他反向代理后。部署到独立域名或端口时再设置 `VITE_API_BASE_URL`。

后端可用环境变量：

```env
SAU_BACKEND_HOST=0.0.0.0
SAU_BACKEND_PORT=5409
OPENCLI_ADMIN_BASE_URL=https://collector.example.com/api/v1
OPENCLI_ADMIN_API_TOKEN=change-me
VIDEO_JIEXI_BASE_URL=https://parser.example.com
VIDEO_JIEXI_API_TOKEN=change-me
```

这些地址和 Token 也可以写入太阳鸟运行时 `settings.json`（字段名见上文），不要把真实 Token 提交到 GitHub。
