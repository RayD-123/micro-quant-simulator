import os
import pandas as pd

class LedgerManager:
    """
    量化流水账本管理器
    负责追踪每天的持仓状态（买入、持有、卖出），计算准确的持有天数与利润，并按月输出详细报表。
    """
    def __init__(self):
        self.global_ledger_log = []
        # 用于保存昨天的持仓快照，方便比对今天哪些股票被卖出了
        self.yesterday_snapshot = {}

    def record_daily_ledger(self, current_date, positions):
        """记录每日流水"""
        dt_current = pd.to_datetime(current_date).date()
        today_ledger = []
        current_snapshot = {}

        # a. 记录当前的持仓（买入 / 持有）
        for ticker, pos in positions.items():
            is_buy_today = (pos.entry_date == dt_current)
            holding_days = (dt_current - pos.entry_date).days
            
            row = {
                'Date': current_date,
                'Ticker': ticker,
                'Shares': round(pos.shares, 3), # 股数保留3位小数
                'Buy_Price': round(pos.cost_per_share, 2),
                'Status': '买入' if is_buy_today else '持有',
                'Buy_Date': str(pos.entry_date),
                'Holding_Days': holding_days,
                'Sell_Date': '-',
                'Sell_Price': '-',
                'Invested_Amount': round(pos.cost_basis, 2),
                'Net_Profit': round(pos.unrealized_pnl, 2),
                'Current_Valuation': round(pos.current_value, 2),
                'ROI': f"{pos.unrealized_pnl_pct * 100:.2f}%"
            }
            today_ledger.append(row)
            
            # 为当前持仓建立快照，明天用来比对
            current_snapshot[ticker] = {
                'shares': pos.shares,
                'cost_per_share': pos.cost_per_share,
                'entry_date': pos.entry_date,
                'cost_basis': pos.cost_basis,
                'current_price': pos.current_price
            }

        # b. 记录今天卖出的股票（昨天在手里，今天不在了）
        for ticker, old_data in self.yesterday_snapshot.items():
            if ticker not in positions:
                # 获取昨天的最新估价作为近似卖出价
                sell_px = old_data['current_price']
                sell_val = old_data['shares'] * sell_px
                realized_pnl = sell_val - old_data['cost_basis']
                roi = (realized_pnl / old_data['cost_basis']) if old_data['cost_basis'] > 0 else 0
                holding_days = (dt_current - old_data['entry_date']).days
                
                row = {
                    'Date': current_date,
                    'Ticker': ticker,
                    'Shares': round(old_data['shares'], 3),
                    'Buy_Price': round(old_data['cost_per_share'], 2),
                    'Status': '卖出',
                    'Buy_Date': str(old_data['entry_date']),
                    'Holding_Days': holding_days,
                    'Sell_Date': current_date,
                    'Sell_Price': round(sell_px, 2),
                    'Invested_Amount': round(old_data['cost_basis'], 2),
                    'Net_Profit': round(realized_pnl, 2),
                    'Current_Valuation': round(sell_val, 2),
                    'ROI': f"{roi * 100:.2f}%"
                }
                today_ledger.append(row)

        # c. 如果今天大盘空仓落袋为安，按要求显示“异常”/“空仓”
        if not today_ledger:
            today_ledger.append({
                'Date': current_date, 'Ticker': '空仓', 'Shares': 0, 'Buy_Price': 0, 
                'Status': '资金落袋为安 (空仓异常)', 'Buy_Date': '-', 'Holding_Days': 0, 
                'Sell_Date': '-', 'Sell_Price': '-', 'Invested_Amount': 0, 
                'Net_Profit': 0, 'Current_Valuation': 0, 'ROI': "0.00%"
            })
            
        # 并入总流水，并更新昨天的快照
        self.global_ledger_log.extend(today_ledger)
        self.yesterday_snapshot = current_snapshot

    def export_monthly_csv(self, output_dir="history_database"):
        """将流水记录按月切片并保存到 CSV"""
        if not self.global_ledger_log:
            print("⚠️ 账本为空，无法导出数据。")
            return
            
        df_ledger = pd.DataFrame(self.global_ledger_log)
        # 提取月份并按月分组保存
        df_ledger['Month'] = pd.to_datetime(df_ledger['Date']).dt.strftime('%Y_%m')
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        for month_str, group in df_ledger.groupby('Month'):
            group_to_save = group.drop(columns=['Month'])
            file_name = f"{output_dir}/ledger_{month_str}.csv"
            # utf-8-sig 防止 Excel 中文乱码
            group_to_save.to_csv(file_name, index=False, encoding='utf-8-sig')
            print(f"📒 月度流水账单已生成: {file_name}")
