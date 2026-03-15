import cv2
import mediapipe as mp
import pyautogui
import math
import keyboard
import numpy as np
import sys
import ctypes

# --- НАСТРОЙКИ ОКНА ---
CAM_WIDTH = 1280
CAM_HEIGHT = 720
WINDOW_NAME = 'Hand Mouse: Fist Scroll Edition'

def set_always_on_top(window_name):
    hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
    if hwnd:
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)

# Настройки чувствительности
frame_reduction = 180 
smoothening = 5        
p_locX, p_locY = 0, 0
c_locX, c_locY = 0, 0

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

screen_w, screen_h = pyautogui.size()

# Флаги состояний
is_pressed = False
click_ready = True
right_ready = True
double_ready = True
running = True

def draw_ui(img, active_gesture=""):
    """Рисует обновленную панель управления"""
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
        thickness = 2 if active_gesture == key else 1
        cv2.putText(img, text, (30, 60 + i * 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, thickness)

keyboard.add_hotkey('ctrl+shift+q', lambda: globals().update(running=False))

while cap.isOpened() and running:
    success, image = cap.read()
    if not success: break

    image = cv2.flip(image, 1)
    h, w, _ = image.shape
    current_action = ""
    
    # Визуальные границы зон скроллинга (тонкие линии)
    cv2.line(image, (0, h // 3), (w, h // 3), (100, 100, 100), 1)
    cv2.line(image, (0, 2 * h // 3), (w, 2 * h // 3), (100, 100, 100), 1)
    cv2.rectangle(image, (frame_reduction, frame_reduction), 
                  (w - frame_reduction, h - frame_reduction), (255, 0, 255), 1)

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_image)

    if results.multi_hand_landmarks:
        # Проверка выхода (две руки)
        exit_gestures = 0
        for hand_lms in results.multi_hand_landmarks:
            t_p = hand_lms.landmark[4]
            p_p = hand_lms.landmark[20]
            if math.hypot((t_p.x - p_p.x) * w, (t_p.y - p_p.y) * h) < 45:
                exit_gestures += 1
        if exit_gestures >= 2: running = False

        # Управление
        main_hand = results.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(image, main_hand, mp_hands.HAND_CONNECTIONS)
        lm = main_hand.landmark
        
        # 1. ОПРЕДЕЛЕНИЕ КУЛАКА
        # Пальцы 8, 12, 16, 20 должны быть ниже суставов 6, 10, 14, 18
        is_fist = (lm[8].y > lm[6].y and lm[12].y > lm[10].y and 
                   lm[16].y > lm[14].y and lm[20].y > lm[18].y)
        
        # Координаты для расчетов
        ttx, tty = int(lm[4].x * w), int(lm[4].y * h)
        itx, ity = int(lm[8].x * w), int(lm[8].y * h)
        mtx, mty = int(lm[12].x * w), int(lm[12].y * h)
        rtx, rty = int(lm[16].x * w), int(lm[16].y * h)

        # Движение курсора (по точке 9 - центр ладони, чтобы кулак не дергал мышь)
        x_map = np.interp(lm[9].x * w, (frame_reduction, w - frame_reduction), (0, screen_w))
        y_map = np.interp(lm[9].y * h, (frame_reduction, h - frame_reduction), (0, screen_h))
        c_locX = p_locX + (x_map - p_locX) / smoothening
        c_locY = p_locY + (y_map - p_locY) / smoothening
        pyautogui.moveTo(c_locX, c_locY, _pause=False)
        p_locX, p_locY = c_locX, c_locY

        # 2. ЛОГИКА СКРОЛЛИНГА НА КУЛАКЕ
        if is_fist:
            current_action = "SCROLL"
            # Определяем зону по высоте ладони (точка 9)
            if lm[9].y * h < h // 3:
                pyautogui.scroll(120)
            elif lm[9].y * h > 2 * h // 3:
                pyautogui.scroll(-120)
        
        else:
            # 3. ЛОГИКА КЛИКОВ (только если НЕ кулак)
            d_idx = math.hypot(itx - ttx, ity - tty)
            d_mid = math.hypot(mtx - ttx, mty - tty)
            d_rng = math.hypot(rtx - ttx, rty - tty)

            # Двойной клик (Указательный + Средний + Большой)
            if d_idx < 45 and d_mid < 45:
                current_action = "DOUBLE"
                if double_ready:
                    pyautogui.doubleClick()
                    double_ready = False
            else:
                double_ready = True
                
                # ПКМ (Безымянный + Большой)
                if d_rng < 45:
                    current_action = "RIGHT"
                    if right_ready:
                        pyautogui.rightClick()
                        right_ready = False
                else:
                    right_ready = True
                
                # Зажатие (Средний + Большой)
                if d_mid < 45:
                    current_action = "DRAG"
                    if not is_pressed:
                        pyautogui.mouseDown()
                        is_pressed = True
                else:
                    if is_pressed:
                        pyautogui.mouseUp()
                        is_pressed = False
                
                # Клик ЛКМ (Указательный + Большой)
                if d_idx < 45:
                    current_action = "CLICK"
                    if click_ready:
                        pyautogui.click()
                        click_ready = False
                else:
                    click_ready = True

    draw_ui(image, current_action)
    cv2.imshow(WINDOW_NAME, image)
    set_always_on_top(WINDOW_NAME)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
keyboard.unhook_all()
sys.exit()