# MediReminder 项目记忆

## 项目名称
Zs服药提醒智能体

## 技术决策
- 后端框架：FastAPI + Jinja2 SSR（非 SPA，简化 MVP 开发）
- 数据库：Supabase PostgreSQL，通过 REST API (PostgREST) 访问
- 认证：Supabase Auth（邮箱注册登录），Cookie 传递 token
- OCR：EasyOCR (支持中英文)；支持 Claude/OpenAI Vision 可插拔
- 前端：原生 JS + 响应式 CSS，无框架依赖
- 部署：单进程 uvicorn，无反向代理
- 定时任务：APScheduler（每日记录生成、过期检查、推送通知）
- 推送：Web Push API + VAPID + pywebpush
- 存储：Supabase Storage（图片），本地目录兜底
- 用户设置：支持 AI 提供商切换和 API 密钥配置

## 关键架构决策
- 模板引擎使用自定义 `render()` 函数而非 Starlette 的 `Jinja2Templates`，避免 Jinja2 3.1.6 LRU 缓存兼容问题
- 每日服药记录由 `notification_service.generate_today_records()` 自动生成
- 图片上传先识别后保存路径，路径存储相对路径
- AI 识别采用可插拔后端架构：EasyOCRBackend / VisionAPIBackend，按用户设置自动切换
- Web Push 采用 VAPID 自动密钥生成 + 多设备订阅管理
- 定时任务 4 个 Job：记录生成(00:05+03:00)、过期检查(08:00)、提醒推送(每分钟)

## 已解决的关键问题
1. 循环导入：templates 实例独立于 main.py 放在 app/templates.py
2. bcrypt 5.0 与 passlib 不兼容：改用 hashlib PBKDF2-SHA256（v2.0 后已移除，改用 Supabase Auth）
3. Jinja2 LRU cache key 类型错误：自定义 render 函数绕过

## 数据库表 (v2.1 Supabase)
- medicines, reminders, medication_records (v1.0)
- push_subscriptions: Web Push 设备订阅（endpoint, p256dh, auth）
- user_settings: 用户设置（AI提供商、API密钥、推送开关）
- 所有表启用 RLS，用户只能访问自己的数据

## Supabase 配置
- Project URL: https://wchcfukrdmsymygplrkn.supabase.co
- 部署前需在 SQL Editor 执行 supabase_client.py 中的 CREATE_TABLES_SQL
