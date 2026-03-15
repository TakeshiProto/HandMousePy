try:
    import mediapipe as mp
    # В новых версиях импорт выглядит именно так:
    mp_hands = mp.solutions.hands
    print("Успех! MediaPipe.solutions доступен.")
except AttributeError:
    print("Ошибка: Атрибут solutions не найден. Похоже, установка всё еще повреждена.")
except Exception as e:
    print(f"Другая ошибка: {e}")