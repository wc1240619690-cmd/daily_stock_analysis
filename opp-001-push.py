# -*- coding: utf-8 -*-
"""
==================================================
opp-001 纯数据推送模块（飞书 + 企业微信 Webhook）
==================================================

自包含的轻量级推送脚本，不依赖上游项目的复杂通知系统。

支持的推送渠道:
  - 飞书群机器人 Webhook（推荐，配置最简单）
  - 企业微信机器人 Webhook

合规声明:
  每条推送末尾强制附带风险提示，不包含任何投资分析/预测/建议。

配置方式:
  1. 环境变量（推荐）
  2. .env 文件

用法:
  python opp-001-push.py              # 拉数据 + 推送到所有已配置渠道
  python opp-001-push.py --dry-run    # 只打印消息，不实际推送
  python opp-001-push.py --feishu-only   # 仅飞书
  python opp-001-push.py --wechat-only   # 仅企业微信
  python opp-001-push.py --test-feishu <URL>   # 测试飞书连接
  python opp-001-push.py --test-wechat <URL>   # 测试企业微信连接
"""

import os
import sys
import json
import time
import base64
import hashlib
import hmac
import logging
import argparse
from datetime import datetime
from typing import Optional, Dict, List, Any

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("opp-001-push")

# ============================================================
# 合规声明（每条推送末尾强制附带）
# ============================================================
COMPLIANCE_FOOTER = (
    "\n\n---\n"
    "⚠️ 以上数据仅供参考，不构成投资建议。投资有风险，入市需谨慎。\n"
    "数据来源：AkShare / 东方财富"
)


# ============================================================
# 飞书推送器（Webhook 模式）
# ============================================================

