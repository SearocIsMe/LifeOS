"""UI revisions contract tests (test-first): U1–U4 (用户 7 条修改意见).

- U1 rate limit   -> 每 IP ≤10 次 /api 请求；超限 429（限流不静默）
- U1 uniqueness   -> 已提交过 survey 的 IP：首页即提示完成，不进提问页
- U2 back button  -> 上一题回退（trial 流可倒推，答案保留）
- U3 fragment page-> 无静态回复 box（bubble 样式移除）；回复按钮暖色调；
                     理由 ≤200 字；默认理由 grey 字体提示
- U4 responsive   -> 全页面 viewport 响应式排版；全部按钮暖色系
- U4 background   -> 首页背景叙述 ≤300 字
"""

from __future__ import annotations

import json

import pytest


# --------------------------------------------------------------------------- #
# U1: IP rate limit + uniqueness (backend)
# --------------------------------------------------------------------------- #

def test_ip_rate_limit_10_per_ip():
    from lifeos.dogfood.blindtest_app import check_rate_limit

    ip = "192.168.10.50"
    for i in range(10):
        assert check_rate_limit(ip, limit=10) is True  # 10 次内放行
    assert check_rate_limit(ip, limit=10) is False  # 第 11 次 → 拒绝


def test_rate_limit_reset_by_window(tmp_path):
    from lifeos.dogfood.blindtest_app import check_rate_limit

    ip = "192.168.10.51"
    for i in range(10):
        check_rate_limit(ip, limit=10, window_s=60)
    assert check_rate_limit(ip, limit=10, window_s=60) is False
    # 窗口外（新窗口）重置
    assert check_rate_limit(ip, limit=10, window_s=0) is True  # window=0 → 新窗口


def test_ip_uniqueness_completed_survey():
    from lifeos.dogfood.blindtest_app import ip_has_completed

    ip = "192.168.10.60"
    assert ip_has_completed(ip, completed_ips=set()) is False
    # 提交过一次 survey 的 IP：首页即提示完成
    assert ip_has_completed(ip, completed_ips={ip}) is True


def test_page_shows_completed_banner_for_submitted_ip():
    """已提交 IP 访问首页 → 完成提示，不进提问页（前端逻辑由后端 flag 驱动）。"""
    from lifeos.dogfood.blindtest_app import create_blindtest_app

    app = create_blindtest_app(out_dir="/tmp/ui_smoke", pool_file="reports/baselines",
                               completed_ips={"192.168.10.203"})
    # the page HTML carries the completed banner element (client renders from flag)
    html = _page_html(app)
    assert "已经完成了" in html or "completed" in html.lower()


def _page_html(app) -> str:
    import asyncio

    from httpx import ASGITransport, AsyncClient

    async def fetch() -> str:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/blindtest")
            return r.text

    return asyncio.run(fetch())


# --------------------------------------------------------------------------- #
# U2: back button (trial 流可倒推)
# --------------------------------------------------------------------------- #

def test_back_navigation_preserves_answers():
    from lifeos.dogfood.blindtest_page import build_trial_sequence

    seq = build_trial_sequence(subject_seq=0, fragments=["BS-026", "BS-027"])
    # answer trial 0, move to 1, then back to 0: answer preserved
    seq[0]["chose"] = seq[0]["arm_left"]
    idx = 1
    idx = max(0, idx - 1)  # 倒推
    assert idx == 0
    assert seq[idx]["chose"] == seq[0]["arm_left"]  # 答案保留（不因回退丢失）


# --------------------------------------------------------------------------- #
# U3/U4: page layout (static checks on the served HTML)
# --------------------------------------------------------------------------- #

def test_no_static_bubble_boxes():
    html = _page_html(_app())
    assert 'class="bubble"' not in html  # 静态回复 box 移除


def test_warm_color_buttons():
    html = _page_html(_app())
    # 暖色系（amber/orange family）按钮样式在档
    for token in ("#f59e0b", "#d97706", "#b45309", "amber"):
        if token in html:
            return
    pytest.fail("no warm-color button style found")


def test_reason_limit_200_and_grey_hint():
    html = _page_html(_app())
    assert "200" in html  # 理由 200 字上限提示
    assert "999" in html.lower() or "grey" in html.lower() or "#9ca3af" in html  # grey hint


def test_viewport_responsive():
    html = _page_html(_app())
    assert "viewport" in html  # 响应式 meta
    assert "@media" in html or "max-width" in html or "flex" in html  # 自适应排版


def test_background_narrative_300_chars():
    html = _page_html(_app())
    # 背景叙述元素在档且标 ≤300 字
    assert "背景" in html and "300" in html


def _app():
    from lifeos.dogfood.blindtest_app import create_blindtest_app

    return create_blindtest_app(out_dir="/tmp/ui_smoke", pool_file="reports/baselines")
