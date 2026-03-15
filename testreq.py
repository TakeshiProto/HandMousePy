import mediapipe as mp
try:
    hands = mp.solutions.hands.Hands()
    print("MediaPipe успешно инициализирован!")
except Exception as e:
    print(f"Ошибка: {e}")
