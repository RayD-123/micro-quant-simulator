import os
import shutil
from main import run_backtest # 导入你原本的 main.py 里的函数

def auto_sync_and_run():
    print("🔄 [Step 1/2] 正在从临时目录同步最新 CSV 数据...")
    source_dir = "temp_data_repo/history_database"
    target_dir = "history_database"
    
    if os.path.exists(source_dir):
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        # 覆盖拷贝数据文件
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
        print("✅ 数据同步成功！")
    else:
        print("❌ 错误：未找到数据源。")
        return

    print("\n🚀 [Step 2/2] 立即启动自动化回测引擎...")
    # 直接调用你原本在 main.py 里写的逻辑
    run_backtest()

if __name__ == "__main__":
    auto_sync_and_run()
