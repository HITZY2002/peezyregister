# peezyregister

自动注册 / 登录 [peezy.p0.systems](https://peezy.p0.systems/connect) 账号，创建 API Key（`p0ag_...`），并推送到自己的 sub2api 实例，形成可用的 OpenAI 兼容上游。

纯 Python 命令行 + WebUI，无浏览器依赖。**所有密钥与服务地址均需自行填写**，代码中不包含任何真实凭据。

## 快速开始

```bash
cd peezyregister
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