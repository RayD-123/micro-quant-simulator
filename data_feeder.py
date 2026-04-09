import pandas as pd
import os
import io

class DataFeeder:
    """
    micro-quant-simulator | Module 2: Data Feeder
    =======================================================
    事件驱动回测引擎的“时间机器”。
    严格按照物理追加顺序，逐批次吐出历史信号，坚决杜绝未来函数。
    本模块纯粹是“发牌机器”，不含任何资金或买卖计算逻辑。
    """
    def __init__(self, file_path_or_buffer):
        self.source = file_path_or_buffer
        self.data = self._clean_and_batch_data()
        
        # 将按 batch_id 分组的数据预先存储为列表，方便迭代
        self.batches = [group for _, group in self.data.groupby('batch_id')]
        self.current_idx = 0
        self.total_batches = len(self.batches)

    def _clean_and_batch_data(self):
        """清洗数据并生成批次 ID"""
        # 读取数据 (支持文件路径或 StringIO buffer 方便测试)
        if isinstance(self.source, str) and not os.path.exists(self.source):
            raise FileNotFoundError(f"⚠️ 找不到数据文件: {self.source}")
        
        df = pd.read_csv(self.source)

        # 1. 清理异常/空缺行
        df = df.dropna(subset=['Date', 'Ticker', 'Action']).copy()

        # 2. 规范化 Action 字段 (提取标准机器可读信号)
        def parse_signal(action_str):
            action_str = str(action_str)
            if 'Buy' in action_str or '买入' in action_str or '🟢' in action_str:
                return 'Buy'
            elif 'Sell' in action_str or '止盈' in action_str or '卖出' in action_str or '🔴' in action_str:
                return 'Sell'
            else:
                return 'Hold'
                
        df['Signal'] = df['Action'].apply(parse_signal)

        # 3. 核心：基于物理连续性划分批次 (Batch ID)
        # 只要 Date 发生变化，就产生一个新的批次。
        # 这样同一天的 AM 和 PM 数据如果物理上连在一起，会自动划入同一个 Batch，非常适合 T+1 统一执行。
        df['batch_id'] = (df['Date'] != df['Date'].shift()).cumsum()

        # 4. 批次内去重：如果同一天同一次运行中，某只股票出现了两次，保留最后一次状态
        df = df.drop_duplicates(subset=['batch_id', 'Ticker'], keep='last')

        return df

    def get_next_batch(self):
        """
        核心接口：每次调用，时间机器往前走一天。
        返回: (当前批次日期字符串, 包含该批次所有信号的 DataFrame)
        """
        if self.current_idx < self.total_batches:
            batch_df = self.batches[self.current_idx]
            batch_date = batch_df['Date'].iloc[0]
            self.current_idx += 1
            
            # 只吐出核心决策列，隐藏批次ID等内部字段，确保引擎只拿到该拿的
            output_df = batch_df[['Ticker', 'Sector', 'PE', 'ROE', 'Momentum', 'RSI', 'Signal']].copy()
            return batch_date, output_df
        else:
            raise StopIteration("🛑 所有历史数据已回放完毕！")

    def reset(self):
        """重置时间机器，方便重复跑回测"""
        self.current_idx = 0


# ==========================================
# 🧪 自测模块 (可以直接运行此文件进行测试)
# ==========================================
if __name__ == "__main__":
    print("🚀 启动 DataFeeder 模块自测...\n")

    # 模拟一份我们 Lab 2 产出的 CSV 数据 (包含同一天的多次扫描)
    mock_csv_data = """Date,Ticker,Sector,PE,ROE,Momentum,RSI,Action
2026-04-01,AAPL,Tech,24.5,25%,0.05,35,🟢 Buy
2026-04-01,MSFT,Tech,30.1,20%,0.03,45,🟡 Hold
2026-04-01,TSLA,Auto,45.0,15%,0.08,38,🟢 Buy
2026-04-02,AAPL,Tech,24.5,25%,0.06,78,🔴 Sell
2026-04-02,NVDA,Tech,35.0,30%,0.10,30,🟢 Buy
2026-04-03,NVDA,Tech,35.0,30%,0.12,80,🔴 Sell
"""
    
    # 使用 StringIO 模拟文件读取
    fake_file = io.StringIO(mock_csv_data)
    
    try:
        feeder = DataFeeder(fake_file)
        print(f"✅ 数据加载成功，共识别出 {feeder.total_batches} 个交易日批次。\n")
        
        # 模拟引擎循环读取数据
        while True:
            current_date, daily_signals = feeder.get_next_batch()
            print(f"📅 【时间机器到达】日期: {current_date}")
            print(daily_signals.to_string(index=False))
            print("-" * 40)
            
    except StopIteration as e:
        print(str(e))
