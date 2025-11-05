"""
Combined example: animated circle + METAR + live QMI8658C IMU display (for Waveshare ESP32-S3 Development Board, with 1.28inch Round Touch LCD)
"""
import gc
import time
import board
import displayio
import pwmio
import wifi
import socketpool
import adafruit_requests
from adafruit_display_text import label
import terminalio
import ssl
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import qmi8658c

# Change IO2 to the pin shown in your schematic if different
bl = pwmio.PWMOut(board.IO2, frequency=1000, duty_cycle=0)
def set_brightness(percent: int):
    """0 = off, 100 = full bright"""
    percent = max(0, min(100, percent))
    bl.duty_cycle = int(65535 * percent / 100)
# Example
set_brightness(30)

from adafruit_display_shapes.circle import Circle

# use built in display (MagTag, PyPortal, PyGamer, PyBadge, CLUE, etc.)
display = board.DISPLAY

# Make the display context
main_group = displayio.Group()

# --- BITMAP BACKGROUND (centered, scaled to fit) ---
bitmap_ok = False # ← Track success
try:
    # Load 24-bit BMP created on macOS with: sips -s format bmp --out bg24.bmp --setProperty formatOptions 24 bg.bmp
    bg_bitmap = displayio.OnDiskBitmap("bmps/gradient_button_0.bmp") # <-- MUST be 24-bit RGB BMP
    bg_tile = displayio.TileGrid(
        bg_bitmap,
        pixel_shader=displayio.ColorConverter(), # 24-bit → RGB888
        width=6,
        height=6,
        tile_width=bg_bitmap.width,
        tile_height=bg_bitmap.height,
        default_tile=0
    )
    # Center the bitmap on screen
    #bg_tile.x = (display.width - bg_bitmap.width) // 2
    #bg_tile.y = (display.height - bg_bitmap.height) // 2
    main_group.append(bg_tile)
    bitmap_ok = True
    print(f"Background loaded: {bg_bitmap.width}x{bg_bitmap.height}")
except Exception as e:
    print("Failed to load bg24.bmp:", e)
    # Fallback: solid black
    color_bitmap = displayio.Bitmap(display.width, display.height, 1)
    color_palette = displayio.Palette(1)
    color_palette[0] = 0x000000
    bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
    main_group.append(bg_sprite)

# Setting up the Circle starting position
posx = 50
posy = 50
# Define Circle characteristics
circle_radius = 20
circle = Circle(posx, posy, circle_radius, fill=0x00FF00, outline=0xFF00FF)
main_group.append(circle)

# Define Circle Animation Steps
delta_x = 2
delta_y = 2

# --- WiFi and internet setup (safe for web workflow) ---
# Assumes WiFi is already connected via settings.toml
if not wifi.radio.connected:
    raise RuntimeError("WiFi not connected! Check settings.toml")
print("Using existing WiFi. IP:", wifi.radio.ipv4_address)
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

# --- METAR label (centered, multi-line) ---
metar_label = label.Label(
    terminalio.FONT,
    text="Fetching METAR...",
    color=0xFFFFFF,
    anchor_point=(0.5, 0.5),
    anchored_position=(display.width // 2, display.height // 2),
    line_spacing=0.8
)
metar_label.scale = 2
main_group.append(metar_label)

# --- IMU setup ---
i2c = board.I2C()                     # Auto-uses SCL=GP7, SDA=GP6 on Waveshare board
sensor = qmi8658c.QMI8658C(i2c)

# IMU display labels – **static, centered inside the *visible* circular area**
# (x = display.width//2, y = 30/45/60 – well inside the circle, no corner clipping)
imu_accel_label = label.Label(
    terminalio.FONT,
    text="",
    color=0xFFFF00,
    anchor_point=(0.5, 0.5),
    anchored_position=(display.width // 2, 30),
    scale=1
)
imu_gyro_label = label.Label(
    terminalio.FONT,
    text="",
    color=0x00FFFF,
    anchor_point=(0.5, 0.5),
    anchored_position=(display.width // 2, 45),
    scale=1
)
imu_temp_label = label.Label(
    terminalio.FONT,
    text="",
    color=0xFF00FF,
    anchor_point=(0.5, 0.5),
    anchored_position=(display.width // 2, 60),
    scale=1
)
main_group.append(imu_accel_label)
main_group.append(imu_gyro_label)
main_group.append(imu_temp_label)

# --- Fetch METAR once at startup ---
def fetch_metar():
    try:
        response = requests.get("https://aviationweather.gov/api/data/metar?ids=CYXE")
        metar_text = response.text.strip()
        response.close()
        if not metar_text or "error" in metar_text.lower():
            return "No METAR"
        words = metar_text.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + (1 if current_line else 0) > 12:
                if current_line:
                    lines.append(current_line)
                current_line = word
                if len(lines) >= 5:
                    break
            else:
                if current_line:
                    current_line += " "
                current_line += word
        if current_line:
            lines.append(current_line)
        while len(lines) < 6:
            lines.append("")
        lines = lines[:6]
        # ← ADD * OR ^ TO FIRST LINE
        if lines[0]:
            if not bitmap_ok:
                lines[0] = "*" + lines[0]
            else:
                lines[0] = "^" + lines[0]
        return "\n".join(lines)
    except ValueError:
        return "Err: SSL"
    except Exception as e:
        return f"Err: {type(e).__name__}"

current_metar = fetch_metar()
metar_label.text = current_metar

# Showing the items on the screen
display.root_group = main_group

last_metar_update = time.monotonic()
last_imu_update = 0.0
IMU_REFRESH_RATE = 0.1   # 10 Hz (increased from 1 Hz)

while True:
    # ----- Circle bounce animation -----
    if circle.y + circle_radius >= display.height - circle_radius:
        delta_y = -1
    if circle.x + circle_radius >= display.width - circle_radius:
        delta_x = -1
    if circle.x - circle_radius <= 0 - circle_radius:
        delta_x = 1
    if circle.y - circle_radius <= 0 - circle_radius:
        delta_y = 1
    circle.x = circle.x + delta_x
    circle.y = circle.y + delta_y

    # ----- METAR periodic refresh (every 5 min) -----
    if time.monotonic() - last_metar_update > 300:
        current_metar = fetch_metar()
        metar_label.text = current_metar
        last_metar_update = time.monotonic()

    # ----- IMU update (10 Hz) -----
    if time.monotonic() - last_imu_update >= IMU_REFRESH_RATE:
        ac = sensor.acceleration
        gy = sensor.gyro
        temp = sensor.temperature

        imu_accel_label.text = f"A:{ac[0]:+5.1f} {ac[1]:+5.1f} {ac[2]:+5.1f}"
        imu_gyro_label.text  = f"G:{gy[0]:+5.1f} {gy[1]:+5.1f} {gy[2]:+5.1f}"
        imu_temp_label.text  = f"T:{temp:5.1f}°C"

        last_imu_update = time.monotonic()

    time.sleep(0.001)
    gc.collect()