# -*- coding: utf-8 -*-
"""
==================================================
opp-001 纯数据采集脚本（已剥离 AI 分析/买卖建议）
==================================================

基于 Akshare (东方财富/新浪/腾讯) 免费数据源,仅做客观数据抓取:
- 日线 K 线数据 (开/高/低/收/量/额)
- 实时行情 (价格/涨跌幅/量比/换手率/PE/PB/市值)
- 大盘指数行情
- 市场涨跌统计
- 行业板块排名
- 成交量异常检测 (仅客观倍数)

合规声明:
  本脚本仅提供客观市场数据,不包含任何投资分析、预测或建议。

数据来源: AkShare (东方财富/新浪/腾讯), 免费无需 Token
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd

# 将原项目的根目录加入 sys.path,以便导入 data_provider 模块
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opp-001-daily-stock")
sys.path.insert(0, REPO_ROOT)

from data_provider.akshare_fetcher import AkshareFetcher

# ============================================================
# 合规声明 (每条输出强制附带)
# ============================================================
COMPLIANCE_DISCLAIMER = (
    "以上数据仅供参考,不构成投资建议。投资有风险,入市需谨慎。\n"
    "数据来源: AkShare / 东方财富"
)


# ============================================================
# 默认自选股列表 (纯示例,按需修改)
# ============================================================
DEFAULT_WATCHLIST = [
    "600519",   # 贵州茅台
    "000001",   # 平安银行
    "000858",   # 五粮液
    "300750",   # 宁德时代
    "688981",   # 中芯国际
]


# ============================================================
# 核心数据获取类
# ============================================================

class PureDataFetcher:
    """
    纯数据采集器 —— 只拉客观数据,不做任何分析/预测/建议。

    设计原则:
    - 只输出事实性数据 (价格/成交量/涨跌幅等)
    - 不输出任何形式的 "建议/评分/结论"
    - 所有输出末尾附加合规声明
    """

    def __init__(self, watchlist: Optional[List[str]] = None):
        self.watchlist = watchlist or DEFAULT_WATCHLIST
        self.fetcher = AkshareFetcher()

    # ---- 日线历史数据 ----

    def fetch_daily_kline(
        self, stock_code: str, days: int = 30
    ) -> Optional[pd.DataFrame]:
        """
        获取单只股票日线 K 线数据 (仅客观数据,无技术分析结论)。

        返回字段: date, open, high, low, close, volume, amount, pct_chg
        """
        try:
            df = self.fetcher.get_daily_data(stock_code, days=days)
            print(f"[{stock_code}] 日线数据获取成功 ({len(df)} 条)")
            return df
        except Exception as e:
            print(f"[{stock_code}] 日线数据获取失败: {e}")
            return None

    def fetch_all_daily_klines(self, days: int = 30) -> Dict[str, pd.DataFrame]:
        """批量获取自选股日线数据"""
        results = {}
        for code in self.watchlist:
            df = self.fetch_daily_kline(code, days=days)
            if df is not None:
                results[code] = df
        return results

    # ---- 实时行情 ----

    def fetch_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票实时行情 (仅客观数据)。

        返回字段: 代码, 名称, 最新价, 涨跌幅, 涨跌额, 成交量, 成交额,
                  量比, 换手率, 振幅, 今开, 最高, 最低, PE, PB, 总市值, 流通市值
        """
        try:
            quote = self.fetcher.get_realtime_quote(stock_code)
            if quote is None:
                print(f"[{stock_code}] 实时行情暂无数据 (可能停牌或非交易时段)")
                return None

            data = {
                "代码": quote.code,
                "名称": getattr(quote, "name", ""),
                "最新价": getattr(quote, "price", None),
                "涨跌幅(%)": getattr(quote, "change_pct", None),
                "涨跌额": getattr(quote, "change_amount", None),
                "成交量(股)": getattr(quote, "volume", None),
                "成交额(元)": getattr(quote, "amount", None),
                "量比": getattr(quote, "volume_ratio", None),
                "换手率(%)": getattr(quote, "turnover_rate", None),
                "振幅(%)": getattr(quote, "amplitude", None),
                "今开": getattr(quote, "open_price", None),
                "最高": getattr(quote, "high", None),
                "最低": getattr(quote, "low", None),
                "市盈率": getattr(quote, "pe_ratio", None),
                "市净率": getattr(quote, "pb_ratio", None),
                "总市值": getattr(quote, "total_mv", None),
                "流通市值": getattr(quote, "circ_mv", None),
            }
            print(f"[{stock_code}] {data['名称']} 实时行情获取成功")
            return data
        except Exception as e:
            print(f"[{stock_code}] 实时行情获取失败: {e}")
            return None

    def fetch_all_realtime_quotes(self) -> List[Dict[str, Any]]:
        """批量获取自选股实时行情"""
        results = []
        for code in self.watchlist:
            quote = self.fetch_realtime_quote(code)
            if quote is not None:
                results.append(quote)
        return results

    # ---- 大盘指数 ----

    def fetch_major_indices(self) -> List[Dict[str, Any]]:
        """获取主要大盘指数实时行情 (使用新浪接口)"""
        try:
            indices = self.fetcher.get_main_indices(region="cn")
            if not indices:
                print("大盘指数数据为空")
                return []
            print(f"大盘指数获取成功 ({len(indices)} 个)")
            return indices
        except Exception as e:
            print(f"大盘指数获取失败: {e}")
            return []

    # ---- 市场涨跌统计 ----

    def fetch_market_stats(self) -> Optional[Dict[str, Any]]:
        """获取市场涨跌统计 (上涨/下跌/平盘/涨停/跌停家数 + 两市成交额)"""
        try:
            stats = self.fetcher.get_market_stats()
            if not stats:
                print("市场统计暂无数据")
                return None

            result = {
                "上涨家数": stats.get("up_count", 0),
                "下跌家数": stats.get("down_count", 0),
                "平盘家数": stats.get("flat_count", 0),
                "涨停家数": stats.get("limit_up_count", 0),
                "跌停家数": stats.get("limit_down_count", 0),
                "两市成交额(亿)": round(stats.get("total_amount", 0), 2),
            }
            print(f"市场统计获取成功 (上涨:{result['上涨家数']} 下跌:{result['下跌家数']})")
            return result
        except Exception as e:
            print(f"市场统计获取失败: {e}")
            return None

    # ---- 行业板块排名 ----

    def fetch_sector_rankings(self, top_n: int = 5) -> Optional[Dict[str, List]]:
        """获取行业板块涨跌幅排名 (仅列事实,不推荐板块)"""
        try:
            rankings = self.fetcher.get_sector_rankings(n=top_n)
            if rankings is None:
                print("板块排名暂无数据")
                return None

            top, bottom = rankings
            result = {
                "领涨板块": top,
                "领跌板块": bottom,
            }
            print(f"板块排名获取成功 (领涨:{len(top)} 领跌:{len(bottom)})")
            return result
        except Exception as e:
            print(f"板块排名获取失败: {e}")
            return None

    # ---- 成交量检测 (仅客观倍数,不解读为"主力进场/出货") ----

    def fetch_volume_surge(
        self, stock_code: str, days: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        检测成交量较前5日均量的倍数 (仅客观数据)。
        """
        try:
            df = self.fetcher.get_daily_data(stock_code, days=days + 5)
            if df is None or len(df) < 2:
                return None

            latest = df.iloc[-1]
            avg_vol_prev5 = df.iloc[:-1]["volume"].tail(5).mean()

            volume_ratio = (
                latest["volume"] / avg_vol_prev5 if avg_vol_prev5 > 0 else 1.0
            )

            result = {
                "代码": stock_code,
                "日期": str(latest.get("date", ""))[:10],
                "今日成交量(股)": int(latest["volume"]),
                "前5日均量(股)": int(avg_vol_prev5),
                "量比": round(volume_ratio, 2),
                "今日成交额(元)": round(float(latest.get("amount", 0)), 2),
            }
            return result
        except Exception as e:
            print(f"[{stock_code}] 成交量分析失败: {e}")
            return None

    # ---- 综合数据报告 ----

    def generate_data_report(self) -> str:
        """
        生成纯数据综合报告 (无 AI 分析,无买卖建议)。

        此报告只陈述客观事实,符合监管要求。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = []
        lines.append("=" * 60)
        lines.append(f"  A股市场数据报告 (纯数据,非投资建议)")
        lines.append(f"  生成时间: {now}")
        lines.append("=" * 60)

        # 1. 大盘指数
        lines.append("\n【一、主要指数】")
        indices = self.fetch_major_indices()
        if indices:
            for idx in indices:
                name = idx.get("name", "")
                current = idx.get("current", 0)
                change_pct = idx.get("change_pct", 0)
                sign = "+" if change_pct >= 0 else ""
                lines.append(
                    f"  {name}: {current:.2f}  涨跌幅: {sign}{change_pct:.2f}%"
                )

        # 2. 市场统计
        lines.append("\n【二、市场全景】")
        stats = self.fetch_market_stats()
        if stats:
            lines.append(f"  上涨: {stats['上涨家数']} 家")
            lines.append(f"  下跌: {stats['下跌家数']} 家")
            lines.append(f"  平盘: {stats['平盘家数']} 家")
            lines.append(f"  涨停: {stats['涨停家数']} 家")
            lines.append(f"  跌停: {stats['跌停家数']} 家")
            lines.append(f"  两市成交额: {stats['两市成交额(亿)']} 亿元")

        # 3. 板块排名
        lines.append("\n【三、行业板块排名】")
        sectors = self.fetch_sector_rankings(top_n=5)
        if sectors:
            lines.append("  领涨板块:")
            for s in sectors["领涨板块"]:
                lines.append(f"    {s['name']}: +{s['change_pct']:.2f}%")
            lines.append("  领跌板块:")
            for s in sectors["领跌板块"]:
                lines.append(f"    {s['name']}: {s['change_pct']:.2f}%")

        # 4. 自选股实时行情
        lines.append("\n【四、自选股实时行情】")
        quotes = self.fetch_all_realtime_quotes()
        if quotes:
            header = (
                f"  {'代码':<10} {'名称':<10} {'最新价':>8} "
                f"{'涨跌幅':>8} {'量比':>6} {'换手率':>8} {'PE':>8}"
            )
            lines.append(header)
            lines.append("  " + "-" * 60)
            for q in quotes:
                price = q.get("最新价", 0) or 0
                change = q.get("涨跌幅(%)", 0) or 0
                vol_ratio = q.get("量比", 0) or 0
                turnover = q.get("换手率(%)", 0) or 0
                pe = q.get("市盈率", 0) or 0

                sign = "+" if change >= 0 else ""
                lines.append(
                    f"  {q['代码']:<10} {q['名称']:<10} {price:>8.2f} "
                    f"{sign}{change:>7.2f}% {vol_ratio:>6.2f} "
                    f"{turnover:>8.2f}% {pe:>8.2f}"
                )

        # 5. 合规声明
        lines.append("\n" + "-" * 60)
        lines.append(COMPLIANCE_DISCLAIMER)
        lines.append("=" * 60)

        return "\n".join(lines)


# ============================================================
# 独立运行入口
# ============================================================

def main():
    """拉取自选股数据并打印报告"""
    print("opp-001 纯数据采集脚本启动中...")
    print(f"自选股列表: {', '.join(DEFAULT_WATCHLIST)}")
    print(f"日期: {datetime.now().strftime('%Y-%m-%d')}")
    print()

    fetcher = PureDataFetcher(watchlist=DEFAULT_WATCHLIST)

    # Step 1: 先拉日线数据 (最稳定,不受交易时段限制)
    print("=" * 60)
    print("【日线数据 (最近 3 个交易日)】")
    print("-" * 60)
    for code in DEFAULT_WATCHLIST:
        df = fetcher.fetch_daily_kline(code, days=30)
        if df is not None and len(df) >= 3:
            print(f"\n  {code} (最近 3 条日线):")
            display_cols = ["date", "close", "volume", "amount", "pct_chg"]
            available = [c for c in display_cols if c in df.columns]
            print(df[available].tail(3).to_string(index=False))
        else:
            print(f"\n  {code}: 数据不足")

    # Step 2: 综合报告 (含实时行情,交易时段才有完整数据)
    print("\n")
    report = fetcher.generate_data_report()
    print(report)


if __name__ == "__main__":
    main()
