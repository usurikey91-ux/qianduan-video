# 本地能力集成

太阳鸟作为主 UI 和主后端，外部项目只作为可替换的本机能力提供方：

## video-jiexi（端口 4200）

- `GET /integrations/video-jiexi/status`：检查解析服务是否在线。
- `POST /integrations/video-jiexi/inspect`：解析公开分享链接。
- `POST /integrations/video-jiexi/download`：创建视频、音频或封面下载任务。
- `GET /integrations/video-jiexi/tasks/{id}`：读取下载进度。
- `POST /integrations/video-jiexi/import`：把已完成的文件复制到太阳鸟 `videoFile` 素材库并登记数据库。

默认连接 `http://127.0.0.1:4200`。如服务使用其他地址，设置环境变量 `VIDEO_JIEXI_BASE_URL`；如下载目录不是默认目录，设置 `VIDEO_JIEXI_DOWNLOAD_DIR`。

## social-auto-upload

太阳鸟本身已经保留并调用同源的 `uploader` 与发布记录模块，发布中心不再额外启动第二个 5409 服务，也不把 Cookie 发送到外部服务。这样可以避免两个后端争抢同一个端口，并保证发布记录、素材和账号状态都留在太阳鸟数据库中。

原项目目录 `D:\ai-coding\视频一键分发\social-auto-upload` 继续作为参考实现和可替换源，不作为太阳鸟运行时依赖。

