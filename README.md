# MagicalGirlCaseMirror Device Repository

MagicalGirlCaseMirror 的独立 RGB 资源仓库。

本仓库用于发布可由 Control Center 订阅和更新的三类声明式资源：设备 Profile、RGB LED 模型和统一 Canvas。资源使用独立的 `.mgdevice.json`、`.mgmodel.json` 和 `.mgcanvas.json` 文件，索引只包含 `resources[]`。

## 当前状态

首批资源已经加入索引并通过结构、路径、哈希和 Host 契约测试。索引和资源文件保留受保护发布流程生成的真实签名；签名工作流会在正式发布时使用官方密钥重新签署变更后的索引和资源。

资源目录：

- `devices/`：已验证的 Vmax 320x960 和 MythCool 480x480 设备声明；
- `models/`：自研 RGB LED 坐标和索引映射；
- `canvases/`：独立的 `solid`、`rainbow`、`breathing`、`wave` 和 `rainbow-rise` 声明式画布。

新增声明式画布只需发布新的 `.mgcanvas.json` 资源和索引条目，无需更新软件。若新增 Host 尚未知的 effect kind，仍必须先更新软件并由 Host 实现和验证。

## 安全边界

- 设备资源只声明设备、LED 模型、拓扑和已有 Host Driver 的引用。
- 不执行包内 JavaScript、HTML、WebAssembly、DLL 或 EXE。
- 新的 USB、HID、WinUSB 或其他设备协议必须在 MagicalGirlCaseMirror 主项目中实现并经过审查和实机验证。
- 不直接收录第三方软件、SDK、运行时、安装包或未经确认授权的资源。
- 每个外部来源包必须保留作者、来源、许可证和必要的再分发说明。

## 目录约定

```text
repository.json        # 仓库索引和版本信息
devices/               # .mgdevice.json 设备 Profile
models/                # .mgmodel.json RGB LED 模型
canvases/              # .mgcanvas.json 统一 Canvas
licenses/              # 资源的许可证说明
repository.json.sig    # 正式发布时生成，当前开发提交不包含
```

## 签名发布

官方仓库使用 ECDSA P-256 / SHA-256。发布工作流从 GitHub Secret `OFFICIAL_REPOSITORY_SIGNING_KEY_PEM` 读取私钥，为每个 `.mgdevice.json`、`.mgmodel.json` 和 `.mgcanvas.json` payload 生成 Base64 DER 签名，再签名根目录 `repository.json` 为同目录的 `repository.json.sig`。私钥只在 Actions 临时目录存在，不提交到仓库，也不写入日志。`scripts/sign_repository.py --verify-release --public-key <公钥>` 会拒绝占位签名、缺失根签名、哈希不匹配、非资源路径和无法验证的 payload。

GitHub 是唯一权威编辑源。签名完成后，同一提交由镜像工作流同步到 Gitee；镜像不能独立编辑资源。

两端官方订阅地址：

- GitHub：`https://raw.githubusercontent.com/LingMoe404/MagicalGirlCaseMirror-DeviceRepository/main/repository.json`
- Gitee：`https://gitee.com/LingMoe404/magical-girl-case-mirror-device-repository/raw/main/repository.json`

正式发布时两端同目录提供 `repository.json.sig` 以及索引引用的 `devices/`、`models/` 和 `canvases/` 文件。GitHub 是权威源，Gitee 只做相同提交的镜像；客户端以内置公钥验证签名，不因地址不同而建立不同信任根。当前开发提交使用远端现有签名文件作为合并过渡，推送后的受保护发布工作流会重新签署最终索引和全部资源。

## 发布要求

资源在发布前必须通过 schema 校验、引用校验、路径安全校验、SHA-256 校验和签名流程。仓库索引是静态 HTTPS 资源；GitHub 仓库可以作为权威编辑源，后续同步到国内 CDN 或对象存储镜像，但镜像必须返回相同的已签名文件。

本仓库不包含主项目源码。主项目位于：

<https://github.com/LingMoe404/MagicalGirlCaseMirror>
