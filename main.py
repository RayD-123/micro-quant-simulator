import os
import io
import pandas as pd
from datetime import datetime

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
    csv_files.sort() # 确保 3 月在 4 月前面
    
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
    print("🚀 启动 Quant Sniper 6.1 真实回测引擎...")
    print("=" * 60)
    
    # 1. 组装数据燃料
    csv_buffer = load_all_csvs("history_database")
    
    # 2. 实例化系统组件
    print("📦 正在初始化账本、时间机器和交易员...")
    pf = Portfolio()
    feeder = DataFeeder(csv_buffer)
    
    # 注意：这里我们不传 mock_prices，让引擎自动使用 yfinance 获取真实历史数据
    engine = ExecutionEngine(portfolio=pf, data_feeder=feeder)
    
    # 用于画图的每日资产记录
    daily_equity_log = []
    
    print("\n" + "-" * 65)
    print(f"{'日期 (Date)':<15} | {'总资产 (Total Equity)':<20} | {'当前持仓数':<10}")
    print("-" * 65)
    
    # 3. 开启“时光机”主循环
    try:
        while True:
            # DataFeeder 和 Engine 的交互逻辑
            # 注意：Claude 设计的 engine.step() 内部其实调用了 feeder.get_next_batch()
            # 如果 Claude 的版本需要传参数，请根据实际情况调整，这里假设使用 Claude 最新的设计：
            engine.step() 
            
            # 安全地获取当前的总资产和持仓数（适配 Claude 的私有变量设计）
            # Claude 提到变量是私有的(_cash, _positions)，并且应该有 property 暴露
            equity = getattr(pf, 'total_equity', 100000.0) 
            # 如果 Claude 没有暴露 total_equity 属性，我们手动计算兜底：
            if not hasattr(pf, 'total_equity'):
                cash = getattr(pf, '_cash', 100000.0)
                positions = getattr(pf, '_positions', {})
                equity = cash + sum(pos.current_value for pos in positions.values())
            
            positions_dict = getattr(pf, '_positions', getattr(pf, 'positions', {}))
            pos_count = len(positions_dict)
            
            # 获取最近处理的日期 (兜底策略)
            current_date = getattr(engine, 'last_signal_date', "Running...")
            
            print(f"{str(current_date):<15} | ${equity:>12,.2f} {'':<6} | {pos_count} 支股票")
            
            # 记录下来用于算回撤
            daily_equity_log.append({'Date': str(current_date), 'Equity': equity})
            
    except StopIteration:
        print("\n🛑 历史信号回放完毕！")
        if hasattr(engine, 'flush_pending_orders'):
            print("⏳ 正在清理最后一日的挂单...")
            engine.flush_pending_orders()
    except Exception as e:
        print(f"\n❌ 回测中断，遇到错误: {e}")

    # 4. 统计与审计
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
        
        print(f"💰 初始本金:   ${initial_capital:,.2f}")
        print(f"🏦 最终总资产: ${final_capital:,.2f}")
        print(f"📈 累计收益率: {total_return:+.2f}%")
        print(f"📉 最大回撤:   {max_drawdown:.2f}% (数字越接近0越抗跌)")
        print(f"\n✅ 每日资产曲线已导出至当前目录的 'daily_equity.csv'")
    else:
        print("⚠️ 回测未产生有效数据。")
    print("=" * 65)

if __name__ == "__main__":
    run_backtest()
