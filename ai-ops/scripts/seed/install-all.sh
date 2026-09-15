#!/usr/bin/env bash
# scripts/seed/install-all.sh
# 一键把 ai-ops 扩展层安装到 Octop 用户级目录（shell 版，不依赖 GNU make）。
# 等价于 make install-all，方便 CI / 非 make 环境。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OCTOP_ROOT="${OCTOP_ROOT:-$HOME/.octop}"
OCTOP_PLUGINS="$OCTOP_ROOT/plugins"
OCTOP_EXPERTS="$OCTOP_ROOT/expert_market"

install_dirs() {
    local src_parent="$1" dst_parent="$2" kind="$3"
    mkdir -p "$dst_parent"
    for src in "$REPO_ROOT/$src_parent"/*/; do
        local id dst
        id="$(basename "$src")"
        dst="$dst_parent/$id"
        # 找到 marker 文件（插件 = plugin.yaml，专家 = manifest.json）
        if [ -f "$src/plugin.yaml" ] || [ -f "$src/manifest.json" ]; then
            echo "  [$kind] $id → $dst"
            rm -rf "$dst"
            cp -r "$src" "$dst"
        fi
    done
}

main() {
    echo "📦 plugins → $OCTOP_PLUGINS"
    install_dirs "plugins" "$OCTOP_PLUGINS" plugin
    echo "🧠 experts → $OCTOP_EXPERTS"
    install_dirs "experts" "$OCTOP_EXPERTS" expert
    echo "✅ 安装完成。启动 Octop 后自动发现。"
}

main "$@"
