import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns
import os

def generate_reports():
    # 1. 加载数据
    file_path = "daily_equity.csv"
    if not os.path.exists(file_path):
        print(f"❌ 找不到 {file_path}，请先运行回测！")
        return
    
    df = pd.read_csv(file_path)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # 设置绘图风格
    sns.set_theme(style="whitegrid")
    plt.rcParams['axes.unicode_minus'] = False # 解决负号显示问题

    # --- 第一张图：总资产折线图 (Total Assets Line Chart) ---
    plt.figure(figsize=(12, 6), dpi=120)
    plt.plot(df['Date'], df['Total_Assets'], color='#E64A19', linewidth=2.5, label='Total Assets')
    plt.fill_between(df['Date'], df['Total_Assets'], df['Total_Assets'].min()*0.99, color='#FFCCBC', alpha=0.3)
    
    plt.title('Account Equity Curve (Total Assets)', fontsize=15, fontweight='bold', pad=15)
    plt.ylabel('Amount (USD)', fontsize=12)
    plt.xticks(rotation=30)
    plt.legend(loc='upper left')
    plt.tight_layout()
    plt.savefig("report_total_assets_line.png")
    print("📈 折线图已生成: report_total_assets_line.png")


    # --- 第二张图：资产构成堆叠柱状图 (Asset Composition Stacked Bar) ---
    # 如果数据点太多，柱状图会挤在一起，这里我们做一个简单的采样，比如每2天显示一个柱子，或者全显示
    plt.figure(figsize=(14, 7), dpi=120)
    
    # 画底层：Evaluated_Equity (红色)
    plt.bar(df['Date'], df['Evaluated_Equity'], color='#D32F2F', label='Evaluated Equity', alpha=0.85)
    
    # 画上层：Cash_Balance (蓝色) - 使用 bottom 参数实现堆叠
    plt.bar(df['Date'], df['Cash_Balance'], bottom=df['Evaluated_Equity'], color='#1976D2', label='Cash Balance', alpha=0.85)

    # 在每个柱子顶部标注总金额
    for i in range(len(df)):
        total = df['Total_Assets'].iloc[i]
        # 标注文字，每隔 N 个标注一个，防止太拥挤
        if len(df) > 15 and i % (len(df)//10) != 0: continue 
        plt.text(df['Date'].iloc[i], total + (total*0.005), f'${total/1000:.1f}k', 
                 ha='center', va='bottom', fontsize=8, fontweight='bold', color='#333333')

    plt.title('Daily Asset Composition: Equity vs Cash', fontsize=15, fontweight='bold', pad=15)
    plt.ylabel('Amount (USD)', fontsize=12)
    plt.legend(loc='upper right', frameon=True, shadow=True) # 右上角图例
    plt.xticks(rotation=30)
    
    # 格式化 Y 轴为千分位
    plt.gca().yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
    
    plt.tight_layout()
    plt.savefig("report_asset_composition_bar.png")
    print("📊 堆叠柱状图已生成: report_asset_composition_bar.png")

if __name__ == "__main__":
    generate_reports()
