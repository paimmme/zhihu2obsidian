#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/paimmme/zhihu2obsidian.git"
NAME="创作者知识库 (Creator Knowledge Base)"

echo "============================================"
echo "  📚 $NAME"
echo "============================================"
echo ""

# Check Python
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "❌ 需要 Python 3.10+，未找到"
    echo "   安装: https://www.python.org/downloads/"
    exit 1
fi

# Check Python version using Python itself (macOS-safe, no grep -P or bc needed)
PY_VER_CHECK=$($PYTHON -c "
import sys
v = sys.version_info
if v.major < 3 or (v.major == 3 and v.minor < 10):
    sys.exit(1)
else:
    print(f'{v.major}.{v.minor}')
" 2>&1) || true
if [ -z "$PY_VER_CHECK" ]; then
    echo "❌ Python 版本过低: $($PYTHON --version) (需要 3.10+)"
    exit 1
fi
echo "✅ Python $($PYTHON --version)"

# Create directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Virtual env
if [ ! -d "cli/.venv" ]; then
    echo "🔧 创建虚拟环境..."
    $PYTHON -m venv cli/.venv
fi

echo "🔧 安装依赖..."
source cli/.venv/bin/activate
pip install -q --upgrade pip
pip install -e "cli/[all]"

echo ""
echo "============================================"
echo "  ✅ 安装完成"
echo "============================================"
echo ""
echo "激活虚拟环境后即可使用:"
echo "  source cli/.venv/bin/activate"
echo ""
echo "快速开始:"
echo "  1. zhihu2obsidian config init"
echo "  2. zhihu2obsidian config set vault ~/Documents/Obsidian"
echo "  3. zhihu2obsidian auth login"
echo "  4. zhihu2obsidian list"
echo "  5. zhihu2obsidian sync --limit 3"
echo "  6. zhihu2obsidian knowledge build"
echo "  7. streamlit run web/app.py"
echo ""
echo "详细文档: README.md"