class FeishuPusher:
    """
    飞书群机器人 Webhook 推送器。

    仅支持最简单的 Webhook 模式，无需 App ID / App Secret。
    支持关键词校验和签名校验。

    用法:
        pusher = FeishuPusher(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
        pusher.send("# 标题\n\n内容...")
    """

    def __init__(
        self,
        webhook_url: str,
        secret: Optional[str] = None,
        keyword: Optional[str] = None,
        max_bytes: int = 20000,
        verify_ssl: bool = True,
    ):
        self.webhook_url = webhook_url
        self.secret = (secret or "").strip()
        self.keyword = (keyword or "").strip()
        self.max_bytes = max_bytes
        self.verify_ssl = verify_ssl

    # ---- 签名 ----

    def _build_sign(self) -> Dict[str, str]:
        """构造飞书签名校验字段（timestamp + sign）。"""
        if not self.secret:
            return {}
        ts = str(int(time.time()))
        sign_str = f"{ts}\n{self.secret}"
        sign = base64.b64encode(
            hmac.new(sign_str.encode("utf-8"), digestmod=hashlib.sha256).digest()
        ).decode("utf-8")
        return {"timestamp": ts, "sign": sign}

    def _apply_keyword(self, content: str) -> str:
        """在消息开头添加关键词（飞书安全设置要求）。"""
        if not self.keyword:
            return content
        return f"{self.keyword}\n{content}"

    # ---- 卡片构建 ----

    @staticmethod
    def _build_card(content: str) -> dict:
        """构建飞书交互式卡片消息体。"""
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "A股市场数据报告"},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": content},
                }
            ],
        }

    # ---- HTTP 发送 ----

    def _post(self, payload: dict) -> bool:
        """发送 HTTP POST 到飞书 Webhook。"""
        payload.update(self._build_sign())
        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30,
                verify=self.verify_ssl,
            )
        except requests.RequestException as e:
            logger.error("飞书网络异常: %s", e)
            return False

        if resp.status_code != 200:
            logger.error("飞书请求失败: HTTP %s", resp.status_code)
            return False

        try:
            result = resp.json()
        except ValueError:
            logger.error("飞书返回非 JSON 响应")
            return False

        code = result.get("code") if "code" in result else result.get("StatusCode")
        if code == 0:
            logger.info("飞书推送成功")
            return True
        logger.error("飞书返回错误: code=%s msg=%s", code, result.get("msg", ""))
        return False

    def _send_card(self, content: str) -> bool:
        """发送交互式卡片消息。"""
        return self._post({
            "msg_type": "interactive",
            "card": self._build_card(content),
        })

    def _send_text(self, content: str) -> bool:
        """发送纯文本消息（卡片发送失败时的兜底）。"""
        return self._post({
            "msg_type": "text",
            "content": {"text": content},
        })

    # ---- Markdown → lark_md 简化转换 ----

    @staticmethod
    def _format_for_feishu(content: str) -> str:
        """
        将基本 Markdown 转为飞书 lark_md 兼容格式。

        飞书 lark_md 不支持：
          - 标准 Markdown 标题（# ## ###）→ 用 **加粗** 代替
          - 引用块（>）→ 添加 💬 前缀
          - 分割线（---）→ 全角横线
        """
        import re

        lines = []
        in_code = False

        for raw_line in content.splitlines():
            line = raw_line.rstrip()

            # 保护代码块
            if line.startswith("```"):
                in_code = not in_code
                lines.append(line)
                continue
            if in_code:
                lines.append(line)
                continue

            stripped = line.strip()

            if stripped.startswith("### "):
                lines.append(f"**{stripped[4:]}**")
            elif stripped.startswith("## "):
                lines.append(f"**{stripped[3:]}**")
            elif stripped.startswith("# "):
                lines.append(f"**{stripped[2:]}**")
            elif stripped.startswith("> "):
                lines.append(f"💬 {stripped[2:]}")
            elif stripped == "---":
                lines.append("————————————————")
            else:
                lines.append(line)

        return "\n".join(lines)

    # ---- 分片 ----

    def _chunk_content(self, content: str) -> List[str]:
        """将超长内容按有效最大字节数分片。"""
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= self.max_bytes:
            return [content]

        chunks = []
        current_lines = []
        current_bytes = 0

        for line in content.splitlines(keepends=True):
            line_bytes = len(line.encode("utf-8"))
            if current_bytes + line_bytes > self.max_bytes and current_lines:
                chunks.append("".join(current_lines))
                current_lines = []
                current_bytes = 0
            current_lines.append(line)
            current_bytes += line_bytes

        if current_lines:
            chunks.append("".join(current_lines))

        total = len(chunks)
        if total > 1:
            for i in range(total):
                chunks[i] = f"📄 ({i+1}/{total})\n{chunks[i]}"

        return chunks

    # ---- 公开接口 ----

    def send(self, content: str) -> bool:
        """
        推送消息到飞书。自动处理关键词、签名、分片。
        卡片优先，纯文本兜底。
        """
        if not self.webhook_url:
            logger.warning("飞书 Webhook URL 未配置，跳过推送")
            return False

        formatted = self._format_for_feishu(content)

        # 分片（预留关键词 + JSON 开销）
        keyword_overhead = len(self.keyword.encode("utf-8")) if self.keyword else 0
        effective_max = self.max_bytes - keyword_overhead - 500
        if effective_max < 200:
            logger.error("飞书关键词过长，消息预算不足")
            return False

        chunks = self._chunk_content(formatted)

        success_all = True
        for i, chunk in enumerate(chunks):
            prepared = self._apply_keyword(chunk)
            ok = self._send_card(prepared)
            if not ok:
                logger.info("飞书卡片发送失败，尝试纯文本兜底...")
                ok = self._send_text(prepared)
            if not ok:
                logger.error("飞书第 %d/%d 片发送失败", i + 1, len(chunks))
                success_all = False
            if i < len(chunks) - 1:
                time.sleep(0.8)

        return success_all


# ============================================================
# 企业微信推送器（Webhook 模式）
# ============================================================

