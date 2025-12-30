#!/usr/bin/python3
import os
import shutil
import time
import datetime

# --- 設定 ---
# 監視対象のルートディレクトリ（カメラの保存先）
TARGET_DIR = '/media/shinji/3ABD-D198/captures'

# 容量確保の閾値（これより空き容量が減ったら削除を開始する）
MIN_FREE_SPACE_GB = 10.0  # 5GB

# チェックを行う間隔（秒）
CHECK_INTERVAL = 600  # 10分に1回チェック

# 削除対象のサブディレクトリ
SUB_DIRS = ['constant', 'event']

def get_free_space_gb(path):
    """指定パスを含むディスクの空き容量(GB)を返す"""
    try:
        total, used, free = shutil.disk_usage(path)
        return free / (1024**3)
    except FileNotFoundError:
        return 0.0

def get_oldest_date_folder(base_path):
    """
    指定フォルダ直下にある「数字8桁(YYYYMMDD)」のフォルダを探し、
    一番古いもののパスを返す。なければ None。
    """
    if not os.path.exists(base_path):
        return None
    
    # フォルダ一覧を取得し、数字だけのもの（日付フォルダ）を抽出
    folders = [f for f in os.listdir(base_path) if f.isdigit() and os.path.isdir(os.path.join(base_path, f))]
    
    if not folders:
        return None

    # 文字列としてソートすれば日付順になる (例: '20251230' < '20251231')
    folders.sort()
    
    return os.path.join(base_path, folders[0])

def perform_cleanup():
    """容量回復ロジック"""
    
    # 1. まず容量チェック
    free_gb = get_free_space_gb(TARGET_DIR)
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Free Space: {free_gb:.2f} GB")

    # 容量が十分なら何もしない
    if free_gb >= MIN_FREE_SPACE_GB:
        return

    print("!!! Disk space low. Starting cleanup... !!!")

    # 2. 容量が回復するまでループして削除
    while free_gb < MIN_FREE_SPACE_GB:
        deleted_something = False

        for sub in SUB_DIRS:
            target_path = os.path.join(TARGET_DIR, sub)
            oldest_folder = get_oldest_date_folder(target_path)

            if oldest_folder:
                try:
                    print(f"  -> Deleting: {oldest_folder}")
                    # フォルダごと削除（高速）
                    shutil.rmtree(oldest_folder)
                    deleted_something = True
                    
                    # 削除した直後に容量を再計算
                    free_gb = get_free_space_gb(TARGET_DIR)
                    print(f"  -> New Free Space: {free_gb:.2f} GB")
                    
                    # 目標達成したらループを抜ける
                    if free_gb >= MIN_FREE_SPACE_GB:
                        break

                except Exception as e:
                    print(f"  [Error] Failed to delete {oldest_folder}: {e}")

        # 削除候補が見つからない（空っぽ）なのに容量不足の場合、無限ループ防止で抜ける
        if not deleted_something:
            print("  [Warning] No deletable folders found, but disk is still full.")
            break
        
        time.sleep(1) # CPU負荷低減のためのウェイト

    print("Cleanup finished.")

def main():
    print("Disk Cleaner Service Started.")
    print(f"Target: {TARGET_DIR}")
    print(f"Threshold: < {MIN_FREE_SPACE_GB} GB")
    
    try:
        while True:
            # USBメモリがマウントされているか確認
            if os.path.exists(TARGET_DIR):
                perform_cleanup()
            else:
                print(f"[Error] Target directory not found: {TARGET_DIR}")
            
            # 次のチェックまで待機
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopping Cleaner Service.")

if __name__ == "__main__":
    main()
