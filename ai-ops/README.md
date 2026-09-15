# AI 运营自动化中台 · 扩展层

> 面向 [Octop](https://github.com/TencentCloud/Octop)（MIT）的商业扩展层。
> 提供竞品情报、舆情监控、电商自动化等运营场景的**插件 / 专家模板 / Connector**。

## 核心原则

- **独立仓库**：所有扩展层代码不进 Octop 核心仓库，通过 `make install-*` 拷贝进 `~/.octop/`
- **零侵入**：不修改 `src/octop/infra/` 任何文件，只走 harness-agent 插件协议和 Octop 专家目录发现机制
- **可热重载**：插件/专家拷进 Octop 后，启动 Octop 即被发现，无需重启 Python 进程

## 目录结构

```
ai-ops/
├── Makefile                    # install-* / verify / clean
├── pyproject.toml              # 仅声明依赖占位
├── plugins/                    # harness-agent 插件（每个子目录一个插件）
│   └── competitor-crawler/     # Phase 1 竞品爬虫 ✅
├── experts/                    # Octop 专家模板（每个子目录一个专家）
│   └── competitor-intel/      # Phase 1 竞品情报专家 ✅
├── scripts/
│   ├── seed/                   # 一键安装脚本
│   └── deploy/                 # Phase 3 私有化部署脚手架
├── docs/
│   └── plugin-development.md   # 插件开发指南
└── tests/
```

## 快速开始

```bash
# 1. 确认 Octop 已安装（本仓库是扩展层，不包含 Octop）
cd /path/to/octop && make all

# 2. 安装扩展层（拷贝到 ~/.octop/）
cd /path/to/ai-ops
make install-all

# 3. 语法验证
make verify

# 4. 启动 Octop，访问 Dashboard 创建"竞品情报专家" Agent
#    或者直接用 CLI：
octop agent create --expert competitor-intel --name "我的竞品情报员"
octop chat --agent "我的竞品情报员"
```

## 构建流程（每个 Octop release 后执行一次）

```bash
make clean-all          # 清理旧版本
make install-all        # 拷贝新版
# 然后启动 Octop，插件/专家会自动热重载
```

## License

本仓库代码以 MIT 发布，与 Octop 保持一致。
