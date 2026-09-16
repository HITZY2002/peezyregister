# PeezyRegister

PeezyRegister 是一个用于处理 [Peezy（p0.systems）](https://peezy.p0.systems/connect) 账号的 Python 工具，可完成账号注册或已有账号登录、创建 Peezy API Key，并可按需同步到自己的 sub2api 实例。

项目同时提供 CLI 与 WebUI，两种入口共用同一套配置与执行逻辑。

> [!NOTE]
> 本项目随缘维护，不保证持续或及时更新。若后续 Peezy 的注册/登录流程、接口或相关网址发生变化导致项目失效，请 Fork 本仓库后自行修改并适配最新流程。

## 功能

- Peezy 邮箱注册与已有账号登录
- hCaptcha 打码接入（CaptchaRun）
- 临时邮箱 API 接入
- 自动创建 Peezy API Key（`p0ag_...`）
- 可选同步到 sub2api
- sub2api 分组选择与模型映射
- 批量注册与并发执行
- 本地结果保存、实时日志与任务状态查看
- 支持直连或指定 HTTP 代理

## 快速开始

```bash
git clone https://github.com/HITZY2002/peezyregister.git
cd peezyregister

python -m pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`，至少根据需要填写：

```env
CAPTCHA_RUN_TOKEN=
MAIL_API_BASE=
SUB2API_API_BASE=
SUB2API_API_KEY=
```

注册一个新账号并按配置推送：

```bash
python main.py --count 1
```

批量注册：

```bash
python main.py --count 5 --workers 2
```

登录已有账号：

```bash
python main.py --mode login --account-file accounts_to_login.txt
```

账号文件每行格式：

```text
email@example.com====password
```

如果本机系统代理影响 Peezy API 连接，可使用直连模式：

```bash
python main.py --count 1 --direct
```

也可以显式指定 HTTP 代理：

```bash
python main.py --count 1 --proxy http://127.0.0.1:7897
```

## WebUI

启动 WebUI：

```bash
python web.py
```

默认地址：

```text
http://127.0.0.1:8000
```

其他常用参数：

```bash
python web.py --port 8001
python web.py --no-browser
```

WebUI 可完成：

- CaptchaRun Token 配置
- 临时邮箱 API 与收信域名配置
- sub2api 管理地址与 Admin API Key 配置
- sub2api 分组选择或按名称自动创建分组
- 注册数量、注册并发与 sub2api 账号并发设置
- 模型映射编辑
- 直连 / 代理切换
- 后台任务启动、停止、日志与进度查看
- 注册结果与 API Key 查看

配置保存到项目根目录 `.env`。

## 处理流程

```text
临时邮箱
   ↓
hCaptcha
   ↓
Peezy 注册 / 登录
   ↓
创建 Peezy API Key
   ↓
保存结果
   ↓
可选：同步到 sub2api
```

Peezy 的 hCaptcha sitekey 会优先从 `/auth/config` 动态获取，配置文件中的 sitekey 仅作为兜底。

## CLI 参数

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--count` | 注册 / 处理账号数量 |
| `--mode register\|login` | 注册新账号或登录已有账号 |
| `--workers` | 注册并发线程数 |
| `--account-file` | login 模式账号文件 |
| `--output` | 结果输出文件 |
| `--group-id` | 指定 sub2api 分组 ID |
| `--group-name` | 指定分组名，找不到时自动创建 |
| `--no-push` | 不同步到 sub2api |
| `--dry-run` | 执行流程但跳过推送 |
| `--direct` | 绕过系统 / 环境代理 |
| `--proxy` | 显式指定 HTTP 代理 |
| `-v, --verbose` | 输出详细日志 |

完整参数可通过以下命令查看：

```bash
python main.py --help
```

## 配置

主要配置均放在 `.env`，示例见 `.env.example`。

| 变量 | 说明 |
| --- | --- |
| `CAPTCHA_RUN_TOKEN` | CaptchaRun Token |
| `MAIL_API_BASE` | 临时邮箱 API 地址 |
| `MAIL_DOMAINS` | 收信域名，多个域名可用逗号分隔 |
| `SUB2API_AUTO_PUSH` | 是否自动同步到 sub2api |
| `SUB2API_API_BASE` | sub2api 管理 API 地址 |
| `SUB2API_API_KEY` | sub2api Admin API Key |
| `SUB2API_GROUP_ID` | 目标分组 ID |
| `SUB2API_GROUP_NAME` | 目标分组名称 |
| `SUB2API_CONCURRENCY` | sub2api 账号并发参数 |
| `SUB2API_MODEL_MAPPING` | 模型映射 JSON |
| `PEEZY_MODELS` | 默认模型列表 |
| `REGISTER_WORKERS` | 默认注册并发数 |
| `DIRECT` | 是否绕过系统代理 |
| `PROXY` | 显式 HTTP 代理 |

外部服务地址和用户凭据均通过 `.env` 或 WebUI 配置，仓库中不包含个人实际密钥。

## 输出

默认结果文件：

```text
accounts.json
```

记录内容包括注册 / 登录状态及后续使用所需的信息，例如：

```text
email
password
auth_token
api_key
sub2api_account_id
group_id
created_at
```

`.env`、`accounts.json`、`accounts_to_login.txt` 和运行日志均已加入 `.gitignore`。这些文件可能包含账号凭据或 API Key，请自行妥善保存。

## 目录结构

```text
config/                 配置加载与各模块配置
core/                   Peezy / CaptchaRun / 邮箱 / sub2api 客户端及执行流程
webui/                  Flask WebUI
main.py                 CLI 入口
web.py                  WebUI 入口
.env.example             配置示例
requirements.txt         Python 依赖
```

## 说明

- Peezy、CaptchaRun、临时邮箱以及 sub2api 的接口行为可能随上游版本变化。
- 注册是否成功以及账号后续可用性以 Peezy 当前服务状态为准。
- hCaptcha Token 有时效性，程序会在拿到结果后立即继续注册流程。
- 单账号注册失败时会按 `PEEZY_REGISTER_RETRIES` 重新尝试。
- 请遵守相关服务的使用条款和适用规则。

## License

MIT
