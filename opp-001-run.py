# -*- coding: utf-8 -*-
"""
==================================================
opp-001 精简入口 — A股市场数据推送（无 AI 分析）
==================================================

功能：
  1. 调用 PureDataFetcher 拉取客观市场数据
  2. 通过 FeishuPusher 推送到飞书群机器人

安全要求：
  - Webhook URL 仅通过环境变量 FEISHU_WEBHOOK_URL 获取
  - 绝不硬编码在代码中

合规声明：
  本脚本仅推送客观市场数据，不包含任何投资分析、预测或建议。

用法：
  FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" python opp-001-run.py
"""

import os
import sys
import logging
from datetime import datetime

# ----------------------------------------------------------
# 路径设置：确保可以导入同目录模块和 data_provider
# ----------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "opp-001-daily-stock"))

# ----------------------------------------------------------
# 日志
# ----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("opp-001-run")


# ============================================================
# 主流程
# ============================================================

def main():
    logger.info("opp-001 数据推送启动（纯数据，非投资建议）")

    # ---- Step 1: 获取飞书 Webhook URL（仅环境变量） ----
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()

    if not webhook_url:
        logger.error("未设置 FEISHU_WEBHOOK_URL 环境变量，无法推送。")
        logger.info("请设置: FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
        sys.exit(1)

    logger.info("飞书 Webhook URL 已从环境变量加载")

    # ---- Step 2: 导入数据采集与推送模块 ----
    try:
        from opp_001_data_fetcher import PureDataFetcher
        from opp_001_push import FeishuPusher
    except ImportError:
        # opp-001-push.py 文件名含连字符，无法直接 import，需手动加载
        import importlib.util
        push_path = os.path.join(ROOT_DIR, "opp-001-push.py")
        spec = importlib.util.spec_from_file_location("opp001_push", push_path)
        opp001_push = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(opp001_push)
        FeishuPusher = opp001_push.FeishuPusher

        from opp_001_data_fetcher import PureDataFetcher

    # ---- Step 3: 拉取客观市场数据（无 AI 分析） ----
    logger.info("正在拉取 A 股市场客观数据...")
    try:
        fetcher = PureDataFetcher()
        raw_report = fetcher.generate_data_report()
        logger.info("数据报告生成完成（%d 字符）", len(raw_report))
    except Exception as e:
        logger.error("数据拉取失败: %s", e)
        sys.exit(2)

    # ---- Step 4: 附加合规声明 ----
    compliance_footer = (
        "\n\n---\n"
        "⚠️ 以上数据仅供参考，不构成投资建议。投资有风险，入市需谨慎。\n"
        "数据来源：AkShare / 东方财富"
    )

    if "以上数据仅供参考" not in raw_report:
        full_message = raw_report.rstrip() + compliance_footer
    else:
        full_message = raw_report

    # ---- Step 5: 推送到飞书 ----
    logger.info("正在推送到飞书...")
    try:
        pusher = FeishuPusher(webhook_url=webhook_url)
        ok = pusher.send(full_message)
    except Exception as e:
        logger.error("飞书推送异常: %s", e)
        sys.exit(3)

    if ok:
        logger.info("推送完成 ✅ — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        sys.exit(0)
    else:
        logger.error("推送失败 ❌")
        sys.exit(4)


if __name__ == "__main__":
    main()