class WechatWorkPusher:
    """
    企业微信机器人 Webhook 推送器。

    用法:
        pusher = WechatWorkPusher(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
        )
        pusher.send("# 标题\n\n内容...")

    注意：
      - Markdown 类型限制约 4096 字节
      - Text 类型限制约 2048 字节
      - 超长自动分片
    """

    def __init__(
        self,
        webhook_url: str,
        msg_type: str = "markdown",
        max_bytes: int = 4000,
        verify_ssl: bool = True,
    ):
        self.webhook_url = webhook_url
        self.msg_type = msg_type  # "markdown" or "text"
        self.max_bytes = max_bytes
        self.verify_ssl = verify_ssl

    def _post(self, payload: dict) -> bool:
        """发送 HTTP POST 到企业微信 Webhook。"""
        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                verify=self.verify_ssl,
            )
        except requests.RequestException as e:
            logger.error("企业微信网络异常: %s", e)
            return False

        if resp.status_code == 200:
            result = resp.json()
            if result.get("errcode") == 0:
                logger.info("企业微信推送成功")
                return True
            logger.error("企业微信返回错误: %s", result.get("errmsg", ""))
            return False
        logger.error("企业微信请求失败: HTTP %s", resp.status_code)
        return False

    def _send_single(self, content: str) -> bool:
        """发送单条消息。"""
        if self.msg_type == "text":
            payload = {
                "msgtype": "text",
                "text": {"content": content},
            }
        else:
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": content},
            }
        return self._post(payload)

    def _chunk_content(self, content: str) -> List[str]:
        """按 max_bytes 分片，优先按分割线切分。"""
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= self.max_bytes:
            return [content]

        # 按自然边界切分
        if "\n---\n" in content:
            sections = content.split("\n---\n")
            sep = "\n---\n"
        elif "\n## " in content:
            parts = content.split("\n## ")
            sections = [parts[0]] + [f"## {p}" for p in parts[1:]]
            sep = "\n"
        else:
            sections = content.split("\n")
            sep = "\n"

        chunks = []
        current = []
        current_bytes = 0
        sep_bytes = len(sep.encode("utf-8"))

        for section in sections:
            sec_bytes = len(section.encode("utf-8"))
            overhead = sep_bytes if current else 0
            if current_bytes + sec_bytes + overhead > self.max_bytes:
                if current:
                    chunks.append(sep.join(current))
                current = [section]
                current_bytes = sec_bytes
            else:
                if current:
                    current_bytes += sep_bytes
                current.append(section)
                current_bytes += sec_bytes

        if current:
            chunks.append(sep.join(current))

        total = len(chunks)
        if total > 1:
            for i in range(total):
                chunks[i] = f"📄 ({i+1}/{total})\n{chunks[i]}"

        return chunks

    def send(self, content: str) -> bool:
        """推送消息到企业微信。自动分片。"""
        if not self.webhook_url:
            logger.warning("企业微信 Webhook URL 未配置，跳过推送")
            return False

        chunks = self._chunk_content(content)
        if not chunks:
            return False

        success_all = True
        for i, chunk in enumerate(chunks):
            ok = self._send_single(chunk)
            if not ok:
                logger.error("企业微信第 %d/%d 片发送失败", i + 1, len(chunks))
                success_all = False
            if i < len(chunks) - 1:
                time.sleep(0.5)

        return success_all


# ============================================================
# 报告格式化（推送专用）
# ============================================================

def format_push_report(report_text: str) -> str:
    """
    对 PureDataFetcher.generate_data_report() 的输出做推送适配：
    - 去掉全等号装饰线（飞书卡片自带标题）
    - 去掉报告中的合规声明（统一在推送器发送前补）
    - 保留所有客观数据
    """
    lines = report_text.split("\n")
    result_lines = []

    for line in lines:
        stripped = line.strip()
        # 跳过全等号装饰线
        if stripped.startswith("====") and stripped.endswith("====") and len(stripped) >= 10:
            continue
        # 跳过已有的合规声明（末尾统一加）
        if "以上数据仅供参考" in stripped:
            continue
        if stripped == "数据来源: AkShare / 东方财富":
            continue
        result_lines.append(line)

    text = "\n".join(result_lines).rstrip()
    if "以上数据仅供参考" not in text:
        text += COMPLIANCE_FOOTER

    return text


