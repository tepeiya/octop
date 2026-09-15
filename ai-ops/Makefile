# AI 运营自动化中台 · 构建与安装
# 面向 Octop (https://github.com/TencentCloud/Octop) 的商业扩展层。
# 所有扩展通过拷贝安装到 Octop 用户级目录，零侵入核心代码。

# Octop 用户级根目录（默认 ~/.octop，可通过 OCTOP_ROOT 环境变量覆盖）
OCTOP_ROOT ?= $(HOME)/.octop
OCTOP_PLUGINS_DIR := $(OCTOP_ROOT)/plugins
OCTOP_EXPERT_DIR := $(OCTOP_ROOT)/expert_market

# 本仓库根（GNU make 内置变量，无需额外赋值）
ROOT := $(abspath $(CURDIR))

# 扩展发现：从 plugins/ 和 experts/ 子目录自动发现
PLUGIN_DIRS := $(sort $(wildcard $(ROOT)/plugins/*/))
EXPERT_DIRS := $(sort $(wildcard $(ROOT)/experts/*/))

.PHONY: help install-all install-plugins install-experts \
        clean-plugins clean-experts clean-all \
        list verify

help: ## 查看所有目标
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
                | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── 安装 ────────────────────────────────────────────────────────────────────

install-all: install-plugins install-experts ## 安装全部扩展

install-plugins: ## 拷贝 plugins/* → $(OCTOP_PLUGINS_DIR)/<id>/
	@mkdir -p $(OCTOP_PLUGINS_DIR)
	@for d in $(PLUGIN_DIRS); do \
                id=$$(basename $$d); \
                if [ -f "$$d/plugin.yaml" ]; then \
                        dst="$(OCTOP_PLUGINS_DIR)/$$id"; \
                        echo "  📦 plugin $$id → $$dst"; \
                        rm -rf "$$dst"; cp -r "$$d" "$$dst"; \
                fi; \
        done
	@echo "✓ plugins installed to $(OCTOP_PLUGINS_DIR)"

install-experts: ## 拷贝 experts/* → $(OCTOP_EXPERT_DIR)/<id>/
	@mkdir -p $(OCTOP_EXPERT_DIR)
	@for d in $(EXPERT_DIRS); do \
                id=$$(basename $$d); \
                if [ -f "$$d/manifest.json" ]; then \
                        dst="$(OCTOP_EXPERT_DIR)/$$id"; \
                        echo "  🧠 expert $$id → $$dst"; \
                        rm -rf "$$dst"; cp -r "$$d" "$$dst"; \
                fi; \
        done
	@echo "✓ experts installed to $(OCTOP_EXPERT_DIR)"

# ── 清理 ────────────────────────────────────────────────────────────────────

clean-plugins: ## 删除 $(OCTOP_PLUGINS_DIR) 下同名插件
	@for d in plugins/*/; do \
		id=$$(basename $$d); \
		if [ -d "$(OCTOP_PLUGINS_DIR)/$$id" ]; then \
			echo "  🗑️  remove plugin $$id"; \
			rm -rf "$(OCTOP_PLUGINS_DIR)/$$id"; \
		fi; \
	done

clean-experts: ## 删除 $(OCTOP_EXPERT_DIR) 下同名专家
	@for d in experts/*/; do \
		id=$$(basename $$d); \
		if [ -d "$(OCTOP_EXPERT_DIR)/$$id" ]; then \
			echo "  🗑️  remove expert $$id"; \
			rm -rf "$(OCTOP_EXPERT_DIR)/$$id"; \
		fi; \
	done

clean-all: clean-plugins clean-experts ## 清理全部

# ── 验证 ────────────────────────────────────────────────────────────────────

list: ## 列出仓库内的插件/专家清单
	@echo "plugins:"; find plugins -name plugin.yaml -exec echo "  {}" \;
	@echo "experts:"; find experts -name manifest.json -exec echo "  {}" \;

verify: ## 检查 manifest / plugin.yaml 语法有效性
	@echo "→ checking plugin.yaml files..."; \
        failed=0; \
        for f in $(PLUGIN_DIRS); do \
                if [ -f "$$f/plugin.yaml" ]; then \
                        uv run python -c "import yaml,sys; yaml.safe_load(open('$$f/plugin.yaml'))" 2>/dev/null \
                                && echo "  ✓ $$f/plugin.yaml" || { echo "  ✗ $$f/plugin.yaml"; failed=1; }; \
                fi; \
        done; \
        echo "→ checking manifest.json files..."; \
        for f in $(EXPERT_DIRS); do \
                if [ -f "$$f/manifest.json" ]; then \
                        uv run python -c "import json,sys; json.load(open('$$f/manifest.json'))" 2>/dev/null \
                                && echo "  ✓ $$f/manifest.json" || { echo "  ✗ $$f/manifest.json"; failed=1; }; \
                fi; \
        done; \
        exit $$failed
