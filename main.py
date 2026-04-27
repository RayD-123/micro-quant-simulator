import os
import io
import warnings
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime

# 屏蔽 yfinance 在周末或缺失数据时的神经病报错输出
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import seaborn as sns
    HAS_PLOT_LIBS = True
except ImportError:
    HAS_PLOT_LIBS = False

from portfolio import Portfolio
from data_feeder import DataFeeder
from execution_engine import ExecutionEngine
from ledger_manager import LedgerManager  # 导入我们刚刚分离的独立账本模块

def load_all_csvs(folder_path="history_database"):
    if not os.path.exists(folder_path):
        folder_path = "."
    csv_files = [f for f in os.listdir(folder_path) if f.startswith('data_') and f.endswith('.csv')]
    csv_files.sort()
    if not csv_files:
        raise FileNotFoundError("❌ 没找到任何历史数据文件 (data_*.csv)！")
    dfs = [pd.read_csv(os.path.join(folder_path, f)) for f in csv_files]
    combined_df = pd.concat(dfs, ignore_index=True)
    csv_buffer = io.StringIO()
    combined_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer

def plot_equity_and_cash(df):
    if not HAS_PLOT_LIBS: return
    sns.set_theme(style="whitegrid")
    df_plot = df.copy()
    df_plot['Date'] = pd.to_datetime(df_plot['Date'])
    
    plt.figure(figsize=(12, 6), dpi=120)
    plt.plot(df_plot['Date'], df_plot['Equity'], color='#2E7D32', linewidth=2, label='Total Equity')
    plt.fill_between(df_plot['Date'], df_plot['Equity'], df_plot['Equity'].min()*0.98, color='#81C784', alpha=0.2)
    plt.plot(df_plot['Date'], df_plot['Cash'], color='#1976D2', linewidth=1.2, linestyle='--', alpha=0.7, label='Idle Cash')

    plt.title('Trading System Performance - Equity Curve', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Trading Date', fontsize=12)
    plt.ylabel('Valuation (USD)', fontsize=12)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45)
    plt.legend(loc='upper left', frameon=True)
    
    final_return = (df_plot['Equity'].iloc[-1] - df_plot['Equity'].iloc[0]) / df_plot['Equity'].iloc[0] * 100
    plt.annotate(f'Total Return: {final_return:+.2f}%', xy=(0.02, 0.92), xycoords='axes fraction', fontsize=11, color='darkgreen', fontweight='bold')
    plt.tight_layout()
    plt.savefig("equity_curve_report.png")

def run_backtest():
    print("🚀 启动 Quant Sniper 6.4 [模块化独立账本 + 风控修复版]...")
    print("=" * 65)

    csv_stream = load_all_csvs()
    feeder = DataFeeder(csv_stream)
    my_portfolio = Portfolio()
    engine = ExecutionEngine(portfolio=my_portfolio)
    ledger = LedgerManager()  # 初始化独立的账本管理器

    daily_equity_log = []
    system_today = datetime.now().date()

    try:
        while True:
            current_date, csv_signals = feeder.get_next_batch()
            
            # 【修复 1】: 日期过滤（拦截未来日期和周末）
            dt_obj = pd.to_datetime(current_date)
            test_date = dt_obj.date()
            if test_date >= system_today:
                break
            if dt_obj.weekday() >= 5: # 5是周六，6是周日
                continue

            # 补充缺失信号维持持仓状态
            current_holdings = list(my_portfolio.positions.keys())
            csv_tickers = csv_signals['Ticker'].tolist()
            missing = [t for t in current_holdings if t not in csv_tickers]
            if missing:
                tracker = [{'Ticker': t, 'Action': '🟡 持有'} for t in missing]
                csv_signals = pd.concat([csv_signals, pd.DataFrame(tracker)], ignore_index=True)

            # 让引擎执行当天的交易并更新市值
            engine.step(current_date, csv_signals)
            
            # 【核心剥离】调用独立的账本管理器记录今天的所有流水操作
            ledger.record_daily_ledger(current_date, my_portfolio.positions)

            # 打印与记录总净值
            equity = my_portfolio.total_equity
            cash = my_portfolio.cash
            pos_count = len(my_portfolio.positions)
            print(f"📅 {current_date} | 资产总值: ${equity:>10,.2f} | 剩余零钱: ${cash:>9,.2f} | 持仓: {pos_count}/10 支")
            daily_equity_log.append({'Date': str(current_date), 'Equity': equity, 'Cash': cash})
            
    except StopIteration:
        pass
    except Exception as e:
        print(f"\n❌ 回测异常: {e}")

    # =========================================================
    # 回测结束：输出最终报告
    # =========================================================
    
    # 调用账本管理器按月导出流水记录
    ledger.export_monthly_csv("history_database")

    if daily_equity_log:
        df_equity = pd.DataFrame(daily_equity_log)
        df_equity.to_csv("daily_equity.csv", index=False)
        final_cap = df_equity['Equity'].iloc[-1]
        total_ret = ((final_cap - 100000) / 100000) * 100
        print("\n" + "=" * 65)
        print(f"📊 最终审计：累计收益 {total_ret:+.2f}% | 零钱结余: ${my_portfolio.cash:,.2f}")
        print("=" * 65)
        plot_equity_and_cash(df_equity)

if __name__ == "__main__":
    run_backtest()
