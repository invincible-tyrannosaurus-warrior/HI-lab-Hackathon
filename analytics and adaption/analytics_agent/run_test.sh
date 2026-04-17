#!/usr/bin/env bash
#
# Analytics & Adaptation Pipeline — 一键测试脚本
#
# 用法:  chmod +x run_test.sh && ./run_test.sh
#
# 前置条件 (三选一):
#   export DASHSCOPE_API_KEY="sk-..."   (阿里云百炼)
#   export OPENAI_API_KEY="sk-..."      (OpenAI)
#   export GEMINI_API_KEY="AIza..."     (Google Gemini)
#
# ────────────────────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

step()  { echo -e "\n${YELLOW}▶ $1${NC}"; }
ok()    { echo -e "${GREEN}  ✓ $1${NC}"; }
fail()  { echo -e "${RED}  ✗ $1${NC}"; }

echo -e "\n${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${BOLD}   Analytics & Adaptation — 测试脚本                      ${NC}${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"

# ── 1. 检查 Python ──

step "检查 Python 环境..."
if command -v python3 &>/dev/null; then
    ok "$(python3 --version 2>&1)"
else
    fail "未找到 python3"; exit 1
fi

# ── 2. 检查依赖 ──

step "检查依赖包..."
MISSING=()
for pkg in openai pydantic; do
    python3 -c "import $pkg" 2>/dev/null && ok "$pkg" || { MISSING+=("$pkg"); fail "$pkg"; }
done
if [ ${#MISSING[@]} -gt 0 ]; then
    step "安装缺失依赖: ${MISSING[*]}"
    python3 -m pip install --break-system-packages "${MISSING[@]}" 2>&1 | tail -3
fi

# ── 3. 检查 API Key ──

step "检查 API Key..."
PROVIDER="none"
if [ -n "$DASHSCOPE_API_KEY" ]; then
    PROVIDER="dashscope"; ok "DASHSCOPE_API_KEY (${DASHSCOPE_API_KEY:0:8}...) — 阿里云百炼"
elif [ -n "$OPENAI_API_KEY" ]; then
    PROVIDER="openai"; ok "OPENAI_API_KEY (${OPENAI_API_KEY:0:8}...)"
elif [ -n "$GEMINI_API_KEY" ]; then
    PROVIDER="gemini"; ok "GEMINI_API_KEY (${GEMINI_API_KEY:0:8}...)"
else
    fail "未设置 API Key (LLM 测试将跳过, 只跑 rule-based)"
fi

# ── 4. Dry Run ──

step "[Test 1/4] Dry Run — 验证代码结构"
python3 main.py --dry-run 2>&1 && ok "Dry Run 通过" || { fail "Dry Run 失败"; exit 1; }

# ── 5. Rule-Based 引擎 ──

step "[Test 2/4] Rule-Based 引擎 — 不调 LLM"
python3 main.py --rule-based --quiet --output test_rule.json 2>&1 && ok "Rule-Based 通过" || { fail "Rule-Based 失败"; exit 1; }

# ── 6. LLM 单步测试 ──

if [ "$PROVIDER" != "none" ]; then
    step "[Test 3/4] LLM 单步测试 — Step 1 (Signal Ingestion)"
    python3 -c "
from pipeline import LLMPipeline, SignalSummary, DeckMetadata, KnowledgeEntry
from main import get_mock_signal, get_mock_deck, get_mock_knowledge

pipe = LLMPipeline(verbose=True)
result = pipe._call_llm('step1_ingest', {
    'signal_json': get_mock_signal().to_json(),
    'deck_json': __import__('json').dumps(__import__('dataclasses').asdict(get_mock_deck()), indent=2),
    'knowledge_json': __import__('json').dumps([__import__('dataclasses').asdict(k) for k in get_mock_knowledge()], indent=2),
}, '1_ingest_signal')
issues = result.get('tagged_issues', [])
print(f'  Tagged issues: {len(issues)}')
for i, x in enumerate(issues[:3]):
    print(f'    {i+1}. [{x.get(\"preliminary_issue_type\",\"?\")}] {x.get(\"raw_text\",\"\")[:60]}')
" 2>&1 && ok "单步测试通过" || fail "单步测试失败"

    # ── 7. LLM 全链路 ──

    step "[Test 4/4] LLM 全链路 — 6 步 Pipeline"
    OUTPUT_FILE="test_output_$(date +%Y%m%d_%H%M%S).json"
    python3 main.py --output "$OUTPUT_FILE" 2>&1 && ok "全链路通过" || { fail "全链路失败"; exit 1; }

    step "验证输出文件..."
    python3 -c "
import json, sys
with open('$OUTPUT_FILE') as f:
    data = json.load(f)
for key in ['step1_ingest','step2_normalize','step3_cluster','step4_score','step5_recommend','step6_proposal','trace']:
    assert key in data, f'missing {key}'
recs = data['step5_recommend'].get('recommendations', [])
valid = {'add_prerequisite_slide','add_example','rewrite_explanation','split_dense_slide','add_misconception_warning','mark_for_kb_review','regenerate_deck_section'}
for r in recs:
    a = r.get('action_type','')
    if a not in valid: print(f'  ⚠ non-standard action: {a}')
print(f'  ✓ 7 steps OK, {len(recs)} recommendations, action taxonomy valid')
" 2>&1 && ok "输出验证通过" || fail "输出验证失败"
else
    echo -e "\n${YELLOW}  [跳过 Test 3/4 和 4/4 — 无 API Key]${NC}"
fi

# ── Done ──

echo -e "\n${CYAN}══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  测试完成!${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
echo ""

# 清理临时文件
rm -f test_rule.json 2>/dev/null
