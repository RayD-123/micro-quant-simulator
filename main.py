import os
import io
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

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

def run_backtest():
    print("🚀 启动 Quant Sniper 6.1 真实回测引擎 (含持仓追踪补丁)...")
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
            # 1. 找出当前持仓中，没出现在今天扫描报告里的股票
            current_holdings = list(my_portfolio.positions.keys())
            # 兼容旧代码，有些版本叫 'Signal' 有些叫 'Action'
            action_col = 'Signal' if 'Signal' in csv_signals.columns else 'Action'
            csv_tickers = csv_signals['Ticker'].tolist()
            
            missing_tickers = [t for t in current_holdings if t not in csv_tickers]
            
            if missing_tickers:
                print(f"🔍 追踪器：发现 {len(missing_tickers)} 只持仓股 ({missing_tickers}) 不在今日扫描单中。")
                
                # 为这些“失踪”股票构造补全信号
                tracker_signals = []
                for ticker in missing_tickers:
                    # 默认状态为“🟡 持有”。
                    # ExecutionEngine 收到此信号后，会强制去抓取该股当天的 Close 价格更新市值。
                    tracker_signals.append({
                        'Ticker': ticker,
                        'Sector': 'Holding-Tracker',
                        'Action': '🟡 持有',
                        'Signal': '🟡 持有'
                    })
                
                # 将补全信号合并进今日信号包
                if tracker_signals:
                    df_missing = pd.DataFrame(tracker_signals)
                    csv_signals = pd.concat([csv_signals, df_missing], ignore_index=True)

            # 3. 将完整的信号包（扫描结果 + 追踪补位）喂给引擎执行
            result = engine.step(current_date, csv_signals)
            
            # 打印每日审计行
            equity = my_portfolio.total_equity
            pos_count = len(my_portfolio.positions)
            print(f"📅 {current_date} | 净值: ${equity:>12,.2f} | 持仓: {pos_count} 支")
            
            # 记录历史用于生成报表
            daily_equity_log.append({'Date': str(current_date), 'Equity': equity})
            
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
        print(f"结果已保存至: daily_equity.csv")

if __name__ == "__main__":
    run_backtest()
