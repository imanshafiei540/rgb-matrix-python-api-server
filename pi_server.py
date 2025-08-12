#!/usr/bin/env python3
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import io
from PIL import Image, ImageOps, ImageSequence, ImageDraw, ImageFont

try:
    # Try Raspberry Pi native library
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    print("[INFO] Using real RGBMatrix library")
except ImportError:
    try:
        # Fallback to emulator for development
        from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
        print("[INFO] Using RGBMatrixEmulator (development mode)")
    except ImportError:
        raise ImportError(
            "Neither rgbmatrix (Raspberry Pi) nor RGBMatrixEmulator found. "
            "Install one of them to proceed."
        )

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
        self.matrix = RGBMatrix(options=opts)
        self.stop_event = threading.Event()
        self.current_job = None
        
    def show_image_from_url(self, url, duration=10.0):
        def worker():
            try:
                with urllib.request.urlopen(url) as response:
                    img_data = response.read()
                img = Image.open(io.BytesIO(img_data))
                
                # Handle animated GIFs
                if getattr(img, "is_animated", False):
                    frames = []
                    delays = []
                    for frame in ImageSequence.Iterator(img):
                        frames.append(frame.convert("RGB").copy())
                        delays.append(max(0.01, frame.info.get("duration", 70) / 1000.0))
                    
                    start_time = time.time()
                    frame_idx = 0
                    while not self.stop_event.is_set() and (time.time() - start_time < duration):
                        resized = ImageOps.fit(frames[frame_idx], (64, 64), method=Image.Resampling.LANCZOS)
                        self.matrix.SetImage(resized)
                        time.sleep(delays[frame_idx])
                        frame_idx = (frame_idx + 1) % len(frames)
                else:
                    # Static image
                    resized = ImageOps.fit(img.convert("RGB"), (64, 64), method=Image.Resampling.LANCZOS)
                    self.matrix.SetImage(resized)
                    start_time = time.time()
                    while not self.stop_event.is_set() and (time.time() - start_time < duration):
                        time.sleep(0.1)
                        
            except Exception as e:
                print(f"Error: {e}")
            finally:
                self.current_job = None
                
        self.stop_event.clear()
        self.current_job = "image"
        threading.Thread(target=worker).start()
        
    def show_text(self, text, duration=10.0):
        def worker():
            try:
                font = ImageFont.load_default()
                img = Image.new("RGB", (1000, 64), "black")
                draw = ImageDraw.Draw(img)
                draw.text((0, 20), text, fill=(255, 255, 255), font=font)
                text_w = draw.textlength(text, font=font)
                
                start_time = time.time()
                x = 0
                while not self.stop_event.is_set() and (time.time() - start_time < duration):
                    x = (x + 1) % (int(text_w) + 64)
                    if x + 64 <= img.width:
                        frame = img.crop((x, 0, x + 64, 64))
                    else:
                        frame = Image.new("RGB", (64, 64))
                        right_part = img.crop((x, 0, img.width, 64))
                        left_part = img.crop((0, 0, 64 - right_part.width, 64))
                        frame.paste(right_part, (0, 0))
                        frame.paste(left_part, (right_part.width, 0))
                    
                    self.matrix.SetImage(frame)
                    time.sleep(0.02)
            except Exception as e:
                print(f"Error: {e}")
            finally:
                self.current_job = None
                
        self.stop_event.clear()
        self.current_job = "text"
        threading.Thread(target=worker).start()
        
    def show_weather(self, template="current", duration=10.0):
        def worker():
            try:
                img = Image.new("RGB", (64, 64), "navy")
                draw = ImageDraw.Draw(img)
                draw.text((1, 1), f"Weather:\n{template}", fill=(255, 255, 0))
                self.matrix.SetImage(img)
                start_time = time.time()
                while not self.stop_event.is_set() and (time.time() - start_time < duration):
                    time.sleep(0.1)
            except Exception as e:
                print(f"Error: {e}")
            finally:
                self.current_job = None
                
        self.stop_event.clear()
        self.current_job = "weather"
        threading.Thread(target=worker).start()
        
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
            duration = data.get('duration', 10.0)
            if url:
                matrix_handler.show_image_from_url(url, duration)
                response = {"ok": True, "message": "Image display started"}
            else:
                response = {"ok": False, "error": "URL required"}
                
        elif self.path == '/matrix/show/text':
            text = data.get('text')
            duration = data.get('duration', 10.0)
            if text:
                matrix_handler.show_text(text, duration)
                response = {"ok": True, "message": "Text display started"}
            else:
                response = {"ok": False, "error": "Text required"}
                
        elif self.path == '/matrix/show/weather':
            template = data.get('template', 'current')
            duration = data.get('duration', 10.0)
            matrix_handler.show_weather(template, duration)
            response = {"ok": True, "message": "Weather display started"}
            
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
