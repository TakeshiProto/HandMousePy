import cv2
import mediapipe as mp
import pyautogui
import math
from pynput import keyboard
import numpy as np
import sys

# --- НАСТРОЙКИ ---
CAM_WIDTH = 1280
CAM_HEIGHT = 720
WINDOW_NAME = 'Hand Mouse: Fist Scroll Edition'

# Отключаем задержки pyautogui для плавности на macOS
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True # Позволяет прервать скрипт, утянув мышь в левый верхний угол

# Настройки чувствительности
frame_reduction = 180 
smoothening = 5        
p_locX, p_locY = 0, 0
c_locX, c_locY = 0, 0

# Инициализация MediaPipe
mp_hands = mp.solutions.hands
# На Mac иногда стабильнее работает с model_complexity=1
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2, 
    model_complexity=1,
    min_detection_confidence=0.7, 
    min_tracking_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

# Инициализация камеры
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
    """Рисует панель управления"""
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

# --- ГОРЯЧИЕ КЛАВИШИ (pynput) ---
def on_press(key):
    global running
    try:
        # Слушаем клавишу 'q' для выхода
        if hasattr(key, 'char') and key.char == 'q':
            print("\nЗавершение работы...")
            running = False
            return False 
    except Exception as e:
        pass

listener = keyboard.Listener(on_press=on_press)
listener.start()

print(f"Скрипт запущен. Нажмите 'q' для выхода.")

while cap.isOpened() and running:
    success, image = cap.read()
    if not success: break

    image = cv2.flip(image, 1)
    h, w, _ = image.shape
    current_action = ""
    
    # Визуальные границы
    cv2.line(image, (0, h // 3), (w, h // 3), (100, 100, 100), 1)
    cv2.line(image, (0, 2 * h // 3), (w, 2 * h // 3), (100, 100, 100), 1)
    cv2.rectangle(image, (frame_reduction, frame_reduction), 
                  (w - frame_reduction, h - frame_reduction), (255, 0, 255), 1)

    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_image)

    if results.multi_hand_landmarks:
        # Проверка выхода (две руки соприкасаются большим пальцем и мизинцем)
        exit_gestures = 0
        for hand_lms in results.multi_hand_landmarks:
            t_p = hand_lms.landmark[4]
            p_p = hand_lms.landmark[20]
            if math.hypot((t_p.x - p_p.x) * w, (t_p.y - p_p.y) * h) < 45:
                exit_gestures += 1
        if exit_gestures >= 2: running = False

        # Управление основной рукой
        main_hand = results.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(image, main_hand, mp_hands.HAND_CONNECTIONS)
        lm = main_hand.landmark
        
        # 1. ОПРЕДЕЛЕНИЕ КУЛАКА
        is_fist = (lm[8].y > lm[6].y and lm[12].y > lm[10].y and 
                   lm[16].y > lm[14].y and lm[20].y > lm[18].y)
        
        # Координаты пальцев
        ttx, tty = int(lm[4].x * w), int(lm[4].y * h)
        itx, ity = int(lm[8].x * w), int(lm[8].y * h)
        mtx, mty = int(lm[12].x * w), int(lm[12].y * h)
        rtx, rty = int(lm[16].x * w), int(lm[16].y * h)

        # Движение курсора по точке 9 (центр ладони)
        x_map = np.interp(lm[9].x * w, (frame_reduction, w - frame_reduction), (0, screen_w))
        y_map = np.interp(lm[9].y * h, (frame_reduction, h - frame_reduction), (0, screen_h))
        c_locX = p_locX + (x_map - p_locX) / smoothening
        c_locY = p_locY + (y_map - p_locY) / smoothening
        
        try:
            pyautogui.moveTo(c_locX, c_locY, _pause=False)
        except pyautogui.FailSafeException:
            running = False
            
        p_locX, p_locY = c_locX, c_locY

        # 2. СКРОЛЛИНГ
        if is_fist:
            current_action = "SCROLL"
            if lm[9].y * h < h // 3:
                pyautogui.scroll(10) # На Mac значения скролла меньше, чем на Win
            elif lm[9].y * h > 2 * h // 3:
                pyautogui.scroll(-10)
        
        else:
            # 3. КЛИКИ
            d_idx = math.hypot(itx - ttx, ity - tty)
            d_mid = math.hypot(mtx - ttx, mty - tty)
            d_rng = math.hypot(rtx - ttx, rty - tty)

            # Двойной клик
            if d_idx < 40 and d_mid < 40:
                current_action = "DOUBLE"
                if double_ready:
                    pyautogui.doubleClick()
                    double_ready = False
            else:
                double_ready = True
                
                # ПКМ
                if d_rng < 40:
                    current_action = "RIGHT"
                    if right_ready:
                        pyautogui.rightClick()
                        right_ready = False
                else:
                    right_ready = True
                
                # Зажатие (Drag)
                if d_mid < 40:
                    current_action = "DRAG"
                    if not is_pressed:
                        pyautogui.mouseDown()
                        is_pressed = True
                else:
                    if is_pressed:
                        pyautogui.mouseUp()
                        is_pressed = False
                
                # ЛКМ
                if d_idx < 40:
                    current_action = "CLICK"
                    if click_ready:
                        pyautogui.click()
                        click_ready = False
                else:
                    click_ready = True

    draw_ui(image, current_action)
    cv2.imshow(WINDOW_NAME, image)
    
    # Резервный выход через OpenCV
    if cv2.waitKey(1) & 0xFF == ord('q'): 
        break

# Завершение
cap.release()
cv2.destroyAllWindows()
listener.stop()
sys.exit()