import os
import io
import warnings
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime

# 屏蔽 yfinance 冗余输出
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

# 核心组件导入 (请确保这些文件在同一目录下)
from portfolio import Portfolio
from data_feeder import DataFeeder
from execution_engine import ExecutionEngine
from ledger_manager import LedgerManager 

def load_all_csvs(folder_path="history_database"):
    """自动读取目录下所有的历史 CSV 文件并按时间拼接"""
    if not os.path.exists(folder_path):
        folder_path = "."
    csv_files = [f for f in os.listdir(folder_path) if f.startswith('data_') and f.endswith('.csv')]
    csv_files.sort()
    if not csv_files:
        raise FileNotFoundError("❌ 没找到任何历史数据文件 (data_*.csv)！")
    
    print(f"📂 正在加载数据文件: {csv_files}")
    dfs = [pd.read_csv(os.path.join(folder_path, f)) for f in csv_files]
    combined_df = pd.concat(dfs, ignore_index=True)
    
    csv_buffer = io.StringIO()
    combined_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer

def run_backtest():
    print("🚀 启动 Quant Sniper 6.5 [专业审计版]...")
    print("=" * 65)

    # 1. 初始化
    csv_stream = load_all_csvs()
    feeder = DataFeeder(csv_stream)
    my_portfolio = Portfolio()
    engine = ExecutionEngine(portfolio=my_portfolio)
    ledger = LedgerManager() 
    
    initial_fund = 100000.0  # 初始本金
    daily_equity_log = []
    system_today = datetime.now().date()

    try:
        while True:
            current_date, csv_signals = feeder.get_next_batch()
            
            # 日期安全过滤
            dt_obj = pd.to_datetime(current_date)
            test_date = dt_obj.date()
            if test_date >= system_today: break
            if dt_obj.weekday() >= 5: continue

            # 信号补全逻辑（维持旧持仓状态）
            current_holdings = list(my_portfolio.positions.keys())
            csv_tickers = csv_signals['Ticker'].tolist()
            missing = [t for t in current_holdings if t not in csv_tickers]
            if missing:
                tracker = [{'Ticker': t, 'Action': '🟡 持有'} for t in missing]
                csv_signals = pd.concat([csv_signals, pd.DataFrame(tracker)], ignore_index=True)

            # 2. 执行交易与更新市值
            engine.step(current_date, csv_signals)
            ledger.record_daily_ledger(current_date, my_portfolio.positions)

            # 3. 精准审计计算 (用户要求的四列)
            total_assets = my_portfolio.total_equity
            cash_bal = my_portfolio.cash
            eval_equity = total_assets - cash_bal               # 第一列：持仓估值
            roi = (total_assets - initial_fund) / initial_fund  # 第四列：收益率
            
            # 打印进度
            print(f"📅 {current_date} | 总资产: ${total_assets:>10,.2f} | 收益率: {roi*100:+.2f}%")

            # 记录数据
            daily_equity_log.append({
                'Evaluated_Equity': round(eval_equity, 2), # 1. 持仓估值
                'Cash_Balance': round(cash_bal, 2),        # 2. 现金结余
                'Total_Assets': round(total_assets, 2),    # 3. 总资产
                'ROI_Pct': f"{roi*100:.2f}%",              # 4. 收益率百分数
                'Date': str(current_date)                  # 时间戳（放在最后供画图调用）
            })
            
    except StopIteration:
        pass
    except Exception as e:
        print(f"\n❌ 回测中断: {e}")

    # 4. 导出账本记录
    ledger.export_monthly_csv("history_database")

    # 5. 导出审计报表
    if daily_equity_log:
        df_equity = pd.DataFrame(daily_equity_log)
        # 按照你要求的顺序排列列
        df_equity = df_equity[['Evaluated_Equity', 'Cash_Balance', 'Total_Assets', 'ROI_Pct', 'Date']]
        df_equity.to_csv("daily_equity.csv", index=False)
        
        print("\n" + "=" * 65)
        print(f"✅ 审计完成！报表已生成: daily_equity.csv")
        print(f"📈 最终总资产: ${my_portfolio.total_equity:,.2f}")
        print("=" * 65)
        print("👉 请运行 'python visualizer.py' 生成分析图表。")

if __name__ == "__main__":
    run_backtest()
