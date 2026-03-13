#!/usr/bin/env python3
"""
Pixel Art Weather Icons for 64x64 RGB Matrix Display
Hand-drawn using PIL for crisp pixel-perfect rendering.
"""
from PIL import Image, ImageDraw, ImageFont

# Color palette for weather icons
COLORS = {
    "sun_yellow": (255, 220, 50),
    "sun_orange": (255, 180, 0),
    "sun_core": (255, 255, 150),
    "moon_white": (240, 240, 230),
    "moon_gray": (200, 200, 190),
    "cloud_white": (255, 255, 255),
    "cloud_gray": (180, 180, 190),
    "cloud_dark": (100, 100, 120),
    "rain_blue": (100, 150, 255),
    "rain_light": (150, 200, 255),
    "snow_white": (255, 255, 255),
    "snow_blue": (200, 220, 255),
    "lightning": (255, 255, 100),
    "sky_day": (70, 130, 200),
    "sky_night": (20, 30, 60),
    "sky_sunset": (255, 120, 80),
    "text_white": (255, 255, 255),
    "text_yellow": (255, 230, 100),
    "mist_gray": (180, 180, 200),
}

def draw_sun(draw, cx, cy, radius, rays=True):
    """Draw a pixel-art sun"""
    # Sun core (circle)
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            if x*x + y*y <= radius*radius:
                dist = (x*x + y*y) ** 0.5
                if dist < radius * 0.5:
                    color = COLORS["sun_core"]
                elif dist < radius * 0.8:
                    color = COLORS["sun_yellow"]
                else:
                    color = COLORS["sun_orange"]
                draw.point((cx + x, cy + y), fill=color)
    
    # Sun rays
    if rays:
        ray_length = 4
        ray_positions = [
            (0, -radius - 2), (0, radius + 2),
            (-radius - 2, 0), (radius + 2, 0),
            (-radius - 1, -radius - 1), (radius + 1, -radius - 1),
            (-radius - 1, radius + 1), (radius + 1, radius + 1),
        ]
        for dx, dy in ray_positions:
            for i in range(ray_length):
                nx = cx + dx + (1 if dx > 0 else -1 if dx < 0 else 0) * i
                ny = cy + dy + (1 if dy > 0 else -1 if dy < 0 else 0) * i
                if 0 <= nx < 64 and 0 <= ny < 64:
                    draw.point((nx, ny), fill=COLORS["sun_yellow"])

def draw_moon(draw, cx, cy, radius):
    """Draw a pixel-art crescent moon"""
    # Main moon circle
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            if x*x + y*y <= radius*radius:
                # Create crescent by subtracting smaller circle offset to the right
                shadow_cx = cx + radius // 2
                shadow_dist = ((cx + x - shadow_cx)**2 + (cy + y - cy)**2) ** 0.5
                if shadow_dist > radius * 0.8:
                    draw.point((cx + x, cy + y), fill=COLORS["moon_white"])

def draw_cloud(draw, cx, cy, size="medium", dark=False):
    """Draw a pixel-art cloud"""
    color = COLORS["cloud_dark"] if dark else COLORS["cloud_white"]
    outline_color = COLORS["cloud_gray"] if not dark else (60, 60, 80)
    
    if size == "small":
        circles = [(0, 0, 5), (-4, 2, 4), (4, 2, 4)]
    elif size == "large":
        circles = [(0, 0, 9), (-8, 3, 7), (8, 3, 7), (-4, 5, 6), (4, 5, 6)]
    else:  # medium
        circles = [(0, 0, 7), (-6, 2, 5), (6, 2, 5), (0, 4, 5)]
    
    # Draw cloud puffs
    for dx, dy, r in circles:
        for y in range(-r, r + 1):
            for x in range(-r, r + 1):
                if x*x + y*y <= r*r:
                    px, py = cx + dx + x, cy + dy + y
                    if 0 <= px < 64 and 0 <= py < 64:
                        # Slight outline effect
                        if x*x + y*y > (r-1)*(r-1):
                            draw.point((px, py), fill=outline_color)
                        else:
                            draw.point((px, py), fill=color)

