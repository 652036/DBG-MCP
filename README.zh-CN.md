# dbgmcp

[English](README.md) | [简体中文](README.zh-CN.md)

`dbgmcp` 是对官方 `x64dbg_automate` MCP 服务的一个轻量本地封装。

这个仓库的目标，是把 Windows 本地调试器 MCP 环境的搭建过程尽量做成一套可重复、可自检的流程：

- 自动探测常见的本地调试器安装位置
- 输出可直接粘贴使用的 MCP 配置片段
- 提供 `x64dbg_automate` 插件安装器
- 提供本地调试联通性 smoke test

## 这个仓库封装了什么

这个项目并没有重新实现调试桥协议本身。

它直接复用 `x64dbg_automate` 官方提供的 MCP 服务，并在外围补了一层本地环境初始化、路径探测、安装和自检工具。

本仓库依赖的上游参考：

- x64dbg-automate MCP 文档：`https://dariushoule.github.io/x64dbg-automate-pyclient/mcp-server/`
- x64dbg-automate 安装文档：`https://dariushoule.github.io/x64dbg-automate-pyclient/installation/`
- PyPI 包：`https://pypi.org/project/x64dbg-automate/`

## 安装

```powershell
python -m pip install -e .
```

依赖条件：

- Windows
- Python 3.10+
- `x64dbg_automate[mcp]==0.7.6`

## 本地命令

### 环境自检

```powershell
python -m dbgmcp doctor
```

这个命令会检查：

- Python 版本
- `x64dbg_automate` 是否已安装
- 当前探测到的调试器可执行文件路径
- 调试器插件目录
- 插件运行时必需文件是否齐全
- 通过 x64dbg-automate lockfile 发现的活动会话数量

### 打印 MCP 配置

```powershell
python -m dbgmcp print-mcp-config
```

它会输出一段 MCP 配置，默认包含：

- `command = python`
- `args = ["-m", "dbgmcp", "mcp"]`
- `env.X64DBG_PATH = 自动探测到的调试器路径`

### 启动 MCP 服务

```powershell
python -m dbgmcp mcp
```

等价入口：

```powershell
dbgmcp-server
```

### 安装 x64dbg-automate 插件

```powershell
python -m dbgmcp install-plugin
```

这个命令会下载与你当前 Python 客户端兼容版本匹配的已发布插件，并把 release 文件复制到调试器的 `plugins` 目录中。

### Smoke test

```powershell
python -m dbgmcp smoke-test
```

默认情况下，它会启动 `C:\Windows\System32\notepad.exe`，验证调试器会话能否被 x64dbg-automate 发现，并进一步读取当前指令指针。

如果你想指定其他目标程序：

```powershell
python -m dbgmcp smoke-test --target C:\path\to\target.exe
```

如果你只想验证调试器和插件本身能否正常启动，而不加载任何目标：

```powershell
python -m dbgmcp smoke-test --no-target
```

也可以通过环境变量指定目标：

```powershell
$env:DBGMCP_SMOKE_TARGET = 'C:\path\to\target.exe'
python -m dbgmcp smoke-test --target $env:DBGMCP_SMOKE_TARGET
```

## 这台机器上的默认行为

在这台机器上，封装层会优先尝试以下调试器位置：

- `C:\Users\Administrator\Desktop\vtce\KittyDebugTool\DBG\DBG64\` 目录下的可执行文件
- 常见的 `x64dbg.exe`、`x32dbg.exe`、`x96dbg.exe` 默认路径

如果你的调试器不在这些位置，请手动设置：

```powershell
$env:X64DBG_PATH = 'C:\path\to\your\debugger.exe'
```

## MCP 配置示例

可参考：

- `.mcp.json.example`
- `mcp.config.example.json`

## 外部前置条件

这个封装层无法自动替你完成以下外部步骤：

- 把 x64dbg-automate 调试器插件安装进实际使用的调试器 `plugins` 目录
- 启动一个真正包含该插件的调试器构建
- 连接到一个可用的调试目标

如果这些条件没有满足，MCP 进程本身仍然可以启动，但像 `start_session`、`connect_to_session` 这类工具就不会真正可用。

在这台工作机上，`DBG64` 目录下的自定义调试器构建可以正常拉起空会话；但是否能稳定加载目标程序，还取决于这个构建本身的行为。如果目标加载卡住，建议把 `X64DBG_PATH` 指向标准版 x64dbg。
