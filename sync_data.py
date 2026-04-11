import os
import shutil

def shallow_copy_database():
    print("🔄 开始执行浅拷贝 (Shallow Copy) 数据同步...")
    
    # 设定源目录（云端拉取下来的数据仓文件夹）和目标目录（回测仓的数据库）
    source_dir = "temp_data_repo/history_database"
    target_dir = "history_database"
    
    # 如果源目录不存在，说明云端拉取失败
    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"❌ 找不到数据源目录: {source_dir}")
        
    # 如果目标目录不存在，先创建它
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"📁 创建了目标目录: {target_dir}")
        
    # 执行 Python 的目录覆盖拷贝 (Python 3.8+ 支持 dirs_exist_ok)
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    
    # 统计搬运了多少个文件
    files_copied = [f for f in os.listdir(target_dir) if f.endswith('.csv')]
    print(f"✅ 数据同步完成！当前 {target_dir} 内共有 {len(files_copied)} 个 CSV 文件。")

if __name__ == "__main__":
    shallow_copy_database()
