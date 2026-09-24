# AGENTS.md — MagicalGirlCaseMirror-DeviceRepository

## 本仓库的用途

官方设备资源仓库（签名索引）。只发布声明式资源：设备 Profile、RGB 模型与 Canvas。
消费端是主仓库 `MagicalGirlCaseMirror` 的 DisplayHost，用**内置公钥**验证签名，
不因地址不同而建立不同信任根。

主项目：`https://github.com/LingMoe404/MagicalGirlCaseMirror`

## 目录约定

- `devices/`：`*.mgdevice.json` 设备 Profile。
- `models/`：`*.mgmodel.json` RGB LED 模型。
- `canvases/`：`*.mgcanvas.json` 声明式 Canvas。
- `licenses/CONTENT-POLICY.md`：内容政策（资源可含与禁含的内容）。
- `scripts/sign_repository.py`：签名与校验工具。
- `tests/`：结构、路径安全、哈希、Host 契约与签名幂等性测试。
- `repository.json` + `repository.json.sig`：资源索引与其 ECDSA P-256 签名。

**没有** `packages/` 目录，索引也**不得**出现 `packages` 键——签名脚本会直接拒绝。

## 签名边界（重要）

- `repository.json` 与 `repository.json.sig` 及三个资源目录的哈希与签名**绝不手工编辑**。
  手工改动任一字节都会使签名失效，且本仓库**没有**私钥，无法本地重签。
- 私钥存放在 GitHub Actions secret `OFFICIAL_REPOSITORY_SIGNING_KEY_PEM`，只在
  `publish.yml` 中以 `umask 077` 写入 `$RUNNER_TEMP` 并在退出时擦除。**不得**把私钥
  或其副本放进仓库、issue、日志或提交信息。
- push 到 `main` 会触发 `publish.yml` 重新签名并推送。因此对 `main` 的普通文档提交
  也会让签名工作流真实运行一次；签名是幂等的（测试已断言重签后字节相同），但改动
  `main` 前要知道这一点。
- `repository.json.sig` 是 Base64 文本；`.gitattributes` 声明为 `-text`，避免 CRLF
  重写产生与 blob 不同的字节。

## 契约与内容边界

- 索引根：`schemaVersion`（必须为 `1`）、`repositoryId`（必须为 `official`）、
  `name`、`publisher`、`resources[]`。
- 条目字段：`resourceId`、`resourceType`（`device` | `rgb-model` | `canvas`）、`version`、
  `downloadUrl`（仓库内相对路径；扁平单层目录；类型与目录/后缀必须匹配）、
  `sha256`（64 位小写十六进制）、`minHostVersion`、`signature`（Base64 DER）。
- 资源内容**不得**包含 HTML、JavaScript、WebAssembly、脚本、协议字段、设备路径、
  厂商模板、第三方素材、二进制、SDK、安装包或私有诊断数据。
- 新的 USB/HID/WinUSB 协议必须在主仓库实现、审查并实机验证，不得写进资源。
- 不收录第三方软件或未经授权的素材；SignalRGB / WhirlwindFX 内容不得复制进来。
- GitHub 是唯一权威编辑源；Gitee 是镜像，**不得**在镜像上独立编辑资源。

## 验证

```bash
python -m unittest discover -s tests -v
python scripts/sign_repository.py --verify-release --public-key <公钥文件>
```

`--verify-release` 会校验：索引存在、无 `packages` 键、无占位签名、`.sig` 存在且为
合法 Base64、仓库签名有效、`schemaVersion` 为 1、以及每个条目的路径安全、SHA-256
与签名。本地没有内置公钥文件，需自备。

**已知缺口（不要假装已覆盖）**：两个 workflow（`publish.yml`、`mirror.yml`）都**不运行**
测试套件；`--verify-release` 是唯一被 README 记载的入口。测试目前只能在本地运行。

## Code Review Rules

- 改动资源后必须同时重算 SHA-256 并重签；不手工改 `repository.json` 或 `.sig`。
- 新增资源必须有作者、来源、许可证与必要的再分发说明。
- 提交前运行 `python -m unittest discover -s tests -v` 与 `git diff --check`。
- 不得把 `staging/`、`.local/`、`private/`、`*.key`、`*.pem` 纳入提交。