def draw_rain(draw, cx, cy, heavy=False):
    """Draw rain drops"""
    drops = 8 if heavy else 5
    color = COLORS["rain_blue"]
    
    import random
    random.seed(42)  # Consistent pattern
    for _ in range(drops):
        x = cx + random.randint(-12, 12)
        y = cy + random.randint(-5, 10)
        length = random.randint(3, 6) if heavy else random.randint(2, 4)
        for i in range(length):
            if 0 <= x < 64 and 0 <= y + i < 64:
                draw.point((x, y + i), fill=color)

def draw_snow(draw, cx, cy, heavy=False):
    """Draw snowflakes"""
    flakes = 10 if heavy else 6
    
    import random
    random.seed(42)
    for _ in range(flakes):
        x = cx + random.randint(-15, 15)
        y = cy + random.randint(-8, 12)
        size = random.choice([1, 2])
        color = COLORS["snow_white"] if random.random() > 0.3 else COLORS["snow_blue"]
        if size == 1:
            if 0 <= x < 64 and 0 <= y < 64:
                draw.point((x, y), fill=color)
        else:
            # Small cross for larger flakes
            for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
                if 0 <= x + dx < 64 and 0 <= y + dy < 64:
                    draw.point((x + dx, y + dy), fill=color)

def draw_lightning(draw, cx, cy):
    """Draw a lightning bolt"""
    bolt = [
        (0, 0), (2, 0), (0, 3), (3, 3), (-2, 8), (0, 5), (-2, 5), (0, 0)
    ]
    for i in range(len(bolt) - 1):
        x1, y1 = bolt[i]
        x2, y2 = bolt[i + 1]
        draw.line([(cx + x1, cy + y1), (cx + x2, cy + y2)], fill=COLORS["lightning"], width=1)

def draw_mist_lines(draw, y_start, count=4):
    """Draw horizontal mist/fog lines"""
    for i in range(count):
        y = y_start + i * 5
        # Varying length lines
        lengths = [35, 45, 30, 40]
        x_start = (64 - lengths[i % 4]) // 2
        for x in range(x_start, x_start + lengths[i % 4]):
            if (x + i) % 3 != 0:  # Dotted effect
                draw.point((x, y), fill=COLORS["mist_gray"])


def create_weather_icon(condition: str, size: int = 64) -> Image.Image:
    """
    Create a weather icon image for the given condition.
    
    Conditions:
        clear_day, clear_night, partly_cloudy_day, partly_cloudy_night,
        cloudy, overcast, rain, rain_day, rain_night, thunderstorm,
        snow, mist
    """
    # Determine background
    is_night = "night" in condition
    bg_color = COLORS["sky_night"] if is_night else COLORS["sky_day"]
    
    img = Image.new("RGB", (size, size), bg_color)
    draw = ImageDraw.Draw(img)
    
    if condition == "clear_day":
        draw_sun(draw, 32, 25, 12, rays=True)
        
    elif condition == "clear_night":
        draw_moon(draw, 32, 25, 12)
        # Add some stars
        stars = [(10, 10), (50, 15), (15, 40), (48, 38), (25, 8), (42, 45)]
        for sx, sy in stars:
            draw.point((sx, sy), fill=COLORS["moon_white"])
            
    elif condition == "partly_cloudy_day":
        draw_sun(draw, 40, 18, 10, rays=True)
        draw_cloud(draw, 28, 30, size="medium")
        
    elif condition == "partly_cloudy_night":
        draw_moon(draw, 40, 18, 10)
        draw_cloud(draw, 28, 30, size="medium")
        
    elif condition == "cloudy":
        draw_cloud(draw, 32, 22, size="medium")
        draw_cloud(draw, 22, 32, size="small")
        draw_cloud(draw, 42, 34, size="small")
        
    elif condition == "overcast":
        draw_cloud(draw, 32, 18, size="large", dark=True)
        draw_cloud(draw, 20, 30, size="medium", dark=True)
        draw_cloud(draw, 44, 32, size="medium", dark=True)
        
    elif condition in ("rain", "rain_day", "rain_night"):
        if "day" in condition:
            draw_sun(draw, 45, 12, 7, rays=False)
        elif "night" in condition:
            draw_moon(draw, 45, 12, 7)
        draw_cloud(draw, 28, 20, size="medium", dark=True)
        draw_rain(draw, 28, 38, heavy=False)
        
    elif condition == "thunderstorm":
        draw_cloud(draw, 32, 15, size="large", dark=True)
        draw_lightning(draw, 30, 30)
        draw_rain(draw, 32, 42, heavy=True)
        
    elif condition == "snow":
        draw_cloud(draw, 32, 18, size="medium", dark=False)
        draw_snow(draw, 32, 40, heavy=False)
        
    elif condition == "mist":
        draw_mist_lines(draw, 20, count=6)
        
    else:
        # Default: clear day
        draw_sun(draw, 32, 25, 12, rays=True)
    
    return img