# ============================================================
# 推送服务（组合数据采集 + 推送）
# ============================================================

class DataPushService:
    """
    数据推送服务 —— 组合 PureDataFetcher 的数据采集和推送通道。
    """

    def __init__(self, config: dict):
        self.config = config
        self._feishu: Optional[FeishuPusher] = None
        self._wechat: Optional[WechatWorkPusher] = None
        self._init_pushers()

    def _init_pushers(self):
        """根据配置初始化推送器。"""
        feishu_url = self.config.get("feishu_webhook_url", "")
        if feishu_url:
            self._feishu = FeishuPusher(
                webhook_url=feishu_url,
                secret=self.config.get("feishu_webhook_secret"),
                keyword=self.config.get("feishu_webhook_keyword"),
                max_bytes=self.config.get("feishu_max_bytes", 20000),
                verify_ssl=self.config.get("webhook_verify_ssl", True),
            )
            logger.info("飞书推送器已配置")

        wechat_url = self.config.get("wechat_webhook_url", "")
        if wechat_url:
            self._wechat = WechatWorkPusher(
                webhook_url=wechat_url,
                msg_type=self.config.get("wechat_msg_type", "markdown"),
                max_bytes=self.config.get("wechat_max_bytes", 4000),
                verify_ssl=self.config.get("webhook_verify_ssl", True),
            )
            logger.info("企业微信推送器已配置")

    @property
    def available_channels(self) -> List[str]:
        channels = []
        if self._feishu:
            channels.append("feishu")
        if self._wechat:
            channels.append("wechat")
        return channels

    def fetch_data_report(self) -> str:
        """调用 PureDataFetcher 生成纯数据报告。"""
        from opp_001_data_fetcher import PureDataFetcher

        fetcher = PureDataFetcher()
        raw_report = fetcher.generate_data_report()
        return format_push_report(raw_report)

    def run(
        self,
        dry_run: bool = False,
        feishu_only: bool = False,
        wechat_only: bool = False,
    ) -> bool:
        """执行数据采集 + 推送。"""
        # Step 1: 拉取数据
        logger.info("正在拉取市场数据...")
        try:
            report = self.fetch_data_report()
        except Exception as e:
            logger.error("数据拉取失败: %s", e)
            return False

        logger.info("数据报告生成完成（%d 字符）", len(report))

        if dry_run:
            print("\n" + "=" * 60)
            print("  DRY RUN - 以下是将要推送的消息内容：")
            print("=" * 60)
            # 安全打印: Windows GBK 终端不支持 emoji，做回退处理
            try:
                print(report)
            except UnicodeEncodeError:
                safe = report.encode("gbk", errors="replace").decode("gbk", errors="replace")
                print(safe)
            print("=" * 60)
            channels = ', '.join(self.available_channels) or '(none)'
            print(f"可用推送渠道: {channels}")
            return True

        # Step 2: 推送
        success = True

        if wechat_only:
            if self._wechat:
                logger.info("正在推送至企业微信...")
                if not self._wechat.send(report):
                    success = False
            else:
                logger.warning("企业微信未配置")
                success = False
        elif feishu_only:
            if self._feishu:
                logger.info("正在推送至飞书...")
                if not self._feishu.send(report):
                    success = False
            else:
                logger.warning("飞书未配置")
                success = False
        else:
            for name, pusher in [("飞书", self._feishu), ("企业微信", self._wechat)]:
                if pusher:
                    logger.info("正在推送至%s...", name)
                    if not pusher.send(report):
                        success = False

        if not dry_run and not self.available_channels:
            logger.warning("没有配置任何推送渠道！")
            logger.info("请设置环境变量 FEISHU_WEBHOOK_URL 或 WECHAT_WEBHOOK_URL")
            return False

        return success


# ============================================================
# 配置加载
# ============================================================

def load_config_from_env() -> dict:
    """从环境变量加载推送配置。"""
    return {
        "feishu_webhook_url": os.getenv("FEISHU_WEBHOOK_URL", ""),
        "feishu_webhook_secret": os.getenv("FEISHU_WEBHOOK_SECRET", ""),
        "feishu_webhook_keyword": os.getenv("FEISHU_WEBHOOK_KEYWORD", ""),
        "feishu_max_bytes": int(os.getenv("FEISHU_MAX_BYTES", "20000")),
        "wechat_webhook_url": os.getenv("WECHAT_WEBHOOK_URL", ""),
        "wechat_msg_type": os.getenv("WECHAT_MSG_TYPE", "markdown"),
        "wechat_max_bytes": int(os.getenv("WECHAT_MAX_BYTES", "4000")),
        "webhook_verify_ssl": os.getenv("WEBHOOK_VERIFY_SSL", "true").lower() == "true",
    }


def load_config_from_dotenv() -> dict:
    """从 .env 文件加载配置（环境变量优先）。"""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and not os.getenv(key):
                    os.environ[key] = value

    return load_config_from_env()


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="opp-001 纯数据推送 — 拉取A股市场数据并推送到飞书/企业微信",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅打印消息，不实际推送")
    parser.add_argument("--feishu-only", action="store_true", help="仅推送到飞书")
    parser.add_argument("--wechat-only", action="store_true", help="仅推送到企业微信")
    parser.add_argument("--test-feishu", type=str, metavar="URL", help="测试飞书连接")
    parser.add_argument("--test-wechat", type=str, metavar="URL", help="测试企业微信连接")
    args = parser.parse_args()

    # -- 测试模式 --
    if args.test_feishu:
        logger.info("飞书推送测试模式")
        pusher = FeishuPusher(webhook_url=args.test_feishu)
        test_msg = (
            "**opp-001 数据推送测试**\n\n"
            f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "状态：✅ 飞书 Webhook 连接正常\n\n"
            "以上数据仅供参考，不构成投资建议。"
        )
        ok = pusher.send(test_msg)
        logger.info("测试结果: %s", "成功 ✅" if ok else "失败 ❌")
        return 0 if ok else 1

    if args.test_wechat:
        logger.info("企业微信推送测试模式")
        pusher = WechatWorkPusher(webhook_url=args.test_wechat)
        test_msg = (
            f"## opp-001 数据推送测试\n\n"
            f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "状态：✅ 企业微信 Webhook 连接正常\n\n"
            "> 以上数据仅供参考，不构成投资建议。"
        )
        ok = pusher.send(test_msg)
        logger.info("测试结果: %s", "成功 ✅" if ok else "失败 ❌")
        return 0 if ok else 1

    # -- Dry-run 模式（无需配置 webhook，直接拉数据展示）--
    if args.dry_run:
        logger.info("DRY RUN 模式 — 仅拉取数据，不推送")
        config = load_config_from_dotenv()
        service = DataPushService(config)
        ok = service.run(dry_run=True)
        return 0 if ok else 1

    # -- 正常推送模式 --
    config = load_config_from_dotenv()

    if not config["feishu_webhook_url"] and not config["wechat_webhook_url"]:
        logger.error("没有配置任何推送渠道！")
        logger.info("请设置以下环境变量之一：")
        logger.info("  FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
        logger.info("  WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")
        logger.info("或创建 .env 文件（参考 .env.example）")
        return 1

    service = DataPushService(config)
    ok = service.run(
        feishu_only=args.feishu_only,
        wechat_only=args.wechat_only,
    )

    if ok:
        logger.info("推送完成 ✅")
    else:
        logger.error("推送失败（部分或全部渠道）❌")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
