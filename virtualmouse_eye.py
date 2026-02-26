import cv2
import mediapipe as mp
import pyautogui
import math
import time
from screen_brightness_control import get_brightness, set_brightness
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# Setup
cam = cv2.VideoCapture(0)
face_mesh = mp.solutions.face_mesh.FaceMesh(refine_landmarks=True)
screen_w, screen_h = pyautogui.size()

# Volume Control Setup
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume_control = cast(interface, POINTER(IAudioEndpointVolume))

# State variables
reading_mode = False
mouse_held = False
last_click_time = 0
last_brightness_adjust_time = 0
last_volume_adjust_time = 0

# Reading mode toggle button
button_top_left = (1103, 25)
button_bottom_right = (1255, 65)

def on_mouse_click(event, x, y, flags, param):
    global reading_mode
    if event == cv2.EVENT_LBUTTONDOWN:
        if button_top_left[0] <= x <= button_bottom_right[0] and button_top_left[1] <= y <= button_bottom_right[1]:
            reading_mode = not reading_mode
            print("Reading Mode Activated!" if reading_mode else "Reading Mode Terminated!")

cv2.namedWindow("Sign Bridge: WL")
cv2.setMouseCallback("Sign Bridge: WL", on_mouse_click)

while True:
    _, frame = cam.read()
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    output = face_mesh.process(rgb_frame)

    # Draw Reading Mode Button
    cv2.rectangle(frame, button_top_left, button_bottom_right, (0, 255, 0), -1)
    button_text = "Reading Mode"
    text_size = cv2.getTextSize(button_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
    text_x = button_top_left[0] + (button_bottom_right[0] - button_top_left[0] - text_size[0]) // 2
    text_y = button_top_left[1] + (button_bottom_right[1] - button_top_left[1] + text_size[1]) // 2
    cv2.putText(frame, button_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    landmarks_points = output.multi_face_landmarks
    frame_h, frame_w, _ = frame.shape
    if landmarks_points:
        landmarks = landmarks_points[0].landmark

        # Cursor movement using eye landmarks
        for index, landmark in enumerate(landmarks[474:478]):
            x = int(landmark.x * frame_w)
            y = int(landmark.y * frame_h)
            cv2.circle(frame, (x, y), 3, (0, 255, 0))
            if index == 1:
                screen_x = screen_w / frame_w * x
                screen_y = screen_h / frame_h * y
                pyautogui.moveTo(screen_x, screen_y)

        # Blink-based click
        left = [landmarks[145], landmarks[159]]
        right = [landmarks[475], landmarks[477]]
        for landmark in left:
            x = int(landmark.x * frame_w)
            y = int(landmark.y * frame_h)
            cv2.circle(frame, (x, y), 3, (0, 255, 255))
        for landmark in right:
            x = int(landmark.x * frame_w)
            y = int(landmark.y * frame_h)
            cv2.circle(frame, (x, y), 3, (0, 0, 255))

        current_time = time.time()

        if reading_mode:
            dist_cent = (screen_y - (frame.shape[0] / 2)) / 20
            pyautogui.vscroll(dist_cent)

        if (right[0].y - right[1].y) > -0.024 and current_time - last_click_time > 1:
            print("Right Click")
            pyautogui.rightClick()
            last_click_time = current_time
        elif (left[0].y - left[1].y) < 0.01 and current_time - last_click_time > 1:
            print("Left Click")
            pyautogui.click()
            last_click_time = current_time

        # Tongue out + left wink = click and hold
        upper_lip = landmarks[13]
        lower_lip = landmarks[14]
        left_eye_top = landmarks[159]
        left_eye_bottom = landmarks[145]

        lip_dist = math.sqrt((upper_lip.x - lower_lip.x)**2 + (upper_lip.y - lower_lip.y)**2)
        left_eye_ratio = abs(left_eye_top.y - left_eye_bottom.y)

        if lip_dist > 0.05 and left_eye_ratio < 0.015:
            if not mouse_held:
                print("Click and Hold STARTED")
                pyautogui.mouseDown()
                mouse_held = True
        else:
            if mouse_held:
                print("Click and Hold RELEASED")
                pyautogui.mouseUp()
                mouse_held = False

        # Brightness Control (eyebrow height)
        left_eyebrow = landmarks[65]
        eyebrow_eye_dist = abs(left_eyebrow.y - left_eye_top.y)
        if current_time - last_brightness_adjust_time > 1:
            try:
                current_brightness = get_brightness()[0]
                if eyebrow_eye_dist > 0.045:
                    print("Increasing Brightness")
                    set_brightness(min(current_brightness + 10, 100))
                    last_brightness_adjust_time = current_time
                elif eyebrow_eye_dist < 0.030:
                    print("Decreasing Brightness")
                    set_brightness(max(current_brightness - 10, 10))
                    last_brightness_adjust_time = current_time
            except Exception as e:
                print("Brightness error:", e)

        # Volume Control via Head Turn (Nose X Position)
        nose = landmarks[1]
        nose_x = nose.x * frame_w

        center_tolerance = 30  # pixels from center
        volume_step = 0.1
        current_volume = volume_control.GetMasterVolumeLevelScalar()

        if current_time - last_volume_adjust_time > 1:
            if nose_x < frame_w / 2 - center_tolerance:
                print("Turning Head LEFT - Volume Down")
                volume_control.SetMasterVolumeLevelScalar(max(current_volume - volume_step, 0.0), None)
                last_volume_adjust_time = current_time
            elif nose_x > frame_w / 2 + center_tolerance:
                print("Turning Head RIGHT - Volume Up")
                volume_control.SetMasterVolumeLevelScalar(min(current_volume + volume_step, 1.0), None)
                last_volume_adjust_time = current_time

    cv2.imshow("Sign Bridge: WL", frame)
    if cv2.waitKey(1) == 27:  # ESC to exit
        break

cam.release()
cv2.destroyAllWindows()
