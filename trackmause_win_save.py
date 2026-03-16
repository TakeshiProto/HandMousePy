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
WINDOW_NAME = 'Hand Mouse: Control Panel Edition'

# Настройки "Тачпада" (прямоугольника управления)
# Центрируем бокс 600x400
BOX_W, BOX_H = 600, 400
X1, Y1 = (CAM_WIDTH - BOX_W) // 2, (CAM_HEIGHT - BOX_H) // 2
X2, Y2 = X1 + BOX_W, Y1 + BOX_H

def set_always_on_top(window_name):
    hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
    if hwnd:
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)

# Настройки чувствительности
smoothening = 5        
p_locX, p_locY = 0, 0

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)
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
    # 1. Основное меню жестов
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

    # 2. Отрисовка "Тачпада" (центрального прямоугольника)
    box_color = (0, 255, 0) if hand_in_box else (255, 0, 255)
    cv2.rectangle(img, (X1, Y1), (X2, Y2), box_color, 2)
    cv2.putText(img, "CONTROL PANEL", (X1 + 10, Y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1)

keyboard.add_hotkey('ctrl+shift+q', lambda: globals().update(running=False))

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
        
        # Точка 9 (центр ладони) для управления
        cx, cy = int(lm[9].x * w), int(lm[9].y * h)
        
        # Проверяем, находится ли рука в боксе
        if X1 < cx < X2 and Y1 < cy < Y2:
            hand_in_box = True
            
            # Масштабируем координаты бокса на весь экран
            x_map = np.interp(cx, (X1, X2), (0, screen_w))
            y_map = np.interp(cy, (Y1, Y2), (0, screen_h))
            
            # Сглаживание
            c_locX = p_locX + (x_map - p_locX) / smoothening
            c_locY = p_locY + (y_map - p_locY) / smoothening
            
            pyautogui.moveTo(c_locX, c_locY, _pause=False)
            p_locX, p_locY = c_locX, c_locY

            # Определение кулака
            is_fist = (lm[8].y > lm[6].y and lm[12].y > lm[10].y and 
                       lm[16].y > lm[14].y and lm[20].y > lm[18].y)
            
            # Координаты пальцев для жестов
            def get_pt(idx): return int(lm[idx].x * w), int(lm[idx].y * h)
            ttx, tty = get_pt(4)
            itx, ity = get_pt(8)
            mtx, mty = get_pt(12)
            rtx, rty = get_pt(16)

            if is_fist:
                current_action = "SCROLL"
                # Скроллинг относительно зон внутри бокса
                if cy < Y1 + BOX_H // 3: pyautogui.scroll(120)
                elif cy > Y1 + 2 * BOX_H // 3: pyautogui.scroll(-120)
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
keyboard.unhook_all()
sys.exit()