#!/usr/bin/env bash
# scripts/deploy/deploy.sh
# 私有化部署脚手架（Phase 3）。
# 在客户服务器上一键拉起 Octop + PostgreSQL + Nginx + SSL，预装 ai-ops 扩展层。
#
# 用法：
#   ./deploy.sh --customer acme --domain aiops.acme.com --octop-version v0.8.0
#   可选参数：
#     --octop-version   默认 latest
#     --image            自定义 Octop Docker 镜像（默认 tencentcloud/octop）
#     --no-tls           跳过 Let's Encrypt（内网部署时用）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

OCTOP_VERSION="latest"
IMAGE="tencentcloud/octop"
CUSTOMER=""
DOMAIN=""
ENABLE_TLS=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --customer)      CUSTOMER="$2"; shift 2 ;;
        --domain)        DOMAIN="$2";   shift 2 ;;
        --octop-version) OCTOP_VERSION="$2"; shift 2 ;;
        --image)         IMAGE="$2";    shift 2 ;;
        --no-tls)        ENABLE_TLS=false; shift ;;
        -h|--help)       sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "unknown arg: $1"; exit 1 ;;
    esac
done

if [ -z "$CUSTOMER" ] || [ -z "$DOMAIN" ]; then
    echo "ERROR: --customer and --domain are required" >&2
    exit 1
fi

echo "═══════════════════════════════════════"
echo "AI 运营自动化中台 · 私有化部署"
echo "═══════════════════════════════════════"
echo "客户:    $CUSTOMER"
echo "域名:    $DOMAIN"
echo "Octop:   $IMAGE:$OCTOP_VERSION"
echo "TLS:     $([ "$ENABLE_TLS" = true ] && echo "启用 (Let's Encrypt)" || echo "跳过")"
echo ""
echo "🚧 此脚本是脚手架（Phase 3 实现），当前只打印参数。"
echo "   正式实现会：生成 docker-compose.yml、写入 .env、docker compose up -d、"
echo "   预装 ai-ops 扩展层、配置 systemd 守护进程、运行健康检查。"
echo ""
echo "下一步（手动）："
echo "  1. docker compose -f $SCRIPT_DIR/docker-compose.yml up -d"
echo "  2. bash $(cd "$SCRIPT_DIR/../seed" && pwd)/install-all.sh"
echo "  3. curl https://$DOMAIN/api/docs — 验证可访问"
