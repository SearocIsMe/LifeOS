"""N1/N2 acceptance: completion-record timing + tickbox alignment.

- N1 completion timing -> IP recorded ONLY on successful submit (start
  alone never marks); completion check reads the persisted ledger
  (submitted_ips.json) - survives restart, never pre-marks;
- N1 answer unthrottled -> /answer does not count against the rate limit
  (subjects must answer 24 trials > 10/window);
- N2 alignment CSS -> checkbox/label flex alignment in the served page.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from lifeos.dogfood.blindtest_app import create_blindtest_app
from lifeos.dogfood.survey_intake import load_survey


def _app(out_dir):
    return create_blindtest_app(out_dir=out_dir, pool_file="reports/baselines")


def test_n1_no_submit_no_completion_mark(tmp_path):
    """未提交的 IP 永不被标记（提交才记录——bug 修复）。"""
    async def flow():
        async with AsyncClient(transport=ASGITransport(app=_app(tmp_path)), base_url="http://t") as c:
            r = await c.post("/blindtest/api/start", json={"subject_id": "LIFE-BT-002", "age": 25, "email": "a@example.com"})
            assert r.status_code == 200
            html = (await c.get("/blindtest")).text
            assert "__COMPLETED__" not in html  # 只 start 未 submit → 无完成标记
            # ledger not written (提交才记录)
            assert not (tmp_path / "submitted_ips.json").exists()

    asyncio.run(flow())


def test_n1_submit_writes_persisted_ledger(tmp_path):
    """submit 成功才写台账；重启服务（新 app 实例）后完成状态不丢。

    F1 修订: 完成提示为 footbar（主页面保留），不再是整页 banner——
    断言同步修订（footbar 显示 + 开始按钮置灰）。
    """
    async def flow():
        app = _app(tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            await c.post("/blindtest/api/start", json={"subject_id": "LIFE-BT-002", "age": 25, "email": "b@example.com"})
            inst = load_survey("LIFE-BT-002")
            for st in inst["trials"]:
                chose = st["arm_right"] if st["order_seq"] % 2 else st["arm_left"]
                await c.post("/blindtest/api/answer", json={"subject_id": "LIFE-BT-002", "order_seq": st["order_seq"], "chose": chose, "reason_text": "t", "is_attention_check": st["is_attention_check"]})
            await c.post("/blindtest/api/submit", json={"subject_id": "LIFE-BT-002"})
        # NEW app instance (restart simulation): completion persists
        app2 = _app(tmp_path)
        async with AsyncClient(transport=ASGITransport(app2), base_url="http://t") as c:
            html = (await c.get("/blindtest")).text
            # 重启后完成状态不丢（查持久化台账）→ footbar 显示 + 按钮置灰
            assert "getElementById('footbar').style.display='block'" in html
            assert "您已经提交过了 survey" in html

    asyncio.run(flow())


def test_n1_answer_not_throttled(tmp_path):
    """/answer 不占限流：24 题连续作答全部通过（限流对象是浏览/start/pool）。"""
    async def flow():
        async with AsyncClient(transport=ASGITransport(app=_app(tmp_path)), base_url="http://t") as c:
            await c.post("/blindtest/api/start", json={"subject_id": "LIFE-BT-002", "age": 25, "email": "c@example.com"})
            inst = load_survey("LIFE-BT-002")
            for st in inst["trials"]:
                chose = st["arm_right"] if st["order_seq"] % 2 else st["arm_left"]
                r = await c.post("/blindtest/api/answer", json={"subject_id": "LIFE-BT-002", "order_seq": st["order_seq"], "chose": chose, "reason_text": "t", "is_attention_check": st["is_attention_check"]})
                assert r.status_code == 200, f"answer {st['order_seq']} throttled: {r.text}"

    asyncio.run(flow())


def test_n2_alignment_css_served(tmp_path):
    """tickbox 与文本对齐 CSS 在档（checkbox 内联 + label flex）。"""
    async def flow():
        async with AsyncClient(transport=ASGITransport(app=_app(tmp_path)), base_url="http://t") as c:
            html = (await c.get("/blindtest")).text
            assert 'vertical-align:middle' in html
            assert 'consent-list label{display:flex' in html
            assert 'align-items:flex-start' in html

    asyncio.run(flow())


def test_client_ip_xff_chain(tmp_path):
    """IP 解析链（2026-10-01 巨大 bug 修复）：XFF 最左 = 用户真实 IP，
    兜底 socket 对端——nginx 反代场景所有用户不再共享 127.0.0.1。"""
    async def flow():
        app = _app(tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # 用户 A（XFF）提交
            await c.post("/blindtest/api/start", json={"subject_id": "LIFE-BT-002", "age": 25, "email": "a@example.com"},
                         headers={"X-Forwarded-For": "203.0.113.5"})
            inst = load_survey("LIFE-BT-002")
            for st in inst["trials"]:
                chose = st["arm_right"] if st["order_seq"] % 2 else st["arm_left"]
                await c.post("/blindtest/api/answer", json={"subject_id": "LIFE-BT-002", "order_seq": st["order_seq"], "chose": chose, "reason_text": "t", "is_attention_check": st["is_attention_check"]},
                             headers={"X-Forwarded-For": "203.0.113.5"})
            await c.post("/blindtest/api/submit", json={"subject_id": "LIFE-BT-002"},
                         headers={"X-Forwarded-For": "203.0.113.5"})
            # 台账记录的是 XFF IP（203.0.113.5），不是代理 127.0.0.1
            ips = json.loads((tmp_path / "submitted_ips.json").read_text(encoding="utf-8"))
            assert "203.0.113.5" in ips["ips"], ips
            assert "127.0.0.1" not in ips["ips"] or ips["ips"].get("127.0.0.1") != ips["ips"].get("203.0.113.5")
            # 用户 B（不同 XFF）不受影响
            r = await c.post("/blindtest/api/start", json={"subject_id": "LIFE-BT-003", "age": 25, "email": "b@example.com"},
                             headers={"X-Forwarded-For": "198.51.100.7"})
            assert r.status_code == 200  # 全员不被挡（解析链修复核心断言）
            # X-Real-IP 次选
            r2 = await c.post("/blindtest/api/start", json={"subject_id": "LIFE-BT-004", "age": 25},
                              headers={"X-Real-IP": "198.51.100.9"})
            assert r2.status_code == 200

    asyncio.run(flow())


def test_f1_footbar_keeps_main_page(tmp_path):
    """F1: 已提交 IP 再访问 → 主页面完整保留 + footbar 提示 + 开始按钮置灰
    （不再整页替换为 banner）。"""
    async def flow():
        app = _app(tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            await c.post("/blindtest/api/start", json={"subject_id": "LIFE-BT-002", "age": 25, "email": "d@example.com"},
                         headers={"X-Forwarded-For": "203.0.113.9"})
            inst = load_survey("LIFE-BT-002")
            for st in inst["trials"]:
                chose = st["arm_right"] if st["order_seq"] % 2 else st["arm_left"]
                await c.post("/blindtest/api/answer", json={"subject_id": "LIFE-BT-002", "order_seq": st["order_seq"], "chose": chose, "reason_text": "t", "is_attention_check": st["is_attention_check"]},
                             headers={"X-Forwarded-For": "203.0.113.9"})
            await c.post("/blindtest/api/submit", json={"subject_id": "LIFE-BT-002"},
                         headers={"X-Forwarded-For": "203.0.113.9"})
            html = (await c.get("/blindtest", headers={"X-Forwarded-For": "203.0.113.9"})).text
            # 主页保留：consent 页元素 + 背景叙述在档
            assert 'id="consent"' in html and "背景" in html
            # footbar 显示 + 开始按钮置灰
            assert "getElementById('footbar').style.display='block'" in html
            assert "您已经提交过了 survey" in html
            assert "getElementById('start_btn').disabled=true" in html

    asyncio.run(flow())
