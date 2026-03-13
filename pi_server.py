#!/usr/bin/env python3
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import io
import cgi
from PIL import Image, ImageOps, ImageSequence, ImageDraw, ImageFont

from rgbmatrix import RGBMatrix, RGBMatrixOptions
from weather_service import weather_service, get_condition_from_code
from weather_icons import create_weather_display, create_weather_icon

class MatrixHandler:
    def __init__(self):
        opts = RGBMatrixOptions()
        opts.rows = 64
        opts.cols = 64
        opts.chain_length = 1
        opts.parallel = 1
        opts.pwm_bits = 11
        opts.brightness = 70
        opts.hardware_mapping = "regular"
        opts.gpio_slowdown = 4 # Tested with RPI4
        # opts.gpio_slowdown = 2 # Tested with RPI ZERO 2W
        self.matrix = RGBMatrix(options=opts)
        self.rotation = 90  # 0, 90, 180, or 270 degrees clockwise
        self.stop_event = threading.Event()
        self.current_job = None
        self._lock = threading.Lock()
    
    def _stop_current_job(self):
        """Stop any currently running job and wait for it to finish"""
        self.stop_event.set()
        # Wait for the thread to notice the stop event and clean up
        # Give it a bit more time for proper cleanup
        for _ in range(10):  # Max 0.5 seconds
            if self.current_job is None:
                break
            time.sleep(0.05)
    
    def _rotate_image(self, img):
        """Rotate image according to self.rotation setting"""
        if self.rotation == 90:
            return img.transpose(Image.Transpose.ROTATE_270)  # PIL rotates counter-clockwise
        elif self.rotation == 180:
            return img.transpose(Image.Transpose.ROTATE_180)
        elif self.rotation == 270:
            return img.transpose(Image.Transpose.ROTATE_90)
        return img
        
    def show_image_from_url(self, url, duration=0, loops=0):
        """
        Display image from URL.
        
        Args:
            url: Image URL
            duration: Seconds to display. 0 = forever until stopped
            loops: For GIFs, number of loops. 0 = infinite (respects duration if set)
        """
        def worker():
            import tempfile
            import os
            import gc
            temp_file = None
            frames = None
            img = None
            try:
                print(f"[DEBUG] Fetching image from: {url}")
                
                # Create request with proper headers
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'Mozilla/5.0 (compatible; RGB-Matrix-Server/1.0)')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status != 200:
                        print(f"[ERROR] HTTP {response.status} when fetching image")
                        return
                    img_data = response.read()
                    print(f"[DEBUG] Downloaded {len(img_data)} bytes")
                
                # Save to temporary file WITHOUT forcing extension - let PIL detect format
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_file.write(img_data)
                    temp_file = tmp_file.name
                
                img = Image.open(temp_file)
                print(f"[DEBUG] Image format: {img.format}, size: {img.size}, mode: {img.mode}")
                
                # Handle animated GIFs
                if getattr(img, "is_animated", False):
                    frames = []
                    delays = []
                    for frame in ImageSequence.Iterator(img):
                        # Pre-resize and rotate to save memory - store only 64x64 frames
                        resized = ImageOps.fit(frame.convert("RGB"), (64, 64), method=Image.Resampling.LANCZOS)
                        rotated = self._rotate_image(resized)
                        frames.append(rotated.convert('RGB'))
                        delays.append(max(0.01, frame.info.get("duration", 70) / 1000.0))
                    
                    # Close original image to free memory
                    img.close()
                    img = None
                    
                    print(f"[DEBUG] Playing animated GIF with {len(frames)} frames (duration={duration}, loops={loops})")
                    start_time = time.time()
                    frame_idx = 0
                    loop_count = 0
                    while not self.stop_event.is_set():
                        # Check duration limit
                        if duration > 0 and (time.time() - start_time >= duration):
                            break
                        # Check loop limit
                        if loops > 0 and loop_count >= loops:
                            break
                            
                        self.matrix.SetImage(frames[frame_idx])
                        time.sleep(delays[frame_idx])
                        frame_idx = (frame_idx + 1) % len(frames)
                        if frame_idx == 0:
                            loop_count += 1
                else:
                    # Static image - display forever or until duration
                    print(f"[DEBUG] Displaying static image (duration={duration})")
                    resized = ImageOps.fit(img.convert("RGB"), (64, 64), method=Image.Resampling.LANCZOS)
                    rotated = self._rotate_image(resized)
                    img.close()
                    img = None
                    self.matrix.SetImage(rotated.convert('RGB'))
                    start_time = time.time()
                    while not self.stop_event.is_set():
                        if duration > 0 and (time.time() - start_time >= duration):
                            break
                        time.sleep(0.1)
                        
            except Exception as e:
                print(f"[ERROR] Image display failed: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Clean up memory
                if frames:
                    frames.clear()
                if img:
                    try:
                        img.close()
                    except:
                        pass
                # Clean up temporary file
                if temp_file and os.path.exists(temp_file):
                    os.unlink(temp_file)
                self.current_job = None
                gc.collect()  # Force garbage collection
                
        # Stop any current job first
        self._stop_current_job()
        self.stop_event.clear()
        self.current_job = "image"
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        
    def show_image_from_data(self, img_data, duration=0, loops=0):
        """
        Display image from raw bytes (uploaded image).
        
        Args:
            img_data: Raw image bytes
            duration: Seconds to display. 0 = forever until stopped
            loops: For GIFs, number of loops. 0 = infinite (respects duration if set)
        """
        def worker():
            import gc
            frames = None
            img = None
            try:
                print(f"[DEBUG] Processing uploaded image ({len(img_data)} bytes)")
                img = Image.open(io.BytesIO(img_data))
                print(f"[DEBUG] Image format: {img.format}, size: {img.size}, mode: {img.mode}")
                
                # Handle animated GIFs
                if getattr(img, "is_animated", False):
                    frames = []
                    delays = []
                    for frame in ImageSequence.Iterator(img):
                        # Pre-resize and rotate to save memory - store only 64x64 frames
                        resized = ImageOps.fit(frame.convert("RGB"), (64, 64), method=Image.Resampling.LANCZOS)
                        rotated = self._rotate_image(resized)
                        frames.append(rotated.convert('RGB'))
                        delays.append(max(0.01, frame.info.get("duration", 70) / 1000.0))
                    
                    # Close original image to free memory
                    img.close()
                    img = None
                    
                    print(f"[DEBUG] Playing animated GIF with {len(frames)} frames (duration={duration}, loops={loops})")
                    start_time = time.time()
                    frame_idx = 0
                    loop_count = 0
                    while not self.stop_event.is_set():
                        # Check duration limit
                        if duration > 0 and (time.time() - start_time >= duration):
                            break
                        # Check loop limit
                        if loops > 0 and loop_count >= loops:
                            break
                            
                        self.matrix.SetImage(frames[frame_idx])
                        time.sleep(delays[frame_idx])
                        frame_idx = (frame_idx + 1) % len(frames)
                        if frame_idx == 0:
                            loop_count += 1
                else:
                    # Static image - display forever or until duration
                    print(f"[DEBUG] Displaying static image (duration={duration})")
                    resized = ImageOps.fit(img.convert("RGB"), (64, 64), method=Image.Resampling.LANCZOS)
                    rotated = self._rotate_image(resized)
                    img.close()
                    img = None
                    self.matrix.SetImage(rotated.convert('RGB'))
                    start_time = time.time()
                    while not self.stop_event.is_set():
                        if duration > 0 and (time.time() - start_time >= duration):
                            break
                        time.sleep(0.1)
                        
            except Exception as e:
                print(f"[ERROR] Image display failed: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Clean up memory
                if frames:
                    frames.clear()
                if img:
                    try:
                        img.close()
                    except:
                        pass
                self.current_job = None
                gc.collect()  # Force garbage collection
                
        # Stop any current job first
        self._stop_current_job()
        self.stop_event.clear()
        self.current_job = "image"
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        
    def show_text(self, text, duration=0, scroll=False, icon=None, bg_color=(0, 0, 0), text_color=(255, 255, 255)):
        """
        Display text on the matrix.
        
        Args:
            text: Text to display
            duration: Seconds to display. 0 = forever until stopped
            scroll: If True, scroll text horizontally. If False, static centered text
            icon: Optional icon name (info, warning, error, check, heart, star, bell, mail)
            bg_color: Background color tuple (R, G, B)
            text_color: Text color tuple (R, G, B)
        """
        def worker():
            try:
                img = Image.new("RGB", (64, 64), bg_color)
                draw = ImageDraw.Draw(img)
                
                # Draw optional icon
                icon_width = 0
                if icon:
                    icon_width = self._draw_icon(draw, icon, 4, 22)
                    if icon_width > 0:
                        icon_width += 4  # padding after icon
                
                # Calculate text area
                text_area_width = 64 - icon_width - 4
                text_x_start = icon_width + 2
                
                # Auto-scale font size based on text length
                # Try different font sizes until text fits
                font_sizes = [14, 12, 10, 9, 8] if not icon else [10, 9, 8, 7]
                
                best_font = None
                best_lines = []
                best_line_height = 10
                
                for font_size in font_sizes:
                    try:
                        test_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                    except:
                        test_font = ImageFont.load_default()
                        
                    line_height = font_size + 2
                    max_lines = 64 // line_height
                    
                    lines = self._wrap_text(text, test_font, text_area_width)
                    
                    # Check if it fits
                    if len(lines) <= max_lines:
                        best_font = test_font
                        best_lines = lines
                        best_line_height = line_height
                        break
                
                # Fallback if nothing fits - use smallest and truncate
                if not best_font:
                    try:
                        best_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 7)
                    except:
                        best_font = ImageFont.load_default()
                    best_line_height = 9
                    max_lines = 64 // best_line_height
                    best_lines = self._wrap_text(text, best_font, text_area_width)[:max_lines]
                
                # Calculate vertical centering
                total_height = len(best_lines) * best_line_height
                y_start = (64 - total_height) // 2
                
                # Draw each line centered
                for i, line in enumerate(best_lines):
                    bbox = draw.textbbox((0, 0), line, font=best_font)
                    line_width = bbox[2] - bbox[0]
                    x = text_x_start + (text_area_width - line_width) // 2
                    y = y_start + i * best_line_height
                    # Shadow for readability
                    draw.text((x + 1, y + 1), line, fill=(0, 0, 0), font=best_font)
                    draw.text((x, y), line, fill=text_color, font=best_font)
                
                if scroll:
                    # Scrolling mode for long text
                    try:
                        scroll_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
                    except:
                        scroll_font = ImageFont.load_default()
                    scroll_img = Image.new("RGB", (1000, 64), bg_color)
                    scroll_draw = ImageDraw.Draw(scroll_img)
                    scroll_draw.text((64, 24), text, fill=text_color, font=scroll_font)
                    text_w = scroll_draw.textlength(text, font=scroll_font)
                    
                    start_time = time.time()
                    x = 0
                    while not self.stop_event.is_set():
                        if duration > 0 and (time.time() - start_time >= duration):
                            break
                        x = (x + 1) % (int(text_w) + 128)
                        frame = scroll_img.crop((x, 0, x + 64, 64))
                        rotated = self._rotate_image(frame)
                        self.matrix.SetImage(rotated.convert('RGB'))
                        time.sleep(0.03)
                else:
                    # Static display
                    rotated = self._rotate_image(img)
                    self.matrix.SetImage(rotated.convert('RGB'))
                    start_time = time.time()
                    while not self.stop_event.is_set():
                        if duration > 0 and (time.time() - start_time >= duration):
                            break
                        time.sleep(0.1)
                        
            except Exception as e:
                print(f"[ERROR] Text display failed: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.current_job = None
                
        # Stop any current job first
        self._stop_current_job()
        self.stop_event.clear()
        self.current_job = "text"
        t = threading.Thread(target=worker, daemon=True)
        t.start()
    
    def _wrap_text(self, text, font, max_width):
        """Wrap text to fit within max_width"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [text]
    
    def _draw_icon(self, draw, icon_name, x, y):
        """Draw a small icon and return its width"""
        icons = {
            "info": {"color": (0, 150, 255), "shape": "circle", "char": "i"},
            "warning": {"color": (255, 200, 0), "shape": "triangle", "char": "!"},
            "error": {"color": (255, 50, 50), "shape": "circle", "char": "X"},
            "check": {"color": (50, 255, 50), "shape": "circle", "char": "✓"},
            "heart": {"color": (255, 50, 100), "shape": "heart"},
            "star": {"color": (255, 220, 50), "shape": "star"},
            "bell": {"color": (255, 180, 0), "shape": "bell"},
            "mail": {"color": (100, 150, 255), "shape": "mail"},
        }
        
        if icon_name not in icons:
            return 0
        
        icon = icons[icon_name]
        size = 20
        color = icon["color"]
        
        if icon["shape"] == "circle":
            draw.ellipse([x, y, x + size, y + size], fill=color)
            if "char" in icon:
                try:
                    char_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
                except:
                    char_font = ImageFont.load_default()
                draw.text((x + 5, y + 2), icon["char"], fill=(255, 255, 255), font=char_font)
                
        elif icon["shape"] == "triangle":
            points = [(x + size//2, y), (x, y + size), (x + size, y + size)]
            draw.polygon(points, fill=color)
            try:
                char_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            except:
                char_font = ImageFont.load_default()
            draw.text((x + 6, y + 6), "!", fill=(0, 0, 0), font=char_font)
            
        elif icon["shape"] == "heart":
            # Simple pixel heart
            for dy, row in enumerate([
                "  **  **  ",
                " ******** ",
                " ******** ",
                "  ******  ",
                "   ****   ",
                "    **    ",
            ]):
                for dx, c in enumerate(row):
                    if c == '*':
                        draw.point((x + dx, y + dy), fill=color)
                        
        elif icon["shape"] == "star":
            # Simple star
            points = []
            import math
            for i in range(5):
                angle = math.radians(i * 72 - 90)
                points.append((x + size//2 + int(size//2 * math.cos(angle)), 
                              y + size//2 + int(size//2 * math.sin(angle))))
                angle = math.radians(i * 72 - 90 + 36)
                points.append((x + size//2 + int(size//4 * math.cos(angle)), 
                              y + size//2 + int(size//4 * math.sin(angle))))
            draw.polygon(points, fill=color)
            
        elif icon["shape"] == "bell":
            draw.ellipse([x + 4, y, x + size - 4, y + 12], fill=color)
            draw.rectangle([x + 2, y + 8, x + size - 2, y + 16], fill=color)
            draw.ellipse([x + 7, y + 16, x + 13, y + 20], fill=color)
            
        elif icon["shape"] == "mail":
            draw.rectangle([x, y + 4, x + size, y + 16], fill=color)
            draw.polygon([(x, y + 4), (x + size//2, y + 12), (x + size, y + 4)], fill=(150, 200, 255))
        
        return size
        
    def show_weather(self, city: str = "London", duration: float = 0):
        """
        Display weather for a city with pixel-art icon.
        
        Args:
            city: City name
            duration: Seconds to display. 0 = forever until stopped
        """
        def worker():
            try:
                print(f"[DEBUG] Fetching weather for: {city}")
                weather_data = weather_service.get_weather(city)
                print(f"[DEBUG] Weather: {weather_data['temp']}{weather_data['temp_unit']}, {weather_data['condition']}")
                
                # Create the weather display image
                img = create_weather_display(weather_data)
                rotated = self._rotate_image(img)
                self.matrix.SetImage(rotated.convert('RGB'))
                
                start_time = time.time()
                while not self.stop_event.is_set():
                    if duration > 0 and (time.time() - start_time >= duration):
                        break
                    time.sleep(0.1)
            except Exception as e:
                print(f"[ERROR] Weather display failed: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.current_job = None
                
        # Stop any current job first
        self._stop_current_job()
        self.stop_event.clear()
        self.current_job = "weather"
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        
    def clear(self):
        self.stop_event.set()
        self.matrix.Clear()
        self.current_job = None
        
    def stop_current(self):
        self.stop_event.set()
        self.current_job = None

matrix_handler = MatrixHandler()

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/matrix/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status = {
                "current_job_type": matrix_handler.current_job,
                "status": "running" if matrix_handler.current_job else "idle"
            }
            self.wfile.write(json.dumps(status).encode())
        else:
            self.send_response(404)
            self.end_headers()
            
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
        except:
            data = {}
            
        if self.path == '/matrix/show/image':
            url = data.get('url')
            duration = data.get('duration', 0)  # 0 = forever
            loops = data.get('loops', 0)  # 0 = infinite loops
            
            if url:
                matrix_handler.show_image_from_url(url, duration, loops)
                msg = "Image display started"
                if duration > 0:
                    msg += f" (duration: {duration}s)"
                if loops > 0:
                    msg += f" (loops: {loops})"
                response = {"ok": True, "message": msg}
            else:
                response = {"ok": False, "error": "'url' required. For file upload, use /matrix/upload/image"}
                
        elif self.path == '/matrix/upload/image':
            # Handle multipart/form-data file upload
            try:
                content_type = self.headers.get('Content-Type', '')
                if 'multipart/form-data' not in content_type:
                    response = {"ok": False, "error": "Content-Type must be multipart/form-data"}
                else:
                    # Parse multipart form data
                    form = cgi.FieldStorage(
                        fp=io.BytesIO(post_data),
                        headers=self.headers,
                        environ={
                            'REQUEST_METHOD': 'POST',
                            'CONTENT_TYPE': content_type,
                            'CONTENT_LENGTH': content_length
                        }
                    )
                    
                    # Get the uploaded file
                    if 'file' in form and form['file'].file:
                        img_data = form['file'].file.read()
                        duration = float(form.getvalue('duration', 0))
                        loops = int(form.getvalue('loops', 0))
                        matrix_handler.show_image_from_data(img_data, duration, loops)
                        response = {"ok": True, "message": f"Uploaded image ({len(img_data)} bytes) display started"}
                    else:
                        response = {"ok": False, "error": "No 'file' field in form data"}
            except Exception as e:
                response = {"ok": False, "error": f"Upload failed: {e}"}
                
        elif self.path == '/matrix/show/text':
            text = data.get('text')
            duration = data.get('duration', 0)  # 0 = forever
            scroll = data.get('scroll', False)
            icon = data.get('icon')  # info, warning, error, check, heart, star, bell, mail
            bg_color = tuple(data.get('bg_color', [0, 0, 0]))
            text_color = tuple(data.get('text_color', [255, 255, 255]))
            
            if text:
                matrix_handler.show_text(text, duration, scroll=scroll, icon=icon, 
                                        bg_color=bg_color, text_color=text_color)
                response = {"ok": True, "message": "Text display started"}
            else:
                response = {"ok": False, "error": "Text required"}
                
        elif self.path == '/matrix/show/weather':
            city = data.get('city', 'London')
            duration = data.get('duration', 0)  # 0 = forever
            matrix_handler.show_weather(city, duration)
            response = {"ok": True, "message": f"Weather display started for {city}"}
            
        elif self.path == '/matrix/clear':
            matrix_handler.clear()
            response = {"ok": True, "message": "Matrix cleared"}
            
        elif self.path == '/matrix/stop':
            matrix_handler.stop_current()
            response = {"ok": True, "message": "Current job stopped"}
            
        else:
            self.send_response(404)
            self.end_headers()
            return
            
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 9191), RequestHandler)
    print("Simple server running on http://0.0.0.0:9191")
    server.serve_forever()
