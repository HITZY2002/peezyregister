# Peezy2API

自动注册 / 登录 [peezy.p0.systems](https://peezy.p0.systems/connect) 账号，创建 API Key（`p0ag_...`），并推送到自己的 sub2api 实例，形成可用的 OpenAI 兼容上游。

纯 Python 命令行 + WebUI，无浏览器依赖。**所有密钥与服务地址均需自行填写**，代码中不包含任何真实凭据。

## 参考项目

本项目参考了以下开源项目（自动化思路与基础设施方案）：

- [Sliverkiss](https://github.com/Sliverkiss) 系列 —— [workbuddy2api](https://github.com/Sliverkiss/workbuddy2api) / [traework2api](https://github.com/Sliverkiss/traework2api) / [qoderwork2api](https://github.com/Sliverkiss/qoderwork2api)：账号生命周期自动化与 OpenAI 兼容上游的总体思路
- [cloudflare_temp_email](https://github.com/dreamhunter2333/cloudflare_temp_email)（[Dream Hunter](https://github.com/dreamhunter2333)）：临时邮箱 Worker 方案（本项目兼容其 API）

感谢原作者的开源与优秀设计。

## 流程

```text
1. 临时邮箱 API 创建邮箱（cloudflare_temp_email 兼容，自行部署/填写地址）
2. CaptchaRun 打 hCaptcha（sitekey 从 /auth/config 动态获取）
3. POST https://api.p0.systems/auth/email/register -> {token, user}
   （注册直接返回 token，无需邮箱验证；token 有效期 7 天）
4. POST https://api.p0.systems/api/agents/v1/api-keys -> apiKey (p0ag_...)
5. POST sub2api /api/v1/admin/accounts
   platform=openai, type=apikey, credentials.api_key=..., base_url=https://api.p0.systems/api/agents/v1
```

## 需要自行准备

| 项目 | 说明 |
| --- | --- |
| CaptchaRun 令牌 | 登录 [captcha-run.com](https://captcha-run.com) 后台「用户信息」页获取。没有账号可点此注册（邀请）：https://captcha-run.com/sso?inviter=ce5f1e67-e364-40b9-9593-6be2f36d2108 |
| 临时邮箱 API | cloudflare_temp_email 兼容的 Worker 邮箱服务地址 + 收信域名 |
| sub2api | 管理 API 地址 + 后台生成的 Admin API Key + 目标分组 |

## 接口依据（逆向自前端 `assets/index-B48DHMMc.js`）

| 用途 | 接口 |
| --- | --- |
| 登录方式/打码配置 | `GET /auth/config`（返回 `hcaptcha.siteKey`、`hcaptchaRequired`） |
| 邮箱注册 | `POST /auth/email/register` `{email,password,captchaToken}` -> `{token,user}` |
| 邮箱登录 | `POST /auth/email/login` 同上 |
| 创建 API Key | `POST /api/agents/v1/api-keys` `{name}`，`Authorization: Bearer <token>` -> `{apiKey}` |
| 上游网关 | `https://api.p0.systems/api/agents/v1`（OpenAI 兼容）/ `https://api.p0.systems/api/agents`（Anthropic 兼容） |
| 打码建任务 | `POST https://api.captcha.run/v2/tasks` `{captchaType:"HCaptcha",siteKey,siteReferer,useCache}` |
| 打码取结果 | `GET https://api.captcha.run/v2/tasks/{taskId}`（status=Success 时取 `response.gRecaptchaResponse`） |
| 临时邮箱 | `POST {mail_api_base}/api/new_address` -> `{address,jwt,password}`；`GET /api/mails?limit=&offset=` |
| sub2api 建号 | `POST {sub2api}/api/v1/admin/accounts`，`x-api-key: <Admin Key>` |

## 快速开始

```bash
cd peezy2api
python -m pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，至少填写：
#   CAPTCHA_RUN_TOKEN      CaptchaRun 令牌
#   MAIL_API_BASE          临时邮箱 API 地址
#   SUB2API_API_BASE       你的 sub2api 地址
#   SUB2API_API_KEY        sub2api Admin API Key

# 命令行：注册 1 个新账号并推送
python main.py --count 1

# 已有账号模式（文件每行 email====password）
python main.py --mode login --account-file accounts_to_login.txt

# 本机有代理导致 api.p0.systems 连接不稳时直连
python main.py --count 1 --direct
```

结果写入 `accounts.json`（email / password / auth_token / api_key / sub2api_account_id 等）。

## WebUI 控制台

```bash
python web.py                # 启动后自动打开 http://127.0.0.1:8000
python web.py --port 8001    # 换端口
python web.py --no-browser   # 不自动打开浏览器
```

WebUI 支持：

- **打码平台填写栏**：CaptchaRun Token 输入框，旁边附注册邀请入口（https://captcha-run.com/sso?inviter=ce5f1e67-e364-40b9-9593-6be2f36d2108）
- **临时邮箱 API**：邮箱服务地址 + 收信域名
- **sub2api**：管理 API 地址 + Admin API Key（保存后写入 .env，不入代码）
- **sub2api 分组选择**：自动拉取 openai 平台分组下拉选择；也可填分组名自动创建
- **并发数设置**：注册并发（线程数）+ sub2api 账号并发
- **模型映射设置**：JSON 编辑框（`{"请求模型":"上游模型"}`），一键填默认映射（auto / kimi-k3 / grok-4.5）
- 后台运行注册/登录任务，实时日志、进度统计、结果表格（API Key 一键复制）

## 配置说明（.env）

| 变量 | 说明 |
| --- | --- |
| `CAPTCHA_RUN_TOKEN` | CaptchaRun 令牌，必填 |
| `MAIL_API_BASE` | 临时邮箱 API 地址，必填 |
| `MAIL_DOMAINS` | 收信域名，逗号分隔（留空由 Worker 决定） |
| `SUB2API_API_BASE` | sub2api 管理地址，必填 |
| `SUB2API_API_KEY` | sub2api Admin API Key，必填 |
| `SUB2API_GROUP_ID` / `SUB2API_GROUP_NAME` | 目标分组 |
| `PEEZY_MODELS` | 默认 `["kimi-k3","grok-4.5"]` |
| `DIRECT` | 直连开关（绕过系统代理，本机 Clash 不稳时设 true） |

## 目录结构

```text
config/            .env 加载与各模块配置
core/              http / 打码 / 邮箱 / Peezy / sub2api 客户端 + 编排
webui/             Flask WebUI 控制台
main.py            命令行入口
web.py             WebUI 入口
accounts.json      注册结果（自动生成，已 gitignore）
```

## 注意事项

- Peezy 注册无需邮箱验证即可拿 token，但账号最终有效性取决于平台风控；建议控制频率。
- hCaptcha token 有效期约 2 分钟，程序是「打码成功立刻注册」，无需人工介入。
- 失败自动换新邮箱重试（`PEEZY_REGISTER_RETRIES`，默认 3 次）。
- 仅供学习研究，使用请遵守目标平台服务条款。

## License

MIT
