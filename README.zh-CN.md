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

安装目标优先使用 `X64DBG_PATH` 指向的调试器目录，否则回退到常见的 x64dbg 安装位置。也可以用 `--dbg64-root` / `--dbg32-root` 显式指定。

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

## 调试器探测

封装层会按下面的顺序查找调试器：

1. 环境变量 `X64DBG_PATH`
2. 常见的标准 x64dbg 安装位置，包括：

- 本仓库旁边，或 `release\x64` / `release\x32` 目录下的 `x64dbg.exe`、`x96dbg.exe`、`x32dbg.exe`
- `%LOCALAPPDATA%\x64dbg\release\x64\x64dbg.exe` 以及对应的 x32 路径
- `C:\x64dbg\release\x64\x64dbg.exe` 以及其他常见的 `C:\x64dbg` 布局
- `C:\Program Files\x64dbg\x64dbg.exe` 和 `C:\Program Files (x86)\x64dbg\x32dbg.exe`

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

如果自定义调试器构建无法稳定加载目标程序，建议把 `X64DBG_PATH` 指向标准版 x64dbg。
