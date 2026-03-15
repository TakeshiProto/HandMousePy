import cv2
import mediapipe as mp
import pyautogui
import math
from pynput import keyboard
import numpy as np
import sys
import platform

# --- ОПРЕДЕЛЕНИЕ СИСТЕМЫ ---
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    import ctypes

# --- НАСТРОЙКИ ОКНА ---
CAM_WIDTH = 1280
CAM_HEIGHT = 720
WINDOW_NAME = 'Hand Mouse: Control Panel Edition'

# Отключаем задержки для плавности
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

# Настройки "Тачпада" (прямоугольника управления)
BOX_W, BOX_H = 600, 400
X1, Y1 = (CAM_WIDTH - BOX_W) // 2, (CAM_HEIGHT - BOX_H) // 2
X2, Y2 = X1 + BOX_W, Y1 + BOX_H

# Настройка скроллинга (Windows: 120, Mac: ~10)
SCROLL_SPEED = 120 if IS_WINDOWS else 10

def set_always_on_top(window_name):
    """Поверх всех окон (только для Windows)"""
    if IS_WINDOWS:
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
            if hwnd:
                ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception:
            pass

# Настройки чувствительности
smoothening = 5        
p_locX, p_locY = 0, 0

mp_hands = mp.solutions.hands
# На Mac model_complexity=1 работает стабильнее
hands = mp_hands.Hands(
    max_num_hands=1, 
    model_complexity=1,
    min_detection_confidence=0.7, 
    min_tracking_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

screen_w, screen_h = pyautogui.size()

# Флаги состояний
is_pressed = False
click_ready = right_ready = double_ready = True
running = True

def draw_ui(img, active_gesture="", hand_in_box=False):
    """Рисует HUD и панель управления"""
    overlay = img.copy()
    cv2.rectangle(overlay, (20, 20), (380, 250), (40, 40, 40), -1)
    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)
    
    gestures = [
        ("Index+Thumb: CLICK", "CLICK"),
        ("Middle+Thumb: DRAG", "DRAG"),
        ("Ring+Thumb: RIGHT CLICK", "RIGHT"),
        ("I+M+Thumb: DOUBLE CLICK", "DOUBLE"),
        ("Hand FIST: SCROLL (Up/Down)", "SCROLL")
    ]
    
    for i, (text, key) in enumerate(gestures):
        color = (0, 255, 0) if active_gesture == key else (200, 200, 200)
        cv2.putText(img, text, (30, 60 + i * 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)

    box_color = (0, 255, 0) if hand_in_box else (255, 0, 255)
    cv2.rectangle(img, (X1, Y1), (X2, Y2), box_color, 2)
    cv2.putText(img, "CONTROL PANEL", (X1 + 10, Y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1)

# --- ГОРЯЧИЕ КЛАВИШИ (pynput заменяет keyboard для совместимости) ---
def on_press(key):
    global running
    try:
        # 'q' для выхода
        if hasattr(key, 'char') and key.char == 'q':
            running = False
            return False 
    except Exception:
        pass

listener = keyboard.Listener(on_press=on_press)
listener.start()

while cap.isOpened() and running:
    success, image = cap.read()
    if not success: break

    image = cv2.flip(image, 1)
    h, w, _ = image.shape
    current_action = ""
    hand_in_box = False
    
    # Визуальные линии скроллинга внутри бокса
    cv2.line(image, (X1, Y1 + BOX_H//3), (X2, Y1 + BOX_H//3), (100, 100, 100), 1)
    cv2.line(image, (X1, Y1 + 2*BOX_H//3), (X2, Y1 + 2*BOX_H//3), (100, 100, 100), 1)

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_image)

    if results.multi_hand_landmarks:
        main_hand = results.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(image, main_hand, mp_hands.HAND_CONNECTIONS)
        lm = main_hand.landmark
        
        cx, cy = int(lm[9].x * w), int(lm[9].y * h)
        
        if X1 < cx < X2 and Y1 < cy < Y2:
            hand_in_box = True
            
            x_map = np.interp(cx, (X1, X2), (0, screen_w))
            y_map = np.interp(cy, (Y1, Y2), (0, screen_h))
            
            c_locX = p_locX + (x_map - p_locX) / smoothening
            c_locY = p_locY + (y_map - p_locY) / smoothening
            
            try:
                pyautogui.moveTo(c_locX, c_locY, _pause=False)
            except pyautogui.FailSafeException:
                running = False
            p_locX, p_locY = c_locX, c_locY

            # Определение кулака
            is_fist = (lm[8].y > lm[6].y and lm[12].y > lm[10].y and 
                       lm[16].y > lm[14].y and lm[20].y > lm[18].y)
            
            def get_pt(idx): return int(lm[idx].x * w), int(lm[idx].y * h)
            ttx, tty = get_pt(4)
            itx, ity = get_pt(8)
            mtx, mty = get_pt(12)
            rtx, rty = get_pt(16)

            if is_fist:
                current_action = "SCROLL"
                if cy < Y1 + BOX_H // 3: pyautogui.scroll(SCROLL_SPEED)
                elif cy > Y1 + 2 * BOX_H // 3: pyautogui.scroll(-SCROLL_SPEED)
            else:
                d_idx = math.hypot(itx - ttx, ity - tty)
                d_mid = math.hypot(mtx - ttx, mty - tty)
                d_rng = math.hypot(rtx - ttx, rty - tty)

                if d_idx < 45 and d_mid < 45:
                    current_action = "DOUBLE"
                    if double_ready: pyautogui.doubleClick(); double_ready = False
                else:
                    double_ready = True
                    if d_rng < 45:
                        current_action = "RIGHT"
                        if right_ready: pyautogui.rightClick(); right_ready = False
                    else: right_ready = True
                    if d_mid < 45:
                        current_action = "DRAG"
                        if not is_pressed: pyautogui.mouseDown(); is_pressed = True
                    else:
                        if is_pressed: pyautogui.mouseUp(); is_pressed = False
                    if d_idx < 45:
                        current_action = "CLICK"
                        if click_ready: pyautogui.click(); click_ready = False
                    else: click_ready = True

    draw_ui(image, current_action, hand_in_box)
    cv2.imshow(WINDOW_NAME, image)
    set_always_on_top(WINDOW_NAME)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
listener.stop() # Останавливаем pynput
sys.exit()