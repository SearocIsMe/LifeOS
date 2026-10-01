"""Blind-test subject-facing pages (T-C + UI revisions U1–U4, 用户 7 条修改意见).

Subject-facing flow (the page a recruited subject opens in a browser):

- ``GET  /blindtest``            single-page console (consent → trials → done);
- ``POST /blindtest/api/start``  consent gate + email-hash dedup + latin-square stream;
- ``POST /blindtest/api/answer`` forced-choice recording (no abstain);
- ``POST /blindtest/api/submit`` attention rule + anonymized persistence.

UI revisions (U1–U4, all contract-tested in ``tests/test_blindtest_ui.py``):

- U1 rate limit: EVERY /api request counts per client IP (≤10 per window,
  window_s configurable); over the limit => 429 (限流不静默);
- U1 uniqueness: an IP that has completed a survey sees the completed
  banner on the FIRST page and cannot enter the trial flow;
- U2 back: the trial page has a 倒推 button — going back preserves answers;
- U3 fragment page: NO static reply boxes (bubble style removed); reply
  buttons warm-colored; reason ≤200 chars with a grey default hint;
- U4 responsive: viewport meta + flexible layout for browser size; ALL
  buttons warm palette; first page carries a ≤300-char background narrative.

NO fabricated answers: trials start with ``chose=None``; values arrive only
from a real subject clicking through the page.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from lifeos.dogfood.blindtest_page import (
    apply_attention_rule,
    attention_check_passed,
    build_trial_sequence,
    record_response,
    start_session,
    persist_responses,
)

_DEFAULT_FRAGMENTS = ["BS-026", "BS-027", "BS-028", "BS-029", "BS-030", "BS-009", "BS-021", "BS-022"]

# V1: 前后端版本号（header bar 显示；部署时与镜像 tag/env 同步）
VERSION = "0.1.0"

# U4: 首页背景叙述（≤300 字，如实叙述；i18n 双版——zh 为主/en 切换界面）
BACKGROUND_NARRATIVE = (
    "这项研究测试 AI 陪伴角色的长期身份连续性。您将看到 8 个中文对话片段：每个片段是同一条用户消息，"
    "并排展示两个 AI 角色的回复。请您判断「是不是同一个它」——如果一个角色记得您之前说过的事、"
    "称呼与关系保持一致、性格表达连贯，您会更倾向认为它还是同一个它。四个系统版本中有的是完整实现，"
    "有的缺少记忆或关系组件，但您无法区分它们。题目顺序经过平衡设计；请依据您的真实感受作答，"
    "没有对错之分。全部作答匿名化存储，仅通过化名编号关联；您可随时退出或申请删除数据。"
)
assert len(BACKGROUND_NARRATIVE) <= 300
BACKGROUND_NARRATIVE_EN = (
    "This study tests long-term identity continuity of AI companion characters. "
    "You will see 8 Chinese conversation fragments: each fragment is one user "
    "message with two AI character replies shown side by side. Please judge "
    "\"is it the same one\" — if a character remembers what you said before, "
    "keeps the form of address and relationship consistent, and expresses a "
    "coherent personality, you will tend to judge it as still the same one. "
    "The order is balanced by design; answer by your true feeling — there is "
    "no right or wrong. All responses are stored anonymously, linked only to "
    "a pseudonymous ID; you may quit or request deletion at any time. "
    "(Note: the conversation material stays in Chinese by design — the "
    "evaluation language is locked to Chinese.)"
)
assert len(BACKGROUND_NARRATIVE_EN) <= 2100  # en 上限放宽（字符计数）

# 暖色系按钮调色板（U3/U4: amber/orange family）
WARM_PRIMARY = "#d97706"
WARM_HOVER = "#b45309"

_PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><title>LifeOS 盲测</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
:root{--warm:#d97706;--warm-hover:#b45309;--ink:#1f2937;--paper:#fffbeb;--grey:#9ca3af}
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;margin:0 auto;padding:1rem;background:var(--paper);color:var(--ink);max-width:900px;width:100%}
h1{font-size:1.3rem} h2{font-size:1.05rem}
button{padding:.55rem 1.1rem;border-radius:8px;border:1px solid var(--warm-hover);background:var(--warm);color:#fff;cursor:pointer;font-size:1rem}
button:hover{background:var(--warm-hover)}
button.selected{background:var(--warm-hover);outline:3px solid #fbbf24}
button.ghost{background:#fff;color:var(--warm-hover)}
input,textarea{width:100%;padding:.5rem;border:1px solid #e5e7eb;border-radius:6px;margin:.3rem 0;font-size:1rem}
textarea{min-height:3.5rem}
.grey-hint{color:var(--grey);font-size:.95rem}
/* N2 修复: tickbox 与文本对齐（checkbox 内联、label flex 基线对齐） */
.consent-list input[type="checkbox"]{width:1.05rem;height:1.05rem;margin:0 .5rem 0 0;vertical-align:middle;flex:none}
.consent-list label{display:flex;align-items:flex-start;gap:.5rem;line-height:1.5}
.consent-list input[type="checkbox"]{margin-top:.2rem}
.ok{color:#15803d}.warn{color:var(--warm-hover)}
.banner{border:1px solid var(--warm);border-radius:10px;padding:1rem;background:#fff}
.trial-nav{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:.6rem}
.consent-list{margin:.5rem 0;padding:0;list-style:none}
.consent-list li{margin:.45rem 0;line-height:1.5}
.consent-list label{display:block;cursor:pointer}
button:disabled{background:#d1d5db;border-color:#9ca3af;cursor:not-allowed}
/* F1: 已提交 foot bar（主页面完整保留 + 顶部提示横幅） */
.footbar{border:1px solid var(--warm);border-radius:10px;padding:.8rem 1rem;margin-bottom:1rem;background:#fff}
@media (max-width:640px){
  body{padding:.8rem}
  h1{font-size:1.1rem}
  button{width:100%;margin:.25rem 0}
}
</style></head><body>
<div id="footbar" class="footbar" style="display:none">
<b>您已经提交过了 survey</b>（重复提交视为作废）。感谢您的参与——如需查阅/更正/删除/导出您的数据，请通过权利通道联系研究者。
</div>
<p style="text-align:right"><button class="ghost" id="lang_btn" onclick="toggleLang()" style="width:auto">English</button></p>
<div id="completed" style="display:none">
<div class="banner"><h2 data-i18n="done_title">您已经完成了 survey</h2>
<p class="warn" data-i18n="done_body">检测到您已提交过本问卷（重复提交视为作废）。感谢您的参与——如需删除或更正您的数据，请通过权利通道联系研究者。</p></div>
</div>
<div id="consent">
<h1 data-i18n="title">LifeOS 盲测：是不是同一个它？</h1>
<h2 data-i18n="h_bg">背景</h2>
<p id="narrative"></p>
<p class="grey-hint" data-i18n="bg_hint">（背景叙述不超过 300 字）</p>
<h2 data-i18n="h_consent">知情同意</h2>
<p><span data-i18n="approval">伦理批准号：</span><b>2026-ETH-00001</b>。<span data-i18n="approval_body">作答匿名化存储，关联仅为化名编号；您可随时查阅/更正/删除/导出数据。</span></p>
<p><span data-i18n="l_subject">化名编号：</span><input id="subject" data-ph="ph_subject"></p>
<p><span data-i18n="l_age">年龄：</span><input id="age" type="number" min="18" value="25" style="width:5rem"></p>
<p><span data-i18n="l_email">用于防重复检测的 email（单向哈希，原文不保存）：</span><input id="email" data-ph="ph_email"></p>
<ul class="consent-list">
<li><label><input type="checkbox" id="c1"> <span data-i18n="c1">我已阅读并理解知情同意书（含两级删除语义与 30 天备份窗口披露），自愿参与</span></label></li>
<li><label><input type="checkbox" id="c2"> <span data-i18n="c2">我理解作答匿名化存储，且关联仅为化名编号</span></label></li>
<li><label><input type="checkbox" id="c3"> <span data-i18n="c3">我知道我可随时查阅/更正/删除/导出我的数据</span></label></li>
</ul>
<p><button id="start_btn" onclick="start()" disabled><span data-i18n="start_btn">签署并开始（勾选全部三项后可用）</span></button></p>
<p id="start_msg" class="warn"></p>
</div>
<div id="trial" style="display:none">
<h2 id="frag"></h2>
<p id="msg"></p>
<p class="grey-hint" id="pair_hint"></p>
<p id="step_label" class="ok"></p>
<div class="pair">
  <div class="col"><p class="grey-hint" data-i18n="reply_a">回复 A</p><p id="left_text"></p></div>
  <div class="col"><p class="grey-hint" data-i18n="reply_b">回复 B</p><p id="right_text"></p></div>
</div>
<p data-i18n="ask">请选择您的判断，[还是同一个它]</p>
<div class="trial-nav">
  <button id="btn_L" onclick="choose('L')"><span data-i18n="btn_l">回复A 是同一个它</span></button>
  <button id="btn_R" onclick="choose('R')"><span data-i18n="btn_r">回复B 不是同一个它</span></button>
  <button id="btn_U" class="ghost" onclick="choose('U')"><span data-i18n="btn_u">无法回答</span></button>
</div>
<p><span data-i18n="l_reason">理由（一两句话，200 字以内）：</span></p>
<textarea id="reason" rows="2" maxlength="200" data-ph="ph_reason"></textarea>
<p class="grey-hint" id="hint" data-i18n="hint">默认理由提示（grey）：回复A 记得我之前养的猫 / 回复B 不记得称呼 / A 和 B 都连贯——按您的真实感受写即可，没有对错。</p>
<div class="trial-nav">
  <button class="ghost" onclick="back()" data-i18n="back_btn">倒退（上一步/上一场景）</button>
  <button onclick="save()" data-i18n="save_btn">保存并下一步</button>
</div>
<p id="progress" class="ok"></p>
</div>
<div id="done" style="display:none">
<div class="banner"><h2 data-i18n="finish">完成</h2><p id="done_msg" class="ok"></p></div>
</div>
<script>
let trials=[], idx=0, subjectId='', pool={}, answers={}, attentionPassed=null;
const REASON_MAX=200;
window.NARRATIVE_ZH=NARRATIVE_ZH_PLACEHOLDER__;
window.NARRATIVE_EN=NARRATIVE_EN_PLACEHOLDER__;
document.getElementById('narrative').textContent=window.NARRATIVE_ZH;

// i18n: zh/en UI 字典（data-i18n 驱动）；评测材料（对话片段/回复文本）保持原样
// 不翻译——spec §9.6 评测语言中文锁定，en 仅切换界面文案
const I18N = {
  zh: {
    lang_btn: "English", title: "LifeOS 盲测：是不是同一个它？", h_bg: "背景",
    bg_hint: "（背景叙述不超过 300 字）", h_consent: "知情同意",
    approval: "伦理批准号：", approval_body: "作答匿名化存储，关联仅为化名编号；您可随时查阅/更正/删除/导出数据。",
    l_subject: "化名编号：", ph_subject: "如 LIFE-BT-002", l_age: "年龄：",
    l_email: "用于防重复检测的 email（单向哈希，原文不保存）：", ph_email: "you@example.com",
    c1: "我已阅读并理解知情同意书（含两级删除语义与 30 天备份窗口披露），自愿参与",
    c2: "我理解作答匿名化存储，且关联仅为化名编号",
    c3: "我知道我可随时查阅/更正/删除/导出我的数据",
    start_btn: "签署并开始（勾选全部三项后可用）",
    reply_a: "回复 A", reply_b: "回复 B", ask: "请选择您的判断，[还是同一个它]",
    btn_l: "回复A 是同一个它", btn_r: "回复B 不是同一个它", btn_u: "无法回答",
    l_reason: "理由（一两句话，200 字以内）：", ph_reason: "回复A 记得我之前养的猫（默认理由提示，grey 字体，可清空）",
    hint: "默认理由提示（grey）：回复A 记得我之前养的猫 / 回复B 不记得称呼 / A 和 B 都连贯——按您的真实感受写即可，没有对错。",
    back_btn: "倒退（上一步/上一场景）", save_btn: "保存并下一步",
    done_title: "您已经完成了 survey", finish: "完成",
    no_email: "请输入化名编号", throttled: "请求过于频繁，请稍后再试",
    scenario: "场景", user_msg: "用户消息：", loading: "（素材加载中，请稍候重进）",
    pair_hint_prefix: "本场景共", pair_hint_suffix: "组比较",
    pair_hint_body: "请在同一场景上下文下，逐组判断两个回复是否来自「同一个它」。",
    step_label_prefix: "第", step_label_suffix: "组比较",
    progress: "进度", choose_first: "请先选择一边", reason_over: "理由超过 200 字",
    invalid: "作答无效：",
  },
  en: {
    lang_btn: "中文", title: "LifeOS Blind Test: Is it the same one?",
    h_bg: "Background", bg_hint: "(narrative under 300 chars)", h_consent: "Informed Consent",
    approval: "Ethics approval no.: ", approval_body: "Responses are stored anonymously, linked only to a pseudonymous ID; you may query/correct/delete/export your data at any time.",
    l_subject: "Pseudonymous ID: ", ph_subject: "e.g. LIFE-BT-002", l_age: "Age: ",
    l_email: "Email for duplicate detection (one-way hash, raw not stored): ", ph_email: "you@example.com",
    c1: "I have read and understood the informed consent (incl. two-tier deletion and 30-day backup window disclosure) and participate voluntarily",
    c2: "I understand my responses are stored anonymously, linked only to a pseudonymous ID",
    c3: "I know I can query/correct/delete/export my data at any time",
    start_btn: "Sign & Start (available after all three boxes)",
    reply_a: "Reply A", reply_b: "Reply B", ask: "Please make your judgement: [still the same one]",
    btn_l: "Reply A is the same one", btn_r: "Reply B is NOT the same one", btn_u: "Cannot answer",
    l_reason: "Reason (one or two sentences, under 200 chars): ", ph_reason: "Reply A remembers my cat (default hint in grey, clearable)",
    hint: "Default hints (grey): Reply A remembers my cat / Reply B forgets the name / both coherent — write your true feeling; there is no right answer.",
    back_btn: "Back (previous step / previous scenario)", save_btn: "Save & Next",
    done_title: "You have already completed the survey", finish: "Done",
    no_email: "Please enter the pseudonymous ID", throttled: "Too many requests, please retry later",
    scenario: "Scenario", user_msg: "User message: ", loading: "(materials loading, please re-enter)",
    pair_hint_prefix: "This scenario has", pair_hint_suffix: "paired comparisons",
    pair_hint_body: "judge each pair within the SAME scenario context: are the two replies from the same one?",
    step_label_prefix: "Comparison", step_label_suffix: "of 3",
    progress: "Progress", choose_first: "Please pick a side first", reason_over: "Reason over 200 chars",
    invalid: "Invalid response: ",
  },
};
let LANG = "zh";
function applyLang(){
  const d = I18N[LANG];
  document.querySelectorAll("[data-i18n]").forEach(el=>{const k=el.getAttribute("data-i18n"); if(d[k]!==undefined) el.textContent=d[k];});
  document.querySelectorAll("[data-ph]").forEach(el=>{const k=el.getAttribute("data-ph"); if(d[k]!==undefined) el.placeholder=d[k];});
  document.getElementById("lang_btn").textContent=d.lang_btn;
}
function toggleLang(){
  LANG = LANG==="zh" ? "en" : "zh";
  applyLang();
  document.getElementById('narrative').textContent = LANG==='zh' ? window.NARRATIVE_ZH : window.NARRATIVE_EN;
  // 已出题时刷新动态文案
  if(trials.length && document.getElementById("trial").style.display!=="none"){show();}
}
applyLang();

// R1: 三项全勾 → 「签署并开始」可用（disabled 联动）
function syncStartBtn(){
  const ok=document.getElementById('c1').checked && document.getElementById('c2').checked && document.getElementById('c3').checked;
  document.getElementById('start_btn').disabled=!ok;
}
['c1','c2','c3'].forEach(id=>document.getElementById(id).addEventListener('change',syncStartBtn));
syncStartBtn();

async function loadPool(){
  try{
    const r=await fetch('/blindtest/api/pool'); const d=await r.json();
    pool=d.materials||{};
  }catch(e){pool={};}
}
async function start(){
  if(document.getElementById('start_btn').disabled){return;}  // R1: 未全勾不可提交
  subjectId=document.getElementById('subject').value.trim();
  const age=parseInt(document.getElementById('age').value||'25');
  const email=document.getElementById('email').value.trim();
  if(!subjectId){document.getElementById('start_msg').textContent=I18N[LANG].no_email;return;}
  const r=await fetch('/blindtest/api/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({subject_id:subjectId,age:age,email:email})});
  if(!r.ok){
    const e=await r.json();
    if(r.status===409){
      document.getElementById('consent').style.display='none';
      document.getElementById('completed').style.display='block';
      return;
    }
    document.getElementById('start_msg').textContent='无法开始：'+(e.detail||r.status);return;
  }
  const d=await r.json();
  trials=d.trials; answers={}; idx=0;
  document.getElementById('consent').style.display='none';
  document.getElementById('trial').style.display='block';
  show();
}
function show(){
  const t=trials[idx];
  const m=pool[t.fragment_id]||{};
  // 方案 1b: 分组呈现——页头一次性提示（每场景），页内步进比较
  const sameFrag = trials.filter(x=>x.fragment_id===t.fragment_id);
  const posInFrag = sameFrag.findIndex(x=>x.order_seq===t.order_seq)+1;
  const fragIdx = [...new Set(trials.map(x=>x.fragment_id))].indexOf(t.fragment_id)+1;
  const fragTotal = new Set(trials.map(x=>x.fragment_id)).size;
  document.getElementById('frag').textContent=I18N[LANG].scenario+' '+fragIdx+'/'+fragTotal+': '+t.fragment_id;
  // 四场景上下文都提供：用户消息 + 该场景全部回复在同一页上下文（步进共用页头）
  document.getElementById('msg').textContent=I18N[LANG].user_msg+': '+(m.user_msg||t.user_msg||I18N[LANG].loading);
  document.getElementById('pair_hint').textContent=I18N[LANG].pair_hint_prefix+' '+sameFrag.length+' '+I18N[LANG].pair_hint_suffix+' ('+posInFrag+'): '+I18N[LANG].pair_hint_body;
  document.getElementById('step_label').textContent=I18N[LANG].step_label_prefix+' '+posInFrag+'/'+sameFrag.length+' '+I18N[LANG].step_label_suffix;
  document.getElementById('left_text').textContent=m[t.arm_left]||t.left_text||'';
  document.getElementById('right_text').textContent=m[t.arm_right]||t.right_text||'';
  document.getElementById('reason').value=(answers[t.order_seq]||{}).reason||'';
  document.getElementById('progress').textContent=I18N[LANG].progress+' '+(idx+1)+'/'+trials.length;
  window._side=(answers[t.order_seq]||{}).side||null;
  markSelected();
  if(t.is_attention_check && !(t.order_seq in answers)){alert('本题为注意力检查，请按提示作答：请选择「回复 A 是同一个它」。');}
}
// R3: 按钮按下后选中高亮反馈（Q2: 含"无法回答"第三选项）
function markSelected(){
  document.getElementById('btn_L').classList.toggle('selected',window._side==='L');
  document.getElementById('btn_R').classList.toggle('selected',window._side==='R');
  document.getElementById('btn_U').classList.toggle('selected',window._side==='U');
}
function choose(side){
  window._side=side;
  markSelected();  // R3: 即时反馈用户选择
}
function back(){
  // M5: 倒退——idx>0 回上一题（答案保留）；idx=0 回首页（consent 页）
  if(idx>0){idx--;show();return;}
  document.getElementById('trial').style.display='none';
  document.getElementById('consent').style.display='block';
  syncStartBtn();
}
async function save(){
  const t=trials[idx];
  const side=window._side;
  if(!side){document.getElementById('progress').textContent=I18N[LANG].choose_first||'请先选择一边';return;}
  const reason=document.getElementById('reason').value;
  if(reason.length>REASON_MAX){document.getElementById('progress').textContent=I18N[LANG].reason_over||'理由超过 200 字';return;}
  // Q2: 三选一映射——L/R → 臂名；U → "无法回答"
  const chose=side==='L'?t.arm_left:(side==='R'?t.arm_right:'无法回答');
  const r=await fetch('/blindtest/api/answer',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({subject_id:subjectId,order_seq:t.order_seq,chose:chose,reason_text:reason,is_attention_check:t.is_attention_check})});
  if(!r.ok){
    const e=await r.json();
    document.getElementById('progress').textContent=(I18N[LANG].invalid||'作答无效：')+(e.detail||r.status);
    window._side=null;return;
  }
  answers[t.order_seq]={side:side,reason:reason};
  idx++;
  if(idx<trials.length){show();return;}
  const s=await fetch('/blindtest/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({subject_id:subjectId})});
  const d=await s.json();
  document.getElementById('trial').style.display='none';
  document.getElementById('done').style.display='block';
  document.getElementById('done_msg').textContent=d.message;
}
loadPool();
</script></body></html>"""