def create_weather_display(weather_data: dict, size: int = 64) -> Image.Image:
    """
    Create a complete weather display with icon and temperature.
    
    weather_data should contain:
        - condition or icon_code
        - temp
        - temp_unit
        - city (optional)
    """
    from weather_service import get_condition_from_code
    
    # Get condition from icon code if not directly provided
    condition = weather_data.get("condition_name")
    if not condition and "icon_code" in weather_data:
        condition = get_condition_from_code(weather_data["icon_code"])
    if not condition:
        condition = "clear_day"
    
    # Create base with weather icon (top portion)
    is_night = "night" in condition
    bg_color = COLORS["sky_night"] if is_night else COLORS["sky_day"]
    
    img = Image.new("RGB", (size, size), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Draw weather icon in top portion (shifted down a bit)
    icon_img = create_weather_icon(condition, size)
    # Paste icon shifted down by 5 pixels to use top space
    img.paste(icon_img.crop((0, 0, size, 38)), (0, 5))
    
    # Draw temperature
    temp = weather_data.get("temp", "??")
    unit = weather_data.get("temp_unit", "°C")
    temp_text = f"{temp}{unit}"
    
    # Try to load a pixel font, fallback to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except:
        font = ImageFont.load_default()
    
    # Center the temperature text
    bbox = draw.textbbox((0, 0), temp_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = (size - text_width) // 2
    
    # Draw temperature with shadow for readability
    draw.text((text_x + 1, 46), temp_text, fill=(0, 0, 0), font=font)
    draw.text((text_x, 45), temp_text, fill=COLORS["text_white"], font=font)
    
    # Show city name at top (better visibility)
    city = weather_data.get("city", "")
    if city and len(city) <= 12:
        try:
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 9)
        except:
            small_font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), city, font=small_font)
        city_width = bbox[2] - bbox[0]
        city_x = (size - city_width) // 2
        # White text with dark shadow at top
        draw.text((city_x + 1, 1), city, fill=(0, 0, 0), font=small_font)
        draw.text((city_x, 0), city, fill=COLORS["text_white"], font=small_font)
    
    return img


# Preview all icons when run directly
if __name__ == "__main__":
    import os
    
    conditions = [
        "clear_day", "clear_night", 
        "partly_cloudy_day", "partly_cloudy_night",
        "cloudy", "overcast", 
        "rain", "rain_day", "rain_night",
        "thunderstorm", "snow", "mist"
    ]
    
    # Create preview directory
    os.makedirs("weather_icons_preview", exist_ok=True)
    
    for cond in conditions:
        img = create_weather_icon(cond)
        img.save(f"weather_icons_preview/{cond}.png")
        print(f"Created: {cond}.png")
    
    # Create sample weather display
    sample_weather = {
        "icon_code": "02d",
        "temp": 22,
        "temp_unit": "°C",
        "city": "London"
    }
    display = create_weather_display(sample_weather)
    display.save("weather_icons_preview/sample_display.png")
    print("Created: sample_display.png")
    
    print(f"\nPreview images saved to: weather_icons_preview/")
