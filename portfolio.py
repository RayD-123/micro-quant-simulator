"""
micro-quant-simulator | Module 1: Portfolio Management
=======================================================
账户记账与持仓管理核心模块

设计原则：
  - 本模块是纯粹的"账本"，只负责记录和计算，不做任何交易决策。
  - 所有状态变更必须通过显式方法调用，禁止外部直接修改属性。
  - 账户结构：
      Cash               ← 未被投资的闲置现金
      Positions          ← 持仓字典，key=Ticker，value=Position 对象
      Total Equity       ← Cash + sum(所有持仓的 current_value)，动态计算

持仓子结构（每只股票）：
  - shares            : 持有股数
  - cost_per_share    : 买入时的实际成交均价（含滑点）
  - cost_basis        : 初始总投入 = shares × cost_per_share
  - current_price     : 最新盯市价格（每日 MTM 更新）
  - current_value     : 当前市场估值 = shares × current_price
  - unrealized_pnl    : 浮动盈亏 = current_value - cost_basis
  - unrealized_pnl_pct: 浮动盈亏百分比
  - entry_date        : 建仓日期（用于 PDT Rule 检查）

风控常量（在此统一定义，供其他模块引用）：
  - INITIAL_CASH      : 初始资金 $100,000
  - MAX_POSITION_SIZE : 单只股票最大投入 $10,000
  - SLIPPAGE_BPS      : 滑点 10 bps (0.001)
  - COMMISSION        : 手续费 $0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional

# ── 日志配置 ──────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── 全局风控常量（其他模块 from portfolio import * 即可使用）──────────────────
INITIAL_CASH: float = 100_000.00
MAX_POSITION_SIZE: float = 10_000.00
SLIPPAGE_BPS: float = 0.001        # 10 bps
COMMISSION: float = 0.00           # 免佣


# ─────────────────────────────────────────────────────────────────────────────
# 数据类：单只股票的持仓快照
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Position:
    """
    代表一只股票的完整持仓信息。
    由 Portfolio 内部创建和维护，外部只读。
    """
    ticker: str
    shares: float
    cost_per_share: float       # 实际成交价（已含滑点）
    entry_date: date
    current_price: float = field(init=False)

    def __post_init__(self) -> None:
        # 初始化时，当前价格即为成交价
        self.current_price = self.cost_per_share

    # ── 派生属性（每次访问时实时计算，保证一致性）─────────────────────────────

    @property
    def cost_basis(self) -> float:
        """初始总投入（含滑点的实际买入成本）"""
        return self.shares * self.cost_per_share

    @property
    def current_value(self) -> float:
        """当前市场估值"""
        return self.shares * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        """浮动盈亏（金额）"""
        return self.current_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        """浮动盈亏百分比（基于成本）"""
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis

    def update_price(self, new_price: float) -> None:
        """
        MTM 盯市更新：用当日收盘价刷新当前持仓估值。
        由 Execution Engine 在每日收盘后调用。
        """
        if new_price <= 0:
            raise ValueError(
                f"[{self.ticker}] MTM 价格无效：{new_price}，拒绝更新。"
            )
        self.current_price = new_price

    def to_dict(self) -> dict:
        """序列化为字典，方便日志输出和报告生成"""
        return {
            "ticker": self.ticker,
            "shares": round(self.shares, 6),
            "cost_per_share": round(self.cost_per_share, 4),
            "entry_date": str(self.entry_date),
            "current_price": round(self.current_price, 4),
            "cost_basis": round(self.cost_basis, 2),
            "current_value": round(self.current_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct * 100, 2),  # 转为 %
        }

    def __repr__(self) -> str:
        return (
            f"Position({self.ticker} | "
            f"shares={self.shares:.2f} | "
            f"cost={self.cost_per_share:.2f} | "
            f"now={self.current_price:.2f} | "
            f"PnL={self.unrealized_pnl:+.2f} "
            f"({self.unrealized_pnl_pct*100:+.1f}%))"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 核心类：Portfolio（账户总账）
# ─────────────────────────────────────────────────────────────────────────────

class Portfolio:
    """
    投资组合账户的完整实现。

    职责范围（只做账本）：
      open_position()     ← 买入建仓
      close_position()    ← 卖出平仓
      update_price()      ← 每日 MTM 盯市
      has_position()      ← 查询是否持仓
      get_position()      ← 获取持仓详情
      snapshot()          ← 打印当前账户快照

    不在本模块处理的事项（交由上层模块负责）：
      - 信号读取与解析（data_feeder.py）
      - T+1 价格查询（execution_engine.py）
      - PDT Rule 检查（risk_manager.py）
    """

    def __init__(
        self,
        initial_cash: float = INITIAL_CASH,
        max_position_size: float = MAX_POSITION_SIZE,
        slippage_bps: float = SLIPPAGE_BPS,
    ) -> None:
        self._cash: float = initial_cash
        self._positions: Dict[str, Position] = {}
        self._max_position_size: float = max_position_size
        self._slippage_bps: float = slippage_bps

        # 账户初始化快照（用于最终报告计算总回报率）
        self._initial_equity: float = initial_cash

        # 交易记录流水（追加写入，用于报告生成）
        self._trade_log: list = []

        logger.info(
            f"Portfolio 初始化完成 | "
            f"初始资金={initial_cash:,.2f} | "
            f"单仓上限={max_position_size:,.2f} | "
            f"滑点={slippage_bps*10000:.0f}bps"
        )

    # ── 只读属性 ──────────────────────────────────────────────────────────────

    @property
    def cash(self) -> float:
        """账户零钱：当前可用现金"""
        return self._cash

    @property
    def positions(self) -> Dict[str, Position]:
        """当前所有持仓（只读视图）"""
        return dict(self._positions)

    @property
    def positions_value(self) -> float:
        """所有持仓的当前市场总估值"""
        return sum(pos.current_value for pos in self._positions.values())

    @property
    def total_equity(self) -> float:
        """
        总资产净值 = Cash + 所有持仓的当前市场估值
        这是账户的真实价值，每次访问时实时计算。
        """
        return self._cash + self.positions_value

    @property
    def total_unrealized_pnl(self) -> float:
        """所有持仓的浮动盈亏汇总"""
        return sum(pos.unrealized_pnl for pos in self._positions.values())

    @property
    def total_return_pct(self) -> float:
        """相对初始资金的总回报率"""
        return (self.total_equity - self._initial_equity) / self._initial_equity

    @property
    def num_positions(self) -> int:
        """当前持仓数量"""
        return len(self._positions)

    @property
    def trade_log(self) -> list:
        """返回完整交易流水（只读副本）"""
        return list(self._trade_log)

    # ── 持仓查询 ─────────────────────────────────────────────────────────────

    def has_position(self, ticker: str) -> bool:
        """检查是否持有某股票"""
        return ticker in self._positions

    def get_position(self, ticker: str) -> Optional[Position]:
        """获取某股票的持仓详情，未持有则返回 None"""
        return self._positions.get(ticker)

    # ── 核心交易方法 ──────────────────────────────────────────────────────────

    def open_position(
        self,
        ticker: str,
        execution_date: date,
        raw_open_price: float,
    ) -> Optional[Position]:
        """
        买入建仓（Next-Open 执行）。

        参数：
          ticker          : 股票代码
          execution_date  : T+1 执行日期（非信号日）
          raw_open_price  : T+1 的开盘价（来自 yfinance，未含滑点）

        执行逻辑：
          1. 检查是否已持仓（重复信号跳过）
          2. 检查 Cash 是否充足（< MAX_POSITION_SIZE 则跳过）
          3. 计算含滑点的实际成交价 = open_price × (1 + slippage_bps)
          4. 计算可买股数 = floor(MAX_POSITION_SIZE / 实际成交价)
          5. 计算实际总花费，扣减 Cash
          6. 建立 Position 对象，写入持仓字典

        返回：
          成功时返回 Position 对象，失败时返回 None 并打印跳过原因。
        """
        # ── 前置检查 ──────────────────────────────────────────────────────────

        if self.has_position(ticker):
            logger.warning(
                f"[BUY SKIPPED] {ticker} | 原因：已持仓，V1 不加仓。"
            )
            return None

        if self._cash < self._max_position_size:
            logger.warning(
                f"[BUY SKIPPED] {ticker} | 原因：现金不足。"
                f" 可用={self._cash:,.2f} < 要求={self._max_position_size:,.2f}"
            )
            return None

        if raw_open_price <= 0:
            logger.error(
                f"[BUY ERROR] {ticker} | 无效开盘价：{raw_open_price}"
            )
            return None

        # ── 价格计算（含买入滑点）─────────────────────────────────────────────

        exec_price = raw_open_price * (1 + self._slippage_bps)

        # 整股买入：用 MAX_POSITION_SIZE 计算最大可买股数
        shares = self._max_position_size // exec_price  # 向下取整

        if shares <= 0:
            logger.warning(
                f"[BUY SKIPPED] {ticker} | 原因：单价 {exec_price:.2f} "
                f"超过仓位上限 {self._max_position_size:.2f}，无法买入整股。"
            )
            return None

        actual_cost = shares * exec_price

        # ── 账户扣款 ──────────────────────────────────────────────────────────

        self._cash -= actual_cost

        # ── 建立持仓 ──────────────────────────────────────────────────────────

        position = Position(
            ticker=ticker,
            shares=shares,
            cost_per_share=exec_price,
            entry_date=execution_date,
        )
        self._positions[ticker] = position

        # ── 记录流水 ──────────────────────────────────────────────────────────

        log_entry = {
            "action": "BUY",
            "ticker": ticker,
            "date": str(execution_date),
            "raw_price": round(raw_open_price, 4),
            "exec_price": round(exec_price, 4),
            "shares": shares,
            "total_cost": round(actual_cost, 2),
            "cash_after": round(self._cash, 2),
            "equity_after": round(self.total_equity, 2),
        }
        self._trade_log.append(log_entry)

        logger.info(
            f"[BUY] {ticker} | "
            f"exec_price={exec_price:.4f} (raw={raw_open_price:.4f}) | "
            f"shares={shares:.0f} | cost={actual_cost:,.2f} | "
            f"cash_remaining={self._cash:,.2f}"
        )

        return position

    def close_position(
        self,
        ticker: str,
        execution_date: date,
        raw_open_price: float,
    ) -> Optional[dict]:
        """
        卖出平仓（Next-Open 执行）。

        参数：
          ticker          : 股票代码
          execution_date  : T+1 执行日期
          raw_open_price  : T+1 的开盘价（未含滑点）

        执行逻辑：
          1. 检查是否持仓
          2. 计算含滑点的实际卖出价 = open_price × (1 - slippage_bps)
          3. 计算卖出所得 = shares × 卖出价
          4. 将资金（含盈亏）立即归还 Cash（Margin 账户，T+0 可用）
          5. 从持仓字典中移除该 Ticker
          6. 返回本次交易的 PnL 摘要

        返回：
          包含交易摘要的字典（ticker, realized_pnl, return_pct 等）
          未持仓则返回 None。
        """
        position = self._positions.get(ticker)

        if position is None:
            logger.warning(
                f"[SELL SKIPPED] {ticker} | 原因：未持仓，无法卖出。"
            )
            return None

        if raw_open_price <= 0:
            logger.error(
                f"[SELL ERROR] {ticker} | 无效开盘价：{raw_open_price}"
            )
            return None

        # ── 价格计算（含卖出滑点）────────────────────────────────────────────

        exec_price = raw_open_price * (1 - self._slippage_bps)
        proceeds = position.shares * exec_price

        # ── 已实现盈亏 ────────────────────────────────────────────────────────

        realized_pnl = proceeds - position.cost_basis
        realized_pnl_pct = realized_pnl / position.cost_basis if position.cost_basis != 0 else 0.0

        # ── 资金立即归还 Cash ─────────────────────────────────────────────────

        self._cash += proceeds

        # ── 移除持仓 ─────────────────────────────────────────────────────────

        del self._positions[ticker]

        # ── 记录流水 ─────────────────────────────────────────────────────────

        log_entry = {
            "action": "SELL",
            "ticker": ticker,
            "date": str(execution_date),
            "entry_date": str(position.entry_date),
            "raw_price": round(raw_open_price, 4),
            "exec_price": round(exec_price, 4),
            "shares": position.shares,
            "proceeds": round(proceeds, 2),
            "cost_basis": round(position.cost_basis, 2),
            "realized_pnl": round(realized_pnl, 2),
            "realized_pnl_pct": round(realized_pnl_pct * 100, 2),
            "cash_after": round(self._cash, 2),
            "equity_after": round(self.total_equity, 2),
        }
        self._trade_log.append(log_entry)

        logger.info(
            f"[SELL] {ticker} | "
            f"exec_price={exec_price:.4f} (raw={raw_open_price:.4f}) | "
            f"proceeds={proceeds:,.2f} | "
            f"realized_pnl={realized_pnl:+,.2f} ({realized_pnl_pct*100:+.2f}%) | "
            f"cash_after={self._cash:,.2f}"
        )

        return log_entry

    def update_price(self, ticker: str, close_price: float) -> None:
        """
        每日盯市（Mark-to-Market）更新。

        由 Execution Engine 在每个交易日收盘后调用，
        用当日 Close Price 刷新持仓的 current_price，
        从而更新 current_value 和 unrealized_pnl。

        若该 Ticker 未在持仓中，静默跳过（不报错）。
        """
        position = self._positions.get(ticker)
        if position is None:
            return  # 未持仓，静默跳过
        position.update_price(close_price)

    def update_all_prices(self, price_map: Dict[str, float]) -> None:
        """
        批量盯市更新（接受 {ticker: close_price} 字典）。
        由 Execution Engine 传入当日所有持仓的收盘价。
        对 price_map 中找不到的 Ticker 发出警告但不中断。
        """
        for ticker in list(self._positions.keys()):
            if ticker in price_map:
                self.update_price(ticker, price_map[ticker])
            else:
                logger.warning(
                    f"[MTM WARNING] {ticker} | 当日收盘价缺失，MTM 未更新，"
                    f"保持上次价格 {self._positions[ticker].current_price:.4f}"
                )

    # ── 紧急平仓（极端市场事件）──────────────────────────────────────────────

    def emergency_close_all(
        self,
        execution_date: date,
        price_map: Dict[str, float],
    ) -> list:
        """
        一键紧急全平仓（仅在极端市场崩盘场景下调用，绕过 PDT Rule）。
        price_map 必须包含所有当前持仓的可执行价格。
        返回所有平仓记录的列表。
        """
        tickers = list(self._positions.keys())
        results = []
        logger.critical(
            f"[EMERGENCY CLOSE ALL] 触发紧急全平仓 | "
            f"日期={execution_date} | 持仓数={len(tickers)}"
        )
        for ticker in tickers:
            raw_price = price_map.get(ticker)
            if raw_price is None:
                logger.error(
                    f"[EMERGENCY] {ticker} | 无可用价格，跳过平仓！"
                )
                continue
            result = self.close_position(ticker, execution_date, raw_price)
            if result:
                results.append(result)
        return results

    # ── 账户快照与显示 ────────────────────────────────────────────────────────

    def snapshot(self, current_date: Optional[date] = None) -> dict:
        """
        返回当前账户完整快照（字典格式）。
        可传入 current_date 用于日志标记。
        """
        snap = {
            "date": str(current_date) if current_date else "N/A",
            "cash": round(self._cash, 2),
            "positions_value": round(self.positions_value, 2),
            "total_equity": round(self.total_equity, 2),
            "total_unrealized_pnl": round(self.total_unrealized_pnl, 2),
            "total_return_pct": round(self.total_return_pct * 100, 2),
            "num_positions": self.num_positions,
            "initial_equity": round(self._initial_equity, 2),
            "positions": {
                ticker: pos.to_dict()
                for ticker, pos in self._positions.items()
            },
        }
        return snap

    def print_snapshot(self, current_date: Optional[date] = None) -> None:
        """
        将当前账户状态格式化打印到控制台（方便调试和回测日志）。
        """
        snap = self.snapshot(current_date)
        divider = "=" * 65

        print(f"\n{divider}")
        print(f"  📊 Portfolio Snapshot  |  Date: {snap['date']}")
        print(divider)
        print(f"  💵 Cash               : ${snap['cash']:>12,.2f}")
        print(f"  📈 Positions Value    : ${snap['positions_value']:>12,.2f}")
        print(f"  🏦 Total Equity       : ${snap['total_equity']:>12,.2f}")
        print(f"  {'📉' if snap['total_unrealized_pnl'] < 0 else '📈'} "
              f"Unrealized PnL      : ${snap['total_unrealized_pnl']:>+12,.2f}")
        print(f"  🎯 Total Return       : {snap['total_return_pct']:>+11.2f}%")
        print(f"  🔢 Open Positions     : {snap['num_positions']}")

        if snap["positions"]:
            print(f"\n  {'Ticker':<8} {'Shares':>8} {'Cost':>10} "
                  f"{'Now':>10} {'Value':>10} {'PnL':>10} {'PnL%':>8}")
            print(f"  {'-'*7} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
            for t, p in snap["positions"].items():
                pnl_icon = "🟢" if p["unrealized_pnl"] >= 0 else "🔴"
                print(
                    f"  {t:<8} "
                    f"{p['shares']:>8.0f} "
                    f"{p['cost_per_share']:>10.2f} "
                    f"{p['current_price']:>10.2f} "
                    f"{p['current_value']:>10,.2f} "
                    f"{pnl_icon}{p['unrealized_pnl']:>+9,.2f} "
                    f"{p['unrealized_pnl_pct']:>+7.1f}%"
                )
        else:
            print("\n  (空仓状态 — No open positions)")

        print(divider + "\n")

    def __repr__(self) -> str:
        return (
            f"Portfolio("
            f"equity={self.total_equity:,.2f}, "
            f"cash={self._cash:,.2f}, "
            f"positions={self.num_positions})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 模块自测（python portfolio.py 直接运行时执行）
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from datetime import date

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    print("\n🧪 运行 Portfolio 模块自测...")
    print("=" * 65)

    pf = Portfolio()
    pf.print_snapshot(date(2026, 4, 1))

    # ── 测试 1：买入 LNTH ─────────────────────────────────────────────────────
    print("【测试 1】买入 LNTH @ open=$45.00")
    pf.open_position("LNTH", date(2026, 4, 2), raw_open_price=45.00)
    pf.print_snapshot(date(2026, 4, 2))

    # ── 测试 2：买入 BSM @ open=$18.50 ────────────────────────────────────────
    print("【测试 2】买入 BSM @ open=$18.50")
    pf.open_position("BSM", date(2026, 4, 2), raw_open_price=18.50)

    # ── 测试 3：重复买入 LNTH（应被跳过）──────────────────────────────────────
    print("【测试 3】重复买入 LNTH（应被跳过）")
    pf.open_position("LNTH", date(2026, 4, 2), raw_open_price=45.20)

    # ── 测试 4：MTM 盯市更新 ──────────────────────────────────────────────────
    print("【测试 4】MTM 盯市：LNTH close=$47.50，BSM close=$17.80")
    pf.update_all_prices({"LNTH": 47.50, "BSM": 17.80})
    pf.print_snapshot(date(2026, 4, 3))

    # ── 测试 5：卖出 LNTH ─────────────────────────────────────────────────────
    print("【测试 5】卖出 LNTH @ open=$48.00")
    result = pf.close_position("LNTH", date(2026, 4, 4), raw_open_price=48.00)
    if result:
        print(f"  ✅ 已实现盈亏：${result['realized_pnl']:+,.2f} "
              f"({result['realized_pnl_pct']:+.2f}%)")
    pf.print_snapshot(date(2026, 4, 4))

    # ── 测试 6：卖出未持仓股票（应被跳过）─────────────────────────────────────
    print("【测试 6】卖出 AAPL（未持仓，应被跳过）")
    pf.close_position("AAPL", date(2026, 4, 4), raw_open_price=200.00)

    # ── 测试 7：现金不足时的买入（耗尽资金场景）──────────────────────────────
    print("【测试 7】模拟大量买入后 Cash 不足...")
    for sym in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
        pf.open_position(sym, date(2026, 4, 5), raw_open_price=50.00)
    print(f"  现金剩余：${pf.cash:,.2f}")
    print("  尝试再买 J（应因资金不足被跳过）:")
    pf.open_position("J", date(2026, 4, 5), raw_open_price=50.00)

    pf.print_snapshot(date(2026, 4, 5))

    print("✅ 所有测试完成。Portfolio 模块工作正常。")
    sys.exit(0)
