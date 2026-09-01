# 自媒体前端内容拆解

这是一个面向内容创作者的可复用工作台：先采集对标账号的公开作品和互动数据，再筛选出相对账号日常表现更好的作品，进入视频解析、内容拆解和发布流程。

项目由两个可替换部分组成：对标采集与热度筛选、视频解析服务。发布使用独立的 social-auto-upload 工具，不嵌入本工作台。

> 本仓库是自媒体内容拆解主工作台。OpenCLI Admin（另一个仓库）只作为可选的对标采集服务；不配置它也可以启动和使用本地复盘、内容拆解等功能。

这个项目适合内容创作者、自媒体运营者和个人团队使用。它不是单纯的上传工具，而是一个可以持续沉淀账号、对标作品和发布结果的可部署运营工作台。

<img src="media/show/tkupload.gif" alt="tiktok show" width="800"/>

## 目录

- [💡 功能特性](#💡功能特性)
- [🧩 核心能力](#🧩核心能力)
- [🚀 支持的平台](#🚀支持的平台)
- [💾 安装指南](#💾安装指南)
- [🏁 快速开始](#🏁快速开始)
- [🐇 项目背景](#🐇项目背景)
- [📃 详细文档](#📃详细文档)
- [🐾 交流与支持](#🐾交流与支持)
- [🤝 贡献指南](#🤝贡献指南)
- [📜 许可证](#📜许可证)
- [⭐ Star History](#⭐Star-History)

## 🧩核心能力

当前工作台包含以下能力：

-   **对标账号管理**：手动添加任意已接入平台的对标账号；账号可选、可添加多个，采集服务负责同步账号和作品数据。
-   **最新作品同步**：点击同步时，自动扫描并补充最多 20 条本地未同步作品；已有作品会更新标题、封面、点赞数和原始数据。
-   **作品数据沉淀**：保存作品标题/文案、点赞数、作品链接、封面和同步时间，形成自己的对标作品库。
-   **作品内容拆解**：基于已同步的标题和文案，生成开头钩子、核心观点、内容结构、爆点分析、人群痛点、可复刻点和脚本建议。
-   **作品复盘**：在同一栏目内分别提供“抖音作品复盘”和“小红书作品复盘”，按平台保存账号作品与实际可取得的互动/创作者数据；未知字段保持为空，不用推测值填充。
-   **发布记录追踪**：每次发布都会记录平台、标题、素材、账号、状态和错误信息，方便复盘和排查问题。
-   **视频解析**：调用可配置的解析服务，将公开分享链接下载到本地素材目录；发布由独立工具完成。
-   **Playwright 浏览器缓存迁移**：将 Playwright 浏览器运行依赖迁移到 E 盘，减少 C 盘占用并提升本地部署稳定性。

简单说，这个版本想解决的是：从“发视频”升级到“找对标、拆内容、做发布、看结果”的完整内容运营流程。文件只作为发布过程中的临时输入，不再维护独立的素材资产产品页。

## 💡功能特性

### 已支持平台

-   **国内平台**:
    -   [x] 抖音
    -   [x] 视频号
    -   [x] Bilibili
    -   [x] 小红书
    -   [x] 快手
    -   [x] 百家号
-   **国外平台**:
    -   [x] TikTok

### 核心功能

-   [x] 定时上传 (Cron Job / Scheduled Upload)
-   [ ] Cookie 管理 (部分实现，持续优化中)
-   [ ] 国外平台 Proxy 设置 (部分实现)

### 计划支持与开发中

-   **平台扩展**:
    -   [ ] QQ视频
    -   [ ] YouTube
-   **功能增强**:
    -   [x] 更易用的版本 (GUI / CLI 交互优化)
    -   [x] API 封装
    -   [ ] Docker 部署
    -   [ ] 自动化上传 (更智能的调度策略)
    -   [ ] 多线程/异步上传优化
    -   [ ] Slack/消息推送通知

---

## 🚀支持的平台

本项目通过各平台对应的 `uploader` 模块实现视频上传功能。您可以在 `examples` 目录下找到各个平台的使用示例脚本。

每个示例脚本展示了如何配置和调用相应的 uploader。

## 💾安装指南

### Windows 本地使用（推荐）

这是面向普通本机用户的最短路径。项目默认只监听 `127.0.0.1`，不会自动发布到公网。

1. 安装 Python 3.11+、Node.js 18+ 和 Google Chrome/Chromium。
2. 克隆仓库并进入目录：

   ```powershell
   git clone https://github.com/usurikey91-ux/zimeiti-qianduan-neirong-chaijie.git
   cd zimeiti-qianduan-neirong-chaijie
   ```

3. 初始化本机环境：

   ```powershell
   pwsh -File .\scripts\setup-local.ps1
   ```

4. 启动整套工作台：

   ```powershell
   pwsh -File .\scripts\workbench.ps1 start -OpenBrowser
   ```

5. 打开 `http://127.0.0.1:5174`。停止服务：

   ```powershell
   pwsh -File .\scripts\workbench.ps1 stop
   ```

如果只需要主工作台，也可以分别运行 `python sau_backend.py`（5409）和在 `sau_frontend` 中运行 `npm.cmd run dev`（5174）。端口被占用时先执行 `workbench.ps1 stop`，不要把另一个项目的 Vite 服务复用到 5174。

### 其他系统或手动安装

1.  **克隆项目**:
    ```bash
    git clone https://github.com/usurikey91-ux/zimeiti-qianduan-neirong-chaijie.git
    cd zimeiti-qianduan-neirong-chaijie
    ```

2.  **安装依赖**:
    建议在虚拟环境中安装依赖。
    ```bash
    conda create -n content-workbench python=3.10
    conda activate content-workbench
    # 挂载清华镜像 or 命令行代理
    pip install -r requirements.txt
    ```

Windows 用户也可以在项目根目录运行以下命令，一次完成 Python 虚拟环境、依赖、本机配置模板和数据库初始化：

```powershell
pwsh -File .\scripts\setup-local.ps1
```

该脚本优先使用 Python 3.11，生成的 `conf.py`、数据库和本机服务配置不会提交到 GitHub。

3.  **安装 Playwright 浏览器驱动**:
    ```bash
    playwright install chromium firefox
    ```
    根据您的需求，至少需要安装 `chromium`。`firefox` 主要用于 TikTok 上传（旧版）。

4.  **修改配置文件**:
    复制 `conf.example.py` 并重命名为 `conf.py`。
    在 `conf.py` 中，您需要配置以下内容：
    -   `LOCAL_CHROME_PATH`: 本地 Chrome 浏览器的路径，比如 `C:\Program Files\Google\Chrome\Application\chrome.exe` 保存。
    
    **临时解决方案**

    需要在根目录创建 `cookiesFile` 和 `videoFile` 两个文件夹，分别是 存储cookie文件 和 存储上传文件 的文件夹

5.  **配置数据库**:
    如果 db/database.db 文件不存在，您可以运行以下命令来初始化数据库：
    ```bash
    cd db
    python createTable.py
    ```
    此命令将初始化 SQLite 数据库。

6.  **启动后端项目**:
    ```bash
    python sau_backend.py
    ```
    后端项目默认在 `http://localhost:5409` 启动。工作台默认使用本机个人模式，不要求管理员账号登录；部署到服务器时请放在反向代理或其他访问控制后，并可通过 `SAU_AUTH_REQUIRED=1` 开启后端鉴权。还可通过 `SAU_BACKEND_HOST` 和 `SAU_BACKEND_PORT` 配置监听地址与端口。

7.  **启动前端项目**:
    ```bash
    cd sau_frontend
    npm install
    npm run dev
    ```
    前端项目将在 `http://localhost:5174` 启动，在浏览器中打开此链接即可访问。


> 非程序员用户可以参考：[新手级教程](https://juejin.cn/post/7372114027840208911)


## 🏁快速开始

### OpenCLI Admin 辅助监控

“对标内容库”可通过可选的 OpenCLI Admin 服务自动发现对标账号新作品，并读取 `hot`/`very_hot` 待分析队列。部署时通过环境变量 `OPENCLI_ADMIN_BASE_URL`，或在 `settings.json` 中配置 `opencliAdminBaseUrl` 指定地址。平台是否可采集由采集服务的适配器决定，主系统不绑定某一个平台。

### 作品复盘数据源

“作品复盘”不把平台连接器伪装成已连接状态。抖音复盘对应 `Kuhakucai/douyin-mcp`，小红书复盘对应 `xpzouying/xiaohongshu-mcp`；在连接器尚未配置时，可直接导入平台官方导出的 CSV/XLSX，先完成事实数据留存。抖音创作者中心的完播、5 秒完播、2 秒跳出等字段只在文件或连接器实际返回时展示；小红书当前只展示实际取得的公开或创作者字段。

### 统一启动

Windows 本机可在项目根目录运行：

```powershell
pwsh -File .\scripts\workbench.ps1 start -OpenBrowser
```

启动器会依次检查并启动视频解析、OpenCLI Admin、主后端和前端，并把本轮进程记录在本地 `.runtime` 目录。查看或关闭：

```powershell
pwsh -File .\scripts\workbench.ps1 status
pwsh -File .\scripts\workbench.ps1 stop
```

辅助项目若与工作台放在同一父目录，会自动识别；其他目录结构可复制 `runtime.local.example.json` 为 `runtime.local.json` 后填写路径，或设置 `OPENCLI_ADMIN_PROJECT_DIR`、`VIDEO_JIEXI_PROJECT_DIR`。本地配置不会提交到仓库，缺少任一可选服务时主工作台仍能启动并明确降级。

### 爆款拆解 AI

推荐在“设置 → 通用 AI 模型服务”中配置模型：可自定义厂商名称、接口协议、API 地址、使用者自己的 API Key 和模型名，保存后会自动设为爆款拆解模型。当前支持 OpenAI 兼容协议、Anthropic 原生协议和 Google Gemini 原生协议；DeepSeek、通义、智谱、Moonshot、OpenRouter 及多数中转站通常可使用 OpenAI 兼容协议。密钥只写入本机的 `settings.json`，该文件已被 Git 忽略，不会上传到仓库。

本机已登录的 Codex CLI 仍可作为可选备用，但项目不依赖 ChatGPT/Codex 登录。没有配置任何 AI 服务时，账号采集、热度判断、视频下载和转写仍可用；爆款拆解会明确显示规则降级结果。

### 爆款判定规则

爆款判定不是和全网账号比较，而是和同一对标账号最近最多 20 条、已有完整公开指标的作品中位数比较：

- `火`（页面显示火焰）：相对倍数 `>= 3.0x`。
- `超级火`（页面显示特别火）：相对倍数 `>= 5.0x`，并优先进入分析队列。
- 小于 `3.0x` 的作品只保留在观察数据中，不进入爆款拆解队列。

作品发布不足 7 天、基线不足 20 条或关键公开指标缺失时，不会强行判定为爆款。当前 `3x/5x` 是产品默认规则，不是每个用户单独保存的动态设置；如需调整，应在代码和测试中同步修改。

1.  **准备 Cookie**: 
    大多数平台需要登录后的 Cookie 信息才能进行操作。请参照 examples 目录下各 `get_xxx_cookie.py` 脚本（例如 get_douyin_cookie.py, get_ks_cookie.py）的说明，运行脚本以生成并保存 Cookie 文件（通常在 `cookies/[PLATFORM]_uploader/account.json`）。

2.  **准备视频文件**: 
    将需要上传的视频文件（通常为 `.mp4` 格式）放置在 videos 目录下。
    部分平台支持视频封面，可以将封面图片（例如 `.png` 格式，与视频同名）也放在此目录。
    如果需要上传标题及标签，请在视频文件旁边创建一个同名的 `.txt` 文件，内容为标题和标签，以换行分隔。

3.  **修改并运行示例脚本**:
    打开 examples 目录中您想使用的平台的上传脚本（例如 upload_video_to_douyin.py）。
    -   根据脚本内的注释和说明，确认 Cookie 文件路径、视频文件路径等配置是否正确。
    -   您可以修改脚本以适应您的具体需求，例如批量上传、自定义标题、标签等。

4.  **执行上传**:
    运行修改后的示例脚本，例如：
    ```bash
    python examples/upload_video_to_douyin.py
    ```

## 🐇项目说明

对标采集、爆款拆解、作品复盘和视频解析集中在本工作台内；多平台发布保持在独立的 social-auto-upload 项目中。

后续可以在不改变主界面的前提下增加平台适配器、评论分析或其他内容工具。



## 🐾交流与支持

欢迎通过 GitHub Issues 反馈安装、平台适配和内容流程问题。


## 📜许可证

本项目采用 [NC 非商业许可协议](LICENSE)。

您可以在非商业目的下学习、研究、修改和分发本项目代码，但不得将本项目或其衍生作品用于任何商业用途。任何商业化使用、商业部署、商业服务、销售、再授权或用于营利性业务场景，均需事先获得项目作者的书面商业授权并支付相应授权费用。

未经授权的商业化使用将被视为侵权行为，项目作者保留追究法律责任、要求停止侵权、赔偿损失并提起诉讼的权利。