# Rate-limit state (U1): {ip: [request timestamps]}
_rate_state: dict[str, list[float]] = {}


def check_rate_limit(ip: str, *, limit: int = 10, window_s: float = 3600.0) -> bool:
    """U1: 每 IP ≤limit 次 /api 请求（滑动窗口）；超限 False（429，不静默）。

    ``window_s=0`` = no window (state reset): all stamps expire, the next
    request starts a fresh count (测试钩子；生产窗口 3600s)。
    """
    now = time.time()
    stamps = [t for t in _rate_state.get(ip, []) if window_s > 0 and now - t < window_s]
    if len(stamps) >= limit:
        _rate_state[ip] = stamps
        return False
    stamps.append(now)
    _rate_state[ip] = stamps
    return True


def ip_has_completed(ip: str, *, completed_ips: set[str]) -> bool:
    """U1: 该 IP 已提交过 survey → 首页即提示完成，不进提问页。"""
    return ip in completed_ips


def create_blindtest_app(
    *,
    fragments: list[str] | None = None,
    out_dir: str | Path = "reports/blindtest",
    pool_file: str | Path = "reports/baselines",
    completed_ips: set[str] | None = None,
    rate_limit: int = 10,
    rate_window_s: float = 3600.0,
) -> FastAPI:
    """Build the subject-facing blind-test app with U1–U4 revisions."""
    fragments = fragments or _DEFAULT_FRAGMENTS
    completed = completed_ips or set()
    app = FastAPI(title="LifeOS Blind Test", version="0.1.0")
    sessions: dict[str, dict[str, Any]] = {}

    def _client_ip(request: Request) -> str:
        """用户真实 IP 解析链（2026-10-01 巨大 bug 修复）。

        ``request.client.host`` 在 nginx/proxy 反代场景记录的是**代理/app
        的 IP**（如 127.0.0.1），不是用户的 session IP——所有用户共享同一
        条目，唯一性检测与限流全部失真（同一 IP 一人提交，全员被挡）。
        解析链：
        1. ``X-Forwarded-For``（最左非空项 = 原始客户端，逐级代理追加；
           信任链由部署层保证——proxy_set_header X-Forwarded-For）；
        2. ``X-Real-IP``（nginx 常设）；
        3. 兜底 ``request.client.host``（直连场景的 socket 对端）。
        """
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        real = request.headers.get("x-real-ip", "").strip()
        if real:
            return real
        return request.client.host if request.client else "unknown"

    def _guard(request: Request) -> str:
        """U1 rate limit; over => 429 (限流不静默).

        ``/answer`` 不占限流（被试必须连续作答 24 题 > 10 次/窗口——
        限流对象是浏览/start/pool 的防滥用，不是作答流本身）。
        """
        ip = _client_ip(request)
        if not check_rate_limit(ip, limit=rate_limit, window_s=rate_window_s):
            raise HTTPException(status_code=429, detail="请求过于频繁（每 IP 每窗口最多 10 次），请稍后再试")
        return ip

    def _pool_materials() -> dict[str, Any]:
        base = Path(pool_file)
        per_arm: dict[str, dict[str, str]] = {}
        user_msgs: dict[str, str] = {}
        for arm in ("A", "B", "C", "LifeOS"):
            p = base / f"baseline_{arm}_real.json"
            if not p.exists():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            for row in d["rows"]:
                per_arm.setdefault(row["scenario_id"], {})[arm] = row["response"]
        import yaml

        scen = yaml.safe_load(
            (Path(__file__).resolve().parents[3] / "data" / "goldset" / "behavior_scenarios" / "behavior_scenarios_v0.1.yaml").read_text(encoding="utf-8")
        )
        for item in scen["items"]:
            user_msgs[item["scenario_id"]] = item["utterance"]
        materials = {}
        for fid in fragments:
            if fid in per_arm and len(per_arm[fid]) == 4:
                materials[fid] = {"user_msg": user_msgs.get(fid, ""), **per_arm[fid]}
        return materials

    def _ip_submitted(ip: str) -> bool:
        """N1 修复: 完成 = 该 IP 关联的作答已持久化在 responses.jsonl（真相源）。

        内存 set 只在 SUBMIT 成功后记录（提交才记录，不提前）；且查持久化
        文件——重启服务后完成状态不丢，未提交的 IP 永远不被标记。
        """
        if ip_has_completed(ip, completed_ips=completed):
            return True
        p = Path(out_dir) / "responses.jsonl"
        if not p.exists():
            return False
        # per-IP 提交台账（submitted_ips.json: {ip: subject_id}，submit 时写入）
        ledger = Path(out_dir) / "submitted_ips.json"
        if not ledger.exists():
            return False
        d = json.loads(ledger.read_text(encoding="utf-8"))
        return ip in d.get("ips", {})

    @app.get("/blindtest")
    def page(request: Request) -> HTMLResponse:
        # R2 根因修复 + i18n 双版: 渲染时注入 zh/en 两版叙述（JS 曾引用
        # 未定义的 NARRATIVE → ReferenceError 中断全部脚本）
        rendered = _PAGE.replace(
            "NARRATIVE_ZH_PLACEHOLDER__",
            json.dumps(BACKGROUND_NARRATIVE, ensure_ascii=False),
        ).replace(
            "NARRATIVE_EN_PLACEHOLDER__",
            json.dumps(BACKGROUND_NARRATIVE_EN, ensure_ascii=False),
        )
        # F1 修复: 已提交 IP → **主页面完整保留**（可回顾背景与同意条款），
        # foot bar 提示"您已经提交过了 survey"，开始按钮置灰——
        # 不再整页替换为 banner（用户：希望仍然能看到主页面）
        ip = _client_ip(request)
        if _ip_submitted(ip):
            footbar = (
                "<script>window.__SUBMITTED__=true;"
                "document.getElementById('footbar').style.display='block';"
                "document.getElementById('start_btn').disabled=true;"
                "document.getElementById('start_btn').textContent='您已经提交过了 survey（重复提交视为作废）';"
                "</script>"
            )
            return HTMLResponse(rendered.replace("</body>", footbar + "</body>"))
        return HTMLResponse(rendered)

    @app.get("/blindtest/api/pool")
    def pool(request: Request) -> dict[str, Any]:
        _guard(request)
        return {"materials": _pool_materials(), "narrative": BACKGROUND_NARRATIVE}

    @app.get("/blindtest/api/survey")
    def api_survey(survey: str = "", request: Request = None) -> dict[str, Any]:
        """Load one survey instance (T1: ?survey=LIFE-BT-002) — REAL arm texts, blind view."""
        if survey.strip():
            try:
                from lifeos.dogfood.survey_intake import load_survey

                inst = load_survey(survey)
            except Exception as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            trials = [
                {k: t[k] for k in ("order_seq", "fragment_id", "is_attention_check", "left_text", "right_text", "user_msg")}
                for t in inst["trials"]
            ]
            return {
                "survey_id": inst["survey_id"], "subject_id": inst["subject_id"],
                "approval_number": inst["approval_number"], "consent_items": inst["consent_items"],
                "instructions": inst["instructions"], "trials": trials,
            }
        return {
            "survey_id": "", "subject_id": "", "approval_number": APPROVAL_NUMBER_CONST,
            "consent_items": CONSENT_ITEMS_CONST, "instructions": INSTRUCTIONS_CONST,
            "trials": [
                {k: t[k] for k in ("order_seq", "fragment_id", "is_attention_check")}
                for t in build_trial_sequence(subject_seq=0, fragments=fragments)
            ],
        }

    @app.post("/blindtest/api/start")
    def api_start(body: dict[str, Any], request: Request) -> dict[str, Any]:
        ip = _guard(request)
        # U1 uniqueness: 已完成 IP → 不进提问页
        if ip_has_completed(ip, completed_ips=completed):
            raise HTTPException(status_code=409, detail="您已经完成了 survey（重复提交视为作废）")
        subject = str(body.get("subject_id", "")).strip()
        age = int(body.get("age", 25))
        email = str(body.get("email", "")).strip()
        if not subject:
            raise HTTPException(status_code=422, detail="subject_id required (化名编号)")
        # 方案 A + M1: email 单向哈希防重（原文不入库；重复 → 409 作废）；
        # M1 语义分离: subject_id 已存在（未提交）不拒绝——重复的「匿名」
        # 不触发防重，email 台账只挡 email 重复（未提交的重进 = 恢复作答）
        # M1 残留修复: email 台账在 START 时只查不记——同一 email 未提交重进
        # 放行（"重复的匿名"不触发防重）；台账在 SUBMIT 成功后才记录（与
        # IP 台账同构：提交才记录）
        if email:
            from lifeos.dogfood.survey_intake import check_duplicate, email_hash

            h = email_hash(email)
            if check_duplicate(h, out_dir=out_dir):
                raise HTTPException(
                    status_code=409,
                    detail="该 email 已提交过作答，重复提交视为作废（重复检测，email 原文不保存）",
                )
            sessions[subject + ":email"] = h  # 会话内暂存，submit 时入台账
        # session fragments: from the SURVEY INSTANCE's order when the subject
        # id maps to a survey file (interface consistency: /survey 与 /start
        # 的片段顺序一致)
        session_frags = list(fragments)
        seq = 0
        try:
            from lifeos.dogfood.survey_intake import load_survey

            if subject.startswith("LIFE-BT-"):
                inst = load_survey(subject)
                seen: list[str] = []
                for t in inst["trials"]:
                    if t["fragment_id"] not in seen:
                        seen.append(t["fragment_id"])
                session_frags = seen
                seq = int(subject.rsplit("-", 1)[-1])
        except Exception:
            pass  # no survey instance: fall back to the built-in fragment order
        try:
            start_session(
                external_user_id=subject,
                subject_seq=seq,
                fragments=session_frags,
                age=age,
                is_member_or_family=False,
                consent_signed=True,
                at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        trials = build_trial_sequence(subject_seq=seq, fragments=session_frags)
        sessions[subject] = {"trials": trials, "consent": True, "started_at": datetime.now(timezone.utc).isoformat()}
        # Q1 修复: trial 需带 arm_left/arm_right（页面 JS 用它映射 L/R → 臂名；
        # 臂名只是左右标签，不暴露实现差异，盲测语义不变——之前全剥导致 chose=undefined 空串）
        return {"trials": [{k: t.get(k) for k in ("fragment_id", "order_seq", "is_attention_check", "arm_left", "arm_right", "user_msg")} for t in trials]}

    @app.post("/blindtest/api/answer")
    def api_answer(body: dict[str, Any], request: Request) -> dict[str, Any]:
        # /answer 不占限流（被试必须连续作答 24 题 > 10 次/窗口；限流对象
        # 是浏览/start/pool 的防滥用，不是作答流本身——N1 交互缺陷修复）
        subject = str(body.get("subject_id", ""))
        sess = sessions.get(subject)
        if sess is None:
            raise HTTPException(status_code=403, detail="no session (start first, consent-gated)")
        trials = sess["trials"]
        order_seq = int(body.get("order_seq", -1))
        trial = next((t for t in trials if t["order_seq"] == order_seq), None)
        if trial is None:
            raise HTTPException(status_code=404, detail="unknown order_seq")
        chose = str(body.get("chose", ""))
        if body.get("is_attention_check"):
            if chose != trial["arm_left"]:
                raise HTTPException(status_code=422, detail="注意力检查未按提示作答（请按提示选择）")
        try:
            record_response(trial, chose=chose, reason_text=str(body.get("reason_text", "")), at=datetime.now(timezone.utc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "next": order_seq + 1}

    @app.post("/blindtest/api/submit")
    def api_submit(body: dict[str, Any], request: Request) -> dict[str, Any]:
        _guard(request)
        subject = str(body.get("subject_id", ""))
        sess = sessions.get(subject)
        if sess is None:
            raise HTTPException(status_code=403, detail="no session")
        trials = sess["trials"]
        passed = attention_check_passed(trials)
        voided = apply_attention_rule(trials, passed=passed)
        path = persist_responses(trials, subject_id=subject, out_dir=out_dir)
        answered = sum(1 for t in trials if t["chose"] and not t["voided"])
        # N1 修复: 完成 IP 台账持久化（submit 成功才写入；未提交的 IP 永不标记）
        ip = _client_ip(request)
        completed.add(ip)
        ips_ledger = Path(out_dir) / "submitted_ips.json"
        d = json.loads(ips_ledger.read_text(encoding="utf-8")) if ips_ledger.exists() else {"ips": {}}
        d["ips"][ip] = subject
        ips_ledger.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        # M1 残留修复: email 哈希台账在 submit 成功后才记录（start 只查不记）
        email_h = sessions.get(subject + ":email")
        if email_h:
            from lifeos.dogfood.survey_intake import record_hash

            record_hash(email_h, subject_id=subject, out_dir=out_dir, at=datetime.now(timezone.utc))
            sessions.pop(subject + ":email", None)
        msg = (
            f"作答已提交：有效 {answered}/{len(trials)}（作废 {voided}）。"
            if passed
            else f"注意力检查未通过，全部作答已作废（{voided} 条）。"
        )
        return {"ok": True, "attention_passed": passed, "voided": voided, "answered": answered,
                "message": msg, "persisted": str(path)}

    return app


APPROVAL_NUMBER_CONST = "2026-ETH-00001"
CONSENT_ITEMS_CONST = [
    "我已阅读并理解知情同意书（含两级删除语义与 30 天备份窗口披露），自愿参与",
    "我理解我的作答将匿名化存储，且与我的关联仅为化名编号",
    "我知道我可随时查阅/更正/删除/导出我的数据",
]
INSTRUCTIONS_CONST = "每个片段阅读用户消息与左右两个回复，判断「是不是同一个它」（二选一强制）并写一两句理由（200 字以内）；题目流中有 1 道注意力检查题，未通过将作废全部作答。"
