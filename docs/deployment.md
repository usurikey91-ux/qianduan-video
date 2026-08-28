# 可复用部署说明

太阳鸟由一个主应用和两个可选能力服务组成：

```text
浏览器
  ↓
反向代理（同源 HTTPS）
  ├─ 太阳鸟前端静态文件
  └─ 太阳鸟后端
       ├─ OpenCLI Admin（可选：账号巡检与热度筛选）
       └─ video-jiexi（可选：视频解析与下载）
```

## 最小部署

只运行太阳鸟即可使用账号、素材、拆解和发布功能。前端生产构建保持 `VITE_API_BASE_URL` 为空，API 使用同源路径，不包含任何开发机地址。

## 接入采集和解析服务

在太阳鸟设置页或环境变量中配置：

```env
OPENCLI_ADMIN_BASE_URL=https://collector.example.com/api/v1
OPENCLI_ADMIN_API_TOKEN=change-me
VIDEO_JIEXI_BASE_URL=https://parser.example.com
VIDEO_JIEXI_API_TOKEN=change-me
```

OpenCLI Admin 和 video-jiexi 可以部署在独立机器、容器或云服务中。太阳鸟通过 HTTP 调用，不要求共享代码仓库或本机目录。

对标内容库中的 `hot`/`very_hot` 作品可以直接跳转到视频解析页，完成解析、下载和素材导入后，再进入太阳鸟已有的拆解与发布流程。

## 生产注意事项

- 使用 HTTPS 和反向代理，不直接暴露 Flask 开发服务器。
- Token 只放在服务器环境变量或本机 `settings.json`，不要提交到 GitHub。
- 太阳鸟数据库、Cookie、素材目录应使用独立持久化卷。
- video-jiexi 提供 `GET /api/downloads/{id}/file` 后，太阳鸟无需访问解析服务的文件系统。
- 平台 Cookie 只保存在实际执行采集/发布的服务所在机器。
