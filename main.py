import os
import io
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# 导入绘图库
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import seaborn as sns
    HAS_PLOT_LIBS = True
except ImportError:
    HAS_PLOT_LIBS = False
    print("⚠️ 警告: 未找到 matplotlib 或 seaborn，将只生成 CSV 不生成图表。")
    print("👉 请在终端运行: pip install matplotlib seaborn")

# 导入我们的“量化三剑客”
from portfolio import Portfolio
from data_feeder import DataFeeder
from execution_engine import ExecutionEngine

def load_all_csvs(folder_path="history_database"):
    """自动读取目录下所有的历史 CSV 文件并按时间拼接"""
    if not os.path.exists(folder_path):
        print(f"⚠️ 找不到目录 '{folder_path}'，尝试从当前目录寻找 CSV...")
        folder_path = "."
        
    csv_files = [f for f in os.listdir(folder_path) if f.startswith('data_') and f.endswith('.csv')]
    csv_files.sort() # 确保时间顺序
    
    if not csv_files:
        raise FileNotFoundError("❌ 没找到任何历史数据文件 (data_*.csv)！")
        
    print(f"📂 发现 {len(csv_files)} 个数据文件: {csv_files}")
    dfs = [pd.read_csv(os.path.join(folder_path, f)) for f in csv_files]
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # 转换为内存中的文件流，喂给 DataFeeder
    csv_buffer = io.StringIO()
    combined_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer

def plot_equity_and_cash(df):
    """生成美观的净值与零钱折线图"""
    if not HAS_PLOT_LIBS:
        return
        
    sns.set_theme(style="whitegrid")
    df_plot = df.copy()
    df_plot['Date'] = pd.to_datetime(df_plot['Date'])
    
    plt.figure(figsize=(12, 6), dpi=120)
    
    # 绘制主曲线：总资产 (Equity)
    plt.plot(df_plot['Date'], df_plot['Equity'], color='#2E7D32', linewidth=2, label='Total Equity (Assets + Cash)')
    # 填充曲线下方区域
    plt.fill_between(df_plot['Date'], df_plot['Equity'], df_plot['Equity'].min()*0.98, color='#81C784', alpha=0.2)
    
    # 绘制结余线 (Cash) 作为对比（虚线）
    plt.plot(df_plot['Date'], df_plot['Cash'], color='#1976D2', linewidth=1.2, linestyle='--', alpha=0.7, label='Idle Cash (Balance)')

    plt.title('Trading System Performance - Equity Curve', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Trading Date', fontsize=12)
    plt.ylabel('Valuation (USD)', fontsize=12)
    
    # 格式化横坐标（显示日期，剔除周末空白）
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45)
    
    plt.legend(loc='upper left', frameon=True)
    
    # 添加收益率标注
    final_return = (df_plot['Equity'].iloc[-1] - df_plot['Equity'].iloc[0]) / df_plot['Equity'].iloc[0] * 100
    plt.annotate(f'Total Return: {final_return:+.2f}%', 
                 xy=(0.02, 0.92), xycoords='axes fraction',
                 fontsize=11, color='darkgreen', fontweight='bold')

    plt.tight_layout()
    plt.savefig("equity_curve_report.png")
    print(f"🎨 美化图表已生成：equity_curve_report.png")

def run_backtest():
    print("🚀 启动 Quant Sniper 6.1 真实回测引擎 (含持仓追踪与资金绘图补丁)...")
    print("=" * 65)

    # 1. 初始化组件
    csv_stream = load_all_csvs()
    feeder = DataFeeder(csv_stream)
    my_portfolio = Portfolio()
    engine = ExecutionEngine(portfolio=my_portfolio)

    daily_equity_log = []

    # 2. 核心回放循环
    try:
        while True:
            # 获取下一天的数据信号
            current_date, csv_signals = feeder.get_next_batch()
            
            # --- 【新增逻辑：持仓监控追踪器】 ---
            current_holdings = list(my_portfolio.positions.keys())
            action_col = 'Signal' if 'Signal' in csv_signals.columns else 'Action'
            csv_tickers = csv_signals['Ticker'].tolist()
            
            missing_tickers = [t for t in current_holdings if t not in csv_tickers]
            
            if missing_tickers:
                # 只在后台处理，避免打印过多杂音，如果需要打印可解开下面注释
                # print(f"🔍 追踪器：发现 {len(missing_tickers)} 只持仓股 ({missing_tickers}) 不在今日扫描单中。")
                
                tracker_signals = []
                for ticker in missing_tickers:
                    tracker_signals.append({
                        'Ticker': ticker,
                        'Sector': 'Holding-Tracker',
                        'Action': '🟡 持有',
                        'Signal': '🟡 持有'
                    })
                
                if tracker_signals:
                    df_missing = pd.DataFrame(tracker_signals)
                    csv_signals = pd.concat([csv_signals, df_missing], ignore_index=True)

            # 3. 将完整的信号包（扫描结果 + 追踪补位）喂给引擎执行
            result = engine.step(current_date, csv_signals)
            
            # 获取最新净值和零钱
            equity = my_portfolio.total_equity
            cash = my_portfolio.cash
            pos_count = len(my_portfolio.positions)
            
            # 打印每日审计行 (增加了零钱展示)
            print(f"📅 {current_date} | 净值: ${equity:>10,.2f} | 零钱: ${cash:>9,.2f} | 持仓: {pos_count} 支")
            
            # 记录历史用于生成报表 (新增 Cash 字段)
            daily_equity_log.append({
                'Date': str(current_date), 
                'Equity': equity,
                'Cash': cash
            })
            
    except StopIteration:
        print("\n🛑 历史信号回放完毕！")
        if hasattr(engine, 'flush_pending_orders'):
            engine.flush_pending_orders()
    except Exception as e:
        print(f"\n❌ 回测中断，遇到错误: {e}")

    # 4. 统计与审计报告
    print("\n" + "=" * 65)
    print("📊 Quant Sniper 6.1 回测业绩终期审计报告")
    print("=" * 65)
    
    if daily_equity_log:
        df_equity = pd.DataFrame(daily_equity_log)
        
        # 覆盖保存原有的 CSV 文件 (现在多了 Cash 列)
        df_equity.to_csv("daily_equity.csv", index=False)
        
        initial_capital = df_equity['Equity'].iloc[0]
        final_capital = df_equity['Equity'].iloc[-1]
        total_return = ((final_capital - initial_capital) / initial_capital) * 100
        
        # 计算最大回撤 (Max Drawdown)
        df_equity['Peak'] = df_equity['Equity'].cummax()
        df_equity['Drawdown'] = (df_equity['Equity'] - df_equity['Peak']) / df_equity['Peak']
        max_drawdown = df_equity['Drawdown'].min() * 100
        
        print(f"起始资金: ${initial_capital:,.2f}")
        print(f"最终净值: ${final_capital:,.2f}")
        print(f"累计收益: {total_return:+.2f}%")
        print(f"最大回撤: {max_drawdown:.2f}%")
        print(f"📄 数据已覆盖保存至: daily_equity.csv (已包含 Cash 零钱列)")
        
        # 调用绘图函数
        plot_equity_and_cash(df_equity)

if __name__ == "__main__":
    run_backtest()
