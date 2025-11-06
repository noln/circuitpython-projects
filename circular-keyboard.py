"""
CIRCULAR EDGE KEYBOARD – DARK TURQUOISE BAR BEHIND TEXT (NO CRASH)
"""
import board
import digitalio
import busio
import time
import displayio
import pwmio
import math
import random
from adafruit_display_text import label
import terminalio
from adafruit_display_shapes.circle import Circle
from adafruit_display_shapes.line import Line
from adafruit_display_shapes.rect import Rect

# === DISPLAY ===
display = board.DISPLAY
group = displayio.Group()
display.root_group = group

# === BRIGHTNESS ===
bl = pwmio.PWMOut(board.IO2, frequency=1000, duty_cycle=0)
def set_brightness(percent: int):
    percent = max(0, min(100, percent))
    bl.duty_cycle = int(65535 * percent / 100)
set_brightness(90)

# === PINS ===
reset_pin = digitalio.DigitalInOut(board.IO13)
reset_pin.direction = digitalio.Direction.OUTPUT
int_pin = digitalio.DigitalInOut(board.IO5)
int_pin.direction = digitalio.Direction.INPUT
int_pin.pull = digitalio.Pull.UP
i2c = board.I2C()

# === RESET & INIT ===
reset_pin.value = False
time.sleep(0.05)
reset_pin.value = True
time.sleep(0.05)

def write_reg(reg, val):
    i2c.try_lock()
    try:
        i2c.writeto(0x15, bytes([reg, val]))
    finally:
        i2c.unlock()

write_reg(0xA5, 0x00)
time.sleep(0.01)
write_reg(0xFE, 0x01)
time.sleep(0.01)
write_reg(0xA5, 0x01)
time.sleep(0.1)

def read_touch():
    i2c.try_lock()
    try:
        i2c.writeto(0x15, bytes([0x00]))
        result = bytearray(7)
        i2c.readfrom_into(0x15, result)
        return result
    finally:
        i2c.unlock()

# === ALPHABET RING ===
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ "
RING_RADIUS = 100
CENTER_RADIUS = 40
CENTER_X = 120
CENTER_Y = 120
LETTER_RADIUS = 115
TYPED_Y = CENTER_Y + 60

# === STATE ===
typed_text = ""
current_letter = "A"
touch_circle = None
in_center = False
pending_letter = None
swipe_start_x = None
last_touch_x = -1
last_touch_y = -1
typed_bg = None  # Bar behind text

# === BLACK CENTER ===
black_center = Circle(CENTER_X, CENTER_Y, CENTER_RADIUS, fill=0x000000)
group.append(black_center)

# === TURQUOISE → PURPLE SPIDER WEB GRADIENT ===
random.seed(42)
for arm in range(8):
    angle = math.radians(arm * 45)
    for r in range(CENTER_RADIUS + 10, RING_RADIUS, 8):
        jitter = random.randint(-3, 3)
        x1 = CENTER_X + (r + jitter) * math.cos(angle)
        y1 = CENTER_Y + (r + jitter) * math.sin(angle)
        x2 = CENTER_X + (r + 8 + jitter) * math.cos(angle)
        y2 = CENTER_Y + (r + 8 + jitter) * math.sin(angle)
        t = (r - (CENTER_RADIUS + 10)) / (RING_RADIUS - CENTER_RADIUS - 10)
        r_val = int(0x40 + t * (0x80 - 0x40))
        g_val = int(0xE0 + t * (0x00 - 0xE0))
        b_val = int(0xD0 + t * (0x80 - 0xD0))
        color = (r_val << 16) | (g_val << 8) | b_val
        group.append(Line(int(x1), int(y1), int(x2), int(y2), color=color))

for r in range(CENTER_RADIUS + 15, RING_RADIUS, 12):
    points = []
    for seg in range(32):
        angle = math.radians(seg * 360 / 32)
        jitter = random.randint(-4, 4)
        x = CENTER_X + (r + jitter) * math.cos(angle)
        y = CENTER_Y + (r + jitter) * math.sin(angle)
        points.append((int(x), int(y)))
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        t = (r - (CENTER_RADIUS + 15)) / (RING_RADIUS - CENTER_RADIUS - 15)
        r_val = int(0x40 + t * (0x80 - 0x40))
        g_val = int(0xE0 + t * (0x00 - 0xE0))
        b_val = int(0xD0 + t * (0x80 - 0xD0))
        color = (r_val << 16) | (g_val << 8) | b_val
        group.append(Line(x1, y1, x2, y2, color=color))

