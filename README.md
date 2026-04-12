# micro-quant-simulator
This is the first version of simulator based on the data from lab-2
# 🚀 Micro Quant Simulator (量化回测与数据同步自动化系统)

![Python](https://img.shields.io/badge/Python-3.9-blue)
![GitHub Actions](https://img.shields.io/badge/Automation-GitHub_Actions-orange)
![License](https://img.shields.io/badge/License-MIT-green)

这是一个基于 GitHub Actions 的全自动量化回测与数据同步系统。它能够每天定时从私有数据仓拉取最新的策略因子或行情数据，自动运行回测逻辑，并实时更新账户权益曲线。

## 🌟 核心功能 (Core Features)

- **跨仓自动化同步**：通过 GitHub Fine-grained PAT 令牌，安全地从私有数据仓 (`micro-quant-trading-lab-2`) 检出数据。
- **每日定时回测**：每天纽约时间 24:00 (UTC 04:00) 自动触发回测任务。
- **动态行情集成**：内置 `yfinance` 支持，自动获取美股实时行情。
- **资产追踪 (Equity Tracking)**：自动生成并更新 `daily_equity.csv`，记录账户每日净值变化。
- **自动保存结果**：回测产生的交易历史和统计结果会自动提交回 GitHub 仓库，实现无感知的数据持久化。

## 🏗️ 系统架构 (Architecture)

1. **Trigger**: 每天凌晨定时启动或手动点击 `Workflow Dispatch`。
2. **Environment**: 启动 Ubuntu 最新版虚拟机，配置 Python 3.9 环境。
3. **Data Sync**: 使用 `insteadOf` 全局认证模式拉取私有数据仓。
4. **Execution**: 运行 `sync_data.py` 执行核心回测逻辑。
5. **Persistence**: 将最新的 `daily_equity.csv` 和 `history_database/` 推送回仓库。

## 🛠️ 安装与配置 (Setup)

### 1. 依赖安装
```bash
pip install pandas yfinance numpy
