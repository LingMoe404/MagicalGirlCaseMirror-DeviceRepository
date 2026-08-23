# MagicalGirlCaseMirror Device Repository

MagicalGirlCaseMirror 的独立设备包仓库。

本仓库用于发布可由 Control Center 订阅和更新的声明式设备包、LED 模型、设备拓扑和其他受控资源。

## 当前状态

仓库已建立，设备包格式正在开发中。首批包将在 `.mgpack.json` schema 和签名发布流程确定后加入。

## 安全边界

- 设备包只声明设备、LED 模型、拓扑和已有 Host Driver 的引用。
- 不执行包内 JavaScript、HTML、WebAssembly、DLL 或 EXE。
- 新的 USB、HID、WinUSB 或其他设备协议必须在 MagicalGirlCaseMirror 主项目中实现并经过审查和实机验证。
- 不直接收录第三方软件、SDK、运行时、安装包或未经确认授权的资源。
- 每个外部来源包必须保留作者、来源、许可证和必要的再分发说明。

## 目录约定

```text
repository.json       # 仓库索引和版本信息
packages/              # .mgpack.json 设备包
models/                # 可复用的声明式 LED 模型
assets/                # 经授权且必要的静态预览资源
licenses/              # 包和资源的许可证说明
signatures/            # 仓库和包签名
```

## 签名发布

官方仓库使用 ECDSA P-256 / SHA-256。发布工作流从 GitHub Secret `OFFICIAL_REPOSITORY_SIGNING_KEY_PEM` 读取私钥，为每个 `.mgpack.json` 生成 Base64 DER 签名，再签名根目录 `repository.json` 为同目录的 `repository.json.sig`。私钥只在 Actions 临时目录存在，不提交到仓库，也不写入日志。

GitHub 是唯一权威编辑源。签名完成后，同一提交由镜像工作流同步到 AtomGit 和 Gitee；两个镜像不能独立编辑设备包。

三个官方订阅地址：

- GitHub：`https://raw.githubusercontent.com/LingMoe404/MagicalGirlCaseMirror-DeviceRepository/main/repository.json`
- AtomGit：`https://atomgit.com/LingMoe404/MagicalGirlCaseMirror-DeviceRepository/raw/branch/main/repository.json`
- Gitee：`https://gitee.com/LingMoe404/magical-girl-case-mirror-device-repository/raw/main/repository.json`

三端必须返回相同的 `repository.json`、`repository.json.sig` 和 `packages/` 文件；客户端仍以内置公钥验证签名，不因地址不同而建立不同信任根。

## 发布要求

设备包在发布前必须通过 schema 校验、引用校验、SHA-256 校验和签名流程。仓库索引是静态 HTTPS 资源；GitHub 仓库可以作为权威编辑源，后续同步到国内 CDN 或对象存储镜像。

本仓库不包含主项目源码。主项目位于：

<https://github.com/LingMoe404/MagicalGirlCaseMirror>
