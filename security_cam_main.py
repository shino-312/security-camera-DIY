#!/usr/bin/python3
import cv2
import time
import datetime
import os
from collections import deque

# Configuration
VIDEO_DEVICE_INDEX = 0
# OUTPUT_BASE_DIR = './captures'
OUTPUT_BASE_DIR = '/media/shinji/3ABD-D198/captures'
EVENT_DIR = os.path.join(OUTPUT_BASE_DIR, 'event')      # 動画保存先
CONSTANT_DIR = os.path.join(OUTPUT_BASE_DIR, 'constant') # 静止画保存先
WAIT_AFTER_LAUNCH = 10 #[s]

# Motion Detection Config
MIN_AREA = 5000
RECORD_DURATION = 10       # 検知後の動画録画時間[s]
COMPARE_DELAYS = [1.0, 3.0, 5.0] #[s]
BUFFER_DURATION = 6.0 #[s]

# Constant Capture Config
CONSTANT_FPS = 0.3          # 常時保存する静止画のFPS
CONSTANT_INTERVAL = 1.0 / CONSTANT_FPS

def get_past_frame(buffer, seconds_ago):
    """バッファから指定秒数前のフレーム（グレー）を検索"""
    if not buffer:
        return None
    current_time = buffer[-1][0]
    target_time = current_time - seconds_ago
    best_frame = None
    min_diff = 1.0

    for t, _, gray in reversed(buffer):
        diff = abs(t - target_time)
        if diff < min_diff:
            min_diff = diff
            best_frame = gray
        if t < target_time - 0.5: 
            break
    return best_frame

def main():
    # フォルダ作成
    for directory in [EVENT_DIR, CONSTANT_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)

    cap = cv2.VideoCapture(VIDEO_DEVICE_INDEX)
    if not cap.isOpened():
        print(f"Error: Could not open video device {VIDEO_DEVICE_INDEX}")
        return

    frame_buffer = deque()

    start_time = time.time()

    # 状態管理変数
    is_recording = False
    recording_end_time = 0
    video_writer = None
    last_constant_save_time = 0

    print(f"System Started.")
    print(f"- Motion Rec: {RECORD_DURATION}s duration")
    print(f"- Constant Rec: {CONSTANT_FPS} FPS")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            current_time = time.time()

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            #gray = cv2.GaussianBlur(gray, (21, 21), 0)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)
            frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

            frame_buffer.append((current_time, frame, gray))

            # --- 2. 前処理 & バッファリング ---
            while frame_buffer and (current_time - frame_buffer[0][0] > BUFFER_DURATION):
                frame_buffer.popleft()

            # --- 3. 動体検知ロジック ---
            motion_detected = False
            area = 0
            
            # バッファが溜まっており、比較対象がある場合のみ実行
            if (current_time - start_time) > WAIT_AFTER_LAUNCH:
                for delay in COMPARE_DELAYS:
                    past_gray = get_past_frame(frame_buffer, delay)
                    if past_gray is None: continue

                    delta = cv2.absdiff(past_gray, gray)
                    thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                    thresh = cv2.dilate(thresh, None, iterations=2)
                    
                    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    for contour in contours:
                        area = cv2.contourArea(contour) 
                        if area < MIN_AREA:
                            continue
                        motion_detected = True
                        print("motion detected area=",area)
                        break 
                    
                    if motion_detected: break

            # --- 検知情報画面表示 ---
            status = "REC" if is_recording else "MONITOR"
            color = (0, 0, 255) if is_recording else (0, 255, 0)
            cv2.putText(frame, f"{status}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.putText(frame, f"{area:.0f}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            now = datetime.datetime.now()
            date_str = now.strftime("%Y/%m/%d %H:%M:%S")
            cv2.putText(frame, date_str, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)

            # --- イベント録画制御 ---
            if motion_detected:
                print(f"Motion Detected! Recording until {current_time + RECORD_DURATION:.0f}")
                recording_end_time = current_time + RECORD_DURATION

                if not is_recording:
                    is_recording = True
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_filename = os.path.join(EVENT_DIR, f"event_{timestamp}.mp4")
                    fourcc = cv2.VideoWriter_fourcc(*'H264')
                    h, w = frame.shape[:2]
                    video_writer = cv2.VideoWriter(video_filename, fourcc, 20.0, (w, h))
                    print(f"Start Recording Video: {video_filename}")

                    # プリレコ（バッファ書き出し）
                    for _, past_bgr, _ in frame_buffer:
                        video_writer.write(past_bgr)

            if is_recording:
                video_writer.write(frame)
                if current_time > recording_end_time:
                    print("Recording timeout. Stopping.")
                    is_recording = False
                    video_writer.release()
                    video_writer = None

            # --- 静止画保存 ---
            if current_time - last_constant_save_time >= CONSTANT_INTERVAL:
            #if motion_detected and (current_time - last_constant_save_time >= CONSTANT_INTERVAL):
                date_dir = now.strftime("%Y%m%d")
                hour_dir = now.strftime("%H")
                save_dir = os.path.join(CONSTANT_DIR, date_dir, hour_dir)
                os.makedirs(save_dir, exist_ok=True)

                timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(save_dir, f"img_{timestamp_str}-{area:.0f}.jpg")
                cv2.imwrite(filename, frame)
                last_constant_save_time = current_time

            cv2.imshow("Security Feed", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            time.sleep(0.1) # ループを回すため少し短くしました

    finally:
        if video_writer is not None:
            video_writer.release()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
