# 插件开发指南

面向 harness-agent 插件协议 + Octop 插件发现机制的开发手册。

## 插件目录结构

```
plugins/<plugin-id>/
├── plugin.yaml       # 声明式元数据（必填）
├── main.py           # harness-agent 插件入口（必填，必须有 setup(ctx)）
└── ui/               # 可选：Dashboard UI 扩展
    ├── index.js
    └── manifest.json
```

## plugin.yaml 规范

```yaml
id: competitor-crawler        # 唯一标识，用 kebab-case
version: 0.1.0                # 语义化版本
name: 竞品情报爬虫              # 中文展示名
description: 爬取竞品价格...     # 一句话说明
icon: "🕷️"                     # 可选 emoji
kind: tool                    # 可选值：tool | ui | skill
entry: main.py                # Python 入口文件名
requires:                     # 可选：额外 Python 依赖
  - httpx>=0.27
  - beautifulsoup4>=4.12
```

## main.py 协议（必须有 setup(ctx)）

harness-agent 插件加载器（`harness_agent.plugins.loader.load_plugin_dir`）会：

1. 动态 import `entry` 指向的模块
2. 调用 `setup(ctx)`，其中 `ctx` 是 `harness_agent.plugins.PluginContext` 实例
3. `setup` 里必须通过 `ctx.tool()` 注册工具函数

### 最简模板

```python
from __future__ import annotations
from typing import Any
from harness_agent.plugins import PluginContext

async def my_tool(url: str, timeout: int = 15) -> dict[str, Any]:
    """工具函数，async 或 sync 都可以。"""
    return {"ok": True, "url": url, "timeout": timeout}

def setup(ctx: PluginContext) -> None:
    ctx.tool(
        "my_tool",
        my_tool,
        description=(
            "一句话描述 + 每个参数的类型/默认值/含义。"
            "Agent 会把 description 当作 tool docstring 放进 system prompt。"
        ),
    )
```

### PluginContext 提供什么

| 属性 | 类型 | 说明 |
|------|------|------|
| `ctx.browser` | BrowserSession? | harness-browser Chromium 会话（未启用时为 None） |
| `ctx.workspace` | BackendWorkspace | Agent 的 workspace 文件系统 |
| `ctx.config` | dict | Octop 全局配置片段 |
| `ctx.manifest` | PluginManifest | 当前插件的 plugin.yaml 解析结果 |

### 返回值建议

- **JSON 序列化友好**：dict / list / str / int / float / bool，不要返回 dataclass / Path / httpx.Response
- **错误走返回值，不是抛异常**：`{"ok": False, "error": "..."}` 比 `raise RuntimeError(...)` 对 Agent 更友好——Agent 可以在 ReAct 循环里重试或降级

## 安装与验证

```bash
cd /path/to/ai-ops
make verify                    # 语法检查（YAML + manifest）
make install-plugins           # 拷贝到 ~/.octop/plugins/<id>/

# 手动验证发现
cd /path/to/octop
uv run python -c "
from pathlib import Path
from octop.infra.agents.plugins.manager import PluginManager
pm = PluginManager(
    plugins_dir=Path.home() / '.octop' / 'plugins',
    config_path=Path.home() / '.octop' / 'config.json',
)
loaded = pm.load_installed(install_deps=False)
for p in loaded:
    print(f'✅ {p.manifest.id}: tools={[t.__name__ for t in p.tools]}')
"
```

## 常见踩坑

1. **忘记写 `setup(ctx)`**：harness-agent 加载器会直接抛 `AttributeError: plugin entry must define setup(ctx)`
2. **setup 函数签名不对**：必须是 `def setup(ctx: PluginContext) -> None:`，async 会被忽略
3. **工具函数名重复**：同一个 Agent 下注册的 tool 名必须唯一（harness-agent 会校验）
4. **返回不可序列化对象**：httpx.Response / Path / dataclass 直接塞进去会让 Agent 解析失败
5. **反爬太激进**：优先 http 模式，失败再降级 browser 模式；不要试图绕过验证码
