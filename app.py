# app.py
import io
import time
import threading
import queue
import enum
from typing import Optional
from dataclasses import dataclass, field

import requests
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, HttpUrl
import uvicorn
from PIL import Image, ImageSequence, ImageOps

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

# ---------------- Models ----------------

class JobType(str, enum.Enum):
    IMAGE = "image"
    TEXT = "text"
    WEATHER = "weather"
    CLEAR = "clear"
    NOOP = "noop"

@dataclass
class Job:
    type: JobType
    # common
    duration: Optional[float] = None  # seconds; None = until replaced
    id: int = 0
    # image
    image: Optional[Image.Image] = None
    gif_frames: Optional[list[Image.Image]] = None
    frame_delays: Optional[list[float]] = None
    # text
    text: Optional[str] = None
    # weather
    template: Optional[str] = None

# -------------- Display Manager --------------

class DisplayManager:
    def __init__(self, width=64, height=64, chain_length=1, parallel=1, pwm_bits=11, brightness=70):
        self._job_q: "queue.Queue[Job]" = queue.Queue()
        self._current_job: Optional[Job] = None
        self._cancel_evt = threading.Event()
        self._lock = threading.Lock()
        self._next_id = 1
        self._running = True

        if RGBMatrix is None:
            # Dev mode: simple stand-in
            self.matrix = None
            print("[DisplayManager] RGBMatrix not available (probably not on Pi). Running in dry mode.")
        else:
            opts = RGBMatrixOptions()
            opts.rows = height
            opts.cols = width
            opts.chain_length = chain_length
            opts.parallel = parallel
            opts.pwm_bits = pwm_bits
            opts.brightness = brightness
            opts.hardware_mapping = "regular"  # change if needed
            self.matrix = RGBMatrix(options=opts)

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _next_job_id(self) -> int:
        with self._lock:
            jid = self._next_id
            self._next_id += 1
            return jid

    def enqueue(self, job: Job) -> int:
        job.id = self._next_job_id()
        self._job_q.put(job)
        return job.id

    def clear(self):
        self.enqueue(Job(type=JobType.CLEAR, duration=None))

    def stop_current(self):
        self._cancel_evt.set()

    def status(self) -> dict:
        with self._lock:
            cid = self._current_job.id if self._current_job else None
            ctype = self._current_job.type if self._current_job else None
        return {"current_job_id": cid, "current_job_type": ctype, "queue_size": self._job_q.qsize()}

    # ---- Drawing helpers ----

    def _display_image(self, img: Image.Image, duration: Optional[float]) -> None:
        start = time.time()
        # Fit to matrix
        if self.matrix:
            w, h = self.matrix.width, self.matrix.height
        else:
            # default dev size
            w, h = 64, 64
        frame = ImageOps.fit(img.convert("RGB"), (w, h), method=Image.Resampling.LANCZOS)
        if self.matrix:
            self.matrix.SetImage(frame)
        else:
            print("[Display] Showing still image", frame.size)
        # hold until duration or canceled or replaced
        while not self._cancel_evt.is_set() and (duration is None or time.time() - start < duration):
            time.sleep(0.05)

    def _display_gif(self, frames: list[Image.Image], delays: list[float], duration: Optional[float]) -> None:
        start = time.time()
        if self.matrix:
            w, h = self.matrix.width, self.matrix.height
        else:
            w, h = 64, 64

        i = 0
        while not self._cancel_evt.is_set() and (duration is None or time.time() - start < duration):
            f = ImageOps.fit(frames[i].convert("RGB"), (w, h), method=Image.Resampling.NEAREST)
            if self.matrix:
                self.matrix.SetImage(f)
            else:
                if i == 0:
                    print("[Display] Playing GIF", f.size, f"{len(frames)} frames")
            delay = max(0.01, delays[i])
            time.sleep(delay)
            i = (i + 1) % len(frames)

    def _display_text_scroll(self, text: str, duration: Optional[float]) -> None:
        # Simple example using Pillow to render text into an image and scroll it
        from PIL import ImageDraw, ImageFont
        if self.matrix:
            w, h = self.matrix.width, self.matrix.height
        else:
            w, h = 64, 64
        font = ImageFont.load_default()
        img = Image.new("RGB", (1000, h), "black")
        draw = ImageDraw.Draw(img)
        draw.text((0, (h - font.getbbox(text)[3]) // 2), text, fill=(255, 255, 255), font=font)
        text_w = draw.textlength(text, font=font)
        viewport = Image.new("RGB", (w, h), "black")

        start = time.time()
        x = 0
        while not self._cancel_evt.is_set() and (duration is None or time.time() - start < duration):
            # loop scroll
            x = (x + 1) % (int(text_w) + w)
            box = (x, 0, x + w, h)
            # If we scroll off the right edge, wrap by compositing two slices
            if box[2] <= img.width:
                frame = img.crop(box)
            else:
                right = img.crop((x, 0, img.width, h))
                left = img.crop((0, 0, w - right.width, h))
                frame = Image.new("RGB", (w, h))
                frame.paste(right, (0, 0))
                frame.paste(left, (right.width, 0))
            if self.matrix:
                self.matrix.SetImage(frame)
            time.sleep(0.02)

    def _display_weather_template(self, template: str, duration: Optional[float]) -> None:
        # Stub: you’d render from cached weather data or a local sensor.
        # For now, just render a placeholder block.
        img = Image.new("RGB", (64, 32), "navy")
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        d.text((1, 1), f"Weather:\n{template}", fill=(255, 255, 0))
        self._display_image(img, duration)

    # ---- Worker loop ----

    def _worker(self):
        while self._running:
            job = self._job_q.get()
            self._cancel_evt.clear()
            with self._lock:
                self._current_job = job
            try:
                if job.type == JobType.CLEAR:
                    if self.matrix:
                        self.matrix.Clear()
                    else:
                        print("[Display] Clear")
                    # brief pause so Clear is visible
                    time.sleep(0.05)

                elif job.type == JobType.IMAGE:
                    if job.gif_frames:
                        self._display_gif(job.gif_frames, job.frame_delays or [0.07]*len(job.gif_frames), job.duration)
                    elif job.image:
                        self._display_image(job.image, job.duration)
                    else:
                        print("[Display] IMAGE job missing content")

                elif job.type == JobType.TEXT:
                    self._display_text_scroll(job.text or "", job.duration)

                elif job.type == JobType.WEATHER:
                    self._display_weather_template(job.template or "default", job.duration)

                else:
                    time.sleep(0.01)

            finally:
                with self._lock:
                    self._current_job = None
                self._job_q.task_done()

# -------------- FastAPI setup --------------

app = FastAPI(title="RGB Matrix Server", version="0.1.0")
manager = DisplayManager()

class ShowImageRequest(BaseModel):
    url: HttpUrl
    duration: Optional[float] = 10.0  # seconds; None to loop until replaced

class ShowTextRequest(BaseModel):
    text: str
    duration: Optional[float] = 10.0

class ShowWeatherRequest(BaseModel):
    template: str = "current"
    duration: Optional[float] = 10.0

@app.get("/matrix/status")
def get_status():
    return manager.status()

@app.post("/matrix/clear")
def clear_matrix():
    manager.clear()
    return {"ok": True}

@app.post("/matrix/stop")
def stop_current():
    manager.stop_current()
    return {"ok": True}

@app.post("/matrix/show/image")
def show_image(req: ShowImageRequest):
    try:
        resp = requests.get(str(req.url), timeout=10)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"HTTP {resp.status_code} fetching image")

    try:
        img = Image.open(io.BytesIO(resp.content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Not a valid image: {e}")

    # If animated, extract frames and delays
    gif_frames = None
    delays = None
    if getattr(img, "is_animated", False):
        gif_frames = []
        delays = []
        for frame in ImageSequence.Iterator(img):
            gif_frames.append(frame.convert("RGB").copy())
            # delay in ms; default to 70ms if missing
            delays.append(max(0.01, (frame.info.get("duration", 70) / 1000.0)))

    job = Job(
        type=JobType.IMAGE,
        duration=req.duration,
        image=None if gif_frames else img.convert("RGB"),
        gif_frames=gif_frames,
        frame_delays=delays,
    )
    jid = manager.enqueue(job)
    return {"ok": True, "job_id": jid, "animated": bool(gif_frames)}

@app.post("/matrix/show/text")
def show_text(req: ShowTextRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    jid = manager.enqueue(Job(type=JobType.TEXT, text=req.text, duration=req.duration))
    return {"ok": True, "job_id": jid}

@app.post("/matrix/show/weather")
def show_weather(req: ShowWeatherRequest):
    # In a real app, you'd render from cached weather data collected by a separate updater.
    jid = manager.enqueue(Job(type=JobType.WEATHER, template=req.template, duration=req.duration))
    return {"ok": True, "job_id": jid}

if __name__ == "__main__":
    # IMPORTANT: keep a single worker process so only one thing owns the matrix.
    # Use --workers 1 (default) and consider --loop uvloop on the Pi for perf.
    uvicorn.run("app:app", host="0.0.0.0", port=9191, reload=False)