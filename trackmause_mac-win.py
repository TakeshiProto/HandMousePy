import cv2
import mediapipe as mp
import pyautogui
import math
import numpy as np
import sys
import platform
# Используем pynput, так как на Mac keyboard требует root-прав
from pynput import keyboard

# --- КОНФИГУРАЦИЯ СИСТЕМЫ ---
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    import ctypes

# Разрешение камеры
CAM_WIDTH, CAM_HEIGHT = 1280, 720
# ОПТИМИЗАЦИЯ: Разрешение для обработки нейросетью (в 2 раза меньше)
PROC_W, PROC_H = 640, 360 
WINDOW_NAME = 'Hand Mouse: Optimized & Light HUD'

# Настройки "Тачпада" (прямоугольник управления)
BOX_W, BOX_H = 600, 400
X1, Y1 = (CAM_WIDTH - BOX_W) // 2, (CAM_HEIGHT - BOX_H) // 2
X2, Y2 = X1 + BOX_W, Y1 + BOX_H

# Адаптация под ОС
SCROLL_SPEED = 120 if IS_WINDOWS else 10
# Отключаем защитную задержку pyautogui для мгновенного отклика
pyautogui.PAUSE = 0
# Оставляем FAILSAFE: увод мыши в угол закроет программу
pyautogui.FAILSAFE = True

# --- ОПТИМИЗИРОВАННЫЙ ЛЕГКИЙ HUD ---
def draw_ui_light(img, active_gesture="", hand_in_box=False):
    """Рисует панель управления без ресурсоемкого копирования кадра"""
    # 1. Заготовка черного фона (непрозрачного) для меню - это быстро
    # Отрисовываем прямоугольник прямо на исходном изображении
    cv2.rectangle(img, (20, 20), (450, 280), (10, 10, 10), -1) # Темно-серый фон
    
    gestures = [
        ("Index+Thumb: CLICK", "CLICK"),
        ("Middle+Thumb: DRAG", "DRAG"),
        ("Ring+Thumb: RIGHT CLICK", "RIGHT"),
        ("I+M+Thumb: DOUBLE CLICK", "DOUBLE"),
        ("Hand FIST: SCROLL", "SCROLL"),
        ("Both hands Pinky+Thumb: EXIT", "EXIT_GESTURE")
    ]
    
    # 2. Отрисовка текста - нагрузка минимальна
    for i, (text, key) in enumerate(gestures):
        color = (0, 255, 0) if active_gesture == key else (200, 200, 200)
        cv2.putText(img, text, (30, 60 + i * 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)

    # 3. Визуализация бокса "тачпада"
    box_color = (0, 255, 0) if hand_in_box else (255, 0, 255)
    cv2.rectangle(img, (X1, Y1), (X2, Y2), box_color, 2)
    cv2.putText(img, "CONTROL PANEL", (X1 + 10, Y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1)

# --- ИНИЦИАЛИЗАЦИЯ ---
mp_hands = mp.solutions.hands
# ОПТИМИЗАЦИЯ: model_complexity=0 для максимальной скорости
hands = mp_hands.Hands(
    max_num_hands=2, 
    model_complexity=0, 
    min_detection_confidence=0.6, 
    min_tracking_confidence=0.6
)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
# ОПТИМИЗАЦИЯ: Включаем MJPG формат для повышения FPS камеры
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

screen_w, screen_h = pyautogui.size()
p_locX, p_locY = 0, 0
smoothening = 5 # Сглаживание движения       
is_pressed = False
click_ready = right_ready = double_ready = True
running = True

# --- ГОРЯЧИЕ КЛАВИШИ (pynput) ---
def on_press(key):
    global running
    try:
        if hasattr(key, 'char') and key.char == 'q':
            running = False
            return False # Остановить слушатель pynput
    except: pass

listener = keyboard.Listener(on_press=on_press)
listener.start()

# --- ОСНОВНОЙ ЦИКЛ ---
try:
    while cap.isOpened() and running:
        success, image = cap.read()
        if not success: break

        image = cv2.flip(image, 1)
        current_action = ""
        hand_in_box = False
        
        # ОПТИМИЗАЦИЯ: Уменьшаем кадр для нейросети (в 2 раза), но рисуем на большом
        img_small = cv2.resize(image, (PROC_W, PROC_H))
        rgb_image = cv2.cvtColor(img_small, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_image)

        if results.multi_hand_landmarks:
            exit_ready_hands = 0
            
            # 1. Цикл по всем рукам: отрисовка и жест выхода
            for hand_lms in results.multi_hand_landmarks:
                mp_draw.draw_landmarks(image, hand_lms, mp_hands.HAND_CONNECTIONS)
                
                # Координаты для жеста выхода (с учетом масштаба PROC_W/H -> CAM_WIDTH/HEIGHT)
                t_p = hand_lms.landmark[4]
                p_p = hand_lms.landmark[20]
                # Расстояние считаем в пикселях большого кадра
                dist_exit = math.hypot((t_p.x - p_p.x) * CAM_WIDTH, (t_p.y - p_p.y) * CAM_HEIGHT)
                if dist_exit < 40: exit_ready_hands += 1

            # Жест выхода двумя руками
            if exit_ready_hands >= 2:
                current_action = "EXIT_GESTURE"
                running = False

            # 2. Управление мышью (по первой найденной руке)
            main_hand = results.multi_hand_landmarks[0]
            lm = main_hand.landmark
            # Центр ладони
            cx, cy = int(lm[9].x * CAM_WIDTH), int(lm[9].y * CAM_HEIGHT)
            
            # Проверка зоны тачпада
            if X1 < cx < X2 and Y1 < cy < Y2:
                hand_in_box = True
                
                # Маппинг координат
                x_map = np.interp(cx, (X1, X2), (0, screen_w))
                y_map = np.interp(cy, (Y1, Y2), (0, screen_h))
                
                # Сглаживание
                c_locX = p_locX + (x_map - p_locX) / smoothening
                c_locY = p_locY + (y_map - p_locY) / smoothening
                
                # Перемещаем курсор
                try:
                    pyautogui.moveTo(c_locX, c_locY)
                except pyautogui.FailSafeException:
                    running = False
                p_locX, p_locY = c_locX, c_locY

                # Логика жестов управления
                def get_pt(idx): return int(lm[idx].x * CAM_WIDTH), int(lm[idx].y * CAM_HEIGHT)
                ttx, tty = get_pt(4); itx, ity = get_pt(8)
                mtx, mty = get_pt(12); rtx, rty = get_pt(16)

                is_fist = (lm[8].y > lm[6].y and lm[12].y > lm[10].y and 
                           lm[16].y > lm[14].y and lm[20].y > lm[18].y)

                if is_fist:
                    current_action = "SCROLL"
                    if cy < Y1 + BOX_H // 3: pyautogui.scroll(SCROLL_SPEED)
                    elif cy > Y1 + 2 * BOX_H // 3: pyautogui.scroll(-SCROLL_SPEED)
                else:
                    d_idx = math.hypot(itx - ttx, ity - tty)
                    d_mid = math.hypot(mtx - ttx, mty - tty)
                    d_rng = math.hypot(rtx - ttx, rty - tty)

                    # DOUBLE CLICK
                    if d_idx < 45 and d_mid < 45:
                        current_action = "DOUBLE"
                        if double_ready: pyautogui.doubleClick(); double_ready = False
                    else:
                        double_ready = True
                        # RIGHT CLICK
                        if d_rng < 45:
                            current_action = "RIGHT"
                            if right_ready: pyautogui.rightClick(); right_ready = False
                        else: right_ready = True
                        # DRAG
                        if d_mid < 45:
                            current_action = "DRAG"
                            if not is_pressed: pyautogui.mouseDown(); is_pressed = True
                        else:
                            if is_pressed: pyautogui.mouseUp(); is_pressed = False
                        # CLICK
                        if d_idx < 45:
                            current_action = "CLICK"
                            if click_ready: pyautogui.click(); click_ready = False
                        else: click_ready = True

        # Автоматический сброс зажатия при потере контроля
        if (not hand_in_box or not results.multi_hand_landmarks) and is_pressed:
            pyautogui.mouseUp()
            is_pressed = False

        # ОТРИСОВКА ЛЕГКОГО HUD
        draw_ui_light(image, current_action, hand_in_box)
        
        cv2.imshow(WINDOW_NAME, image)
        
        # На Mac функция set_always_on_top проигнорируется
        if IS_WINDOWS:
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_NAME)
                if hwnd: ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
            except: pass
            
        # Дублирующий выход по Q в окне OpenCV
        if cv2.waitKey(1) & 0xFF == ord('q'): break

finally:
    cap.release()
    cv2.destroyAllWindows()
    listener.stop()
    sys.exit()