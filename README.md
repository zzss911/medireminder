# Zs服药提醒智能体 💊

AI 驱动的服药提醒应用，支持手机和桌面。拍照识别药品信息，定时推送服药提醒。

## 技术栈

- **后端**: Python FastAPI + Jinja2 SSR
- **数据库**: Supabase PostgreSQL
- **认证**: Supabase Auth（邮箱注册登录）
- **AI 识别**: 通义千问 Qwen-VL-Plus（推荐）/ Claude / OpenAI / EasyOCR
- **推送**: Web Push API（VAPID + pywebpush）
- **部署**: Vercel Serverless

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的密钥：

```bash
cp .env.example .env
```

**必须填写的两项：**

| 变量 | 说明 | 获取渠道 |
|------|------|----------|
| `SUPABASE_SERVICE_KEY` | Supabase 服务端密钥 | Supabase Dashboard → API |
| `AI_API_KEY` | 千问 API Key | [阿里云 DashScope](https://dashscope.console.aliyun.com/apiKey) |

### 3. 创建数据库表

登录 [Supabase SQL Editor](https://supabase.com/dashboard/project/wchcfukrdmsymygplrkn/sql/new)，执行 `app/supabase_client.py` 中的 `CREATE_TABLES_SQL`。

### 4. 启动本地开发

```bash
python run.py
```

打开 http://localhost:8000

### 5. 部署到 Vercel

```bash
npm i -g vercel
vercel --prod
```

需要在 Vercel Dashboard → Settings → Environment Variables 中配置以下环境变量。

### 定时任务（GitHub Actions）

项目使用 GitHub Actions 定时调用 Vercel 接口实现服药提醒推送：

| Workflow | 频率 | 端点 |
|----------|------|------|
| `medireminder-cron.yml` | 每 5 分钟 | `POST /api/cron/send-reminders` |
| `medireminder-records.yml` | 每天 8:00 (UTC+8) | `POST /api/cron/generate-records` |
| `medireminder-expiry.yml` | 每天 16:00 (UTC+8) | `POST /api/cron/check-expiry` |

**需要在 GitHub 仓库 Settings → Secrets and variables → Actions 配置两个 Secrets：**

| Secret | 说明 |
|--------|------|
| `APP_BASE_URL` | 你的 Vercel 生产地址，如 `https://www.zs-ai.xyz` |
| `CRON_SECRET` | 一个随机字符串，**同时在 Vercel 环境变量也配一份** |

生成 CRON_SECRET：
```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

## AI 识别模型

| 模型 | 精度 | 价格 | 推荐场景 |
|------|------|------|----------|
| **qwen-vl-plus**（默认） | 高 | ¥0.008/千token | 药品标签识别 |
| qwen-vl-max | 最高 | ¥0.02/千token | 复杂药品说明书 |
| qwen2.5-vl-7b-instruct | 中 | ¥0.002/千token | 预算有限 |

切换模型：在 `.env` 中设置 `QWEN_MODEL=qwen-vl-max`

## 目录结构

```
├── api/index.py          # Vercel Serverless 入口
├── app/                  # 后端
│   ├── main.py           # FastAPI 入口
│   ├── config.py         # 配置
│   ├── auth.py           # 认证
│   ├── routers/          # API 路由
│   └── services/         # 业务服务
├── static/               # 前端资源
├── templates/            # Jinja2 模板
├── vercel.json           # Vercel 部署配置
└── requirements.txt
```