# === OUTLINES ===
center_outline = Circle(CENTER_X, CENTER_Y, CENTER_RADIUS, outline=0xFFFFFF)
group.append(center_outline)
ring_outline = Circle(CENTER_X, CENTER_Y, RING_RADIUS, outline=0xFFFFFF)
group.append(ring_outline)

# === LETTER LABELS ===
letter_labels = []
for i, letter in enumerate(ALPHABET):
    angle = math.radians(i * 360 / len(ALPHABET) - 90 + 90)
    x = CENTER_X + LETTER_RADIUS * math.cos(angle)
    y = CENTER_Y + LETTER_RADIUS * math.sin(angle)
    lbl = label.Label(
        terminalio.FONT,
        scale=1,
        color=0xFFFFFF,
        text=letter,
        anchor_point=(0.5, 0.5),
        anchored_position=(int(x), int(y))
    )
    group.append(lbl)
    letter_labels.append(lbl)

# === BIG CENTER LETTER ===
big_letter = label.Label(
    terminalio.FONT,
    scale=4,
    color=0x00FF00,
    text=current_letter,
    anchor_point=(0.5, 0.5),
    anchored_position=(CENTER_X, CENTER_Y)
)
group.append(big_letter)

# === TYPED TEXT (ADDED ONCE) ===
typed_label = label.Label(
    terminalio.FONT,
    scale=2,
    color=0xFFFFFF,
    text=typed_text,
    anchor_point=(0.5, 0),
    anchored_position=(CENTER_X, TYPED_Y)
)
group.append(typed_label)  # ← ADDED ONCE

# === MAIN LOOP ===
while True:
    data = read_touch()
    now_touch = data and len(data) >= 7 and data[1] >= 1

    if now_touch:
        raw_x = data[4]
        raw_y = data[6]

        dx = raw_x - CENTER_X
        dy = raw_y - CENTER_Y
        distance = math.sqrt(dx*dx + dy*dy)
        angle = math.atan2(dy, dx)
        if angle < 0:
            angle += 2 * math.pi
        angle_deg = int(math.degrees(angle))

        if distance > RING_RADIUS - 20:
            letter_angle = angle + math.pi
            letter_angle_deg = int(math.degrees(letter_angle)) % 360
            letter_index = int((letter_angle_deg + 6.666) // 13.333) % 27

            new_letter = ALPHABET[letter_index]
            if new_letter != current_letter:
                current_letter = new_letter
                big_letter.text = current_letter

            for i, lbl in enumerate(letter_labels):
                lbl.color = 0x00FF00 if i == letter_index else 0xFFFFFF

            touch_x = int(CENTER_X + RING_RADIUS * math.cos(angle))
            touch_y = int(CENTER_Y + RING_RADIUS * math.sin(angle))
            if touch_x != last_touch_x or touch_y != last_touch_y:
                if touch_circle and touch_circle in group:
                    group.remove(touch_circle)
                touch_circle = Circle(touch_x, touch_y, 12, fill=0xFFFF00)
                group.append(touch_circle)
                last_touch_x = touch_x
                last_touch_y = touch_y

        now_in_center = distance < CENTER_RADIUS
        if now_in_center:
            pending_letter = current_letter

        if in_center and swipe_start_x is None:
            swipe_start_x = raw_x
        elif in_center and raw_x < swipe_start_x - 30:
            if typed_text:
                typed_text = typed_text[:-1]
                typed_label.text = typed_text
            swipe_start_x = None

        in_center = now_in_center

    else:
        if in_center and pending_letter:
            typed_text += pending_letter
            typed_label.text = typed_text
            pending_letter = None

            # === UPDATE BAR BEHIND TEXT (NO RE-ADD LABEL) ===
            if typed_bg and typed_bg in group:
                group.remove(typed_bg)
            text_width = len(typed_text) * 14
            bar_x = CENTER_X - text_width // 2 - 8
            bar_y = TYPED_Y - 3
            typed_bg = Rect(bar_x, bar_y, text_width + 16, 30, fill=0x008080)
            group.insert(group.index(typed_label), typed_bg)  # ← INSERT BEHIND LABEL

        if touch_circle and touch_circle in group:
            group.remove(touch_circle)
            touch_circle = None
            last_touch_x = -1
            last_touch_y = -1

        swipe_start_x = None
        in_center = False
        for lbl in letter_labels:
            lbl.color = 0xFFFFFF

    time.sleep(0.01)