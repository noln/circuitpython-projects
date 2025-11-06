"""
FINAL TOUCH – 128x128 RAW
100Hz refresh, no redraw if position same
"""
import board
import digitalio
import busio
import time
import displayio
from adafruit_display_text import label
import terminalio
from adafruit_display_shapes.circle import Circle

# === DISPLAY ===
display = board.DISPLAY
group = displayio.Group()
display.root_group = group

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

# === READ 7 BYTES ===
def read_touch():
    i2c.try_lock()
    try:
        i2c.writeto(0x15, bytes([0x00]))
        result = bytearray(7)
        i2c.readfrom_into(0x15, result)
        return result
    finally:
        i2c.unlock()

# === CIRCLE ===
touch_circle = None
last_x = -1
last_y = -1

# === LABEL ===
msg = label.Label(
    terminalio.FONT,
    scale=2,
    color=0x00FF00,
    text="Touch me",
    anchor_point=(0.5, 0.5),
    anchored_position=(120, 120)
)
group.append(msg)

# === MAIN LOOP ===
while True:
    data = read_touch()
    if data and len(data) >= 7 and data[1] >= 1:
        raw_x = data[4]  # B4 = X (0–128)
        raw_y = data[6]  # B6 = Y (0–128)

        # === ONLY UPDATE IF POSITION CHANGED ===
        if raw_x != last_x or raw_y != last_y:
            # Remove old circle
            if touch_circle and touch_circle in group:
                group.remove(touch_circle)

            # Draw new circle
            touch_circle = Circle(raw_x, raw_y, 15, fill=0xFFFFFF, outline=0x00FFFF)
            group.append(touch_circle)

            # Update last known position
            last_x = raw_x
            last_y = raw_y

            # Update text
            msg.text = f"{raw_x},{raw_y}"
            msg.color = 0x00FF00
    else:
        # No touch
        if touch_circle and touch_circle in group:
            group.remove(touch_circle)
            touch_circle = None
        if last_x != -1 or last_y != -1:
            msg.text = "Touch me"
            msg.color = 0xFFFF00
            last_x = -1
            last_y = -1

    time.sleep(0.01)  # 100Hz refresh