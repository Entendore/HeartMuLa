# ==============================================================================
# IMPORTS
# ==============================================================================
import sys
import os
import json
import tempfile
import shutil
import time
import random
import re
import subprocess
import traceback
import logging
import logging.handlers
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QFileDialog,
    QProgressBar, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QMessageBox, QStatusBar, QCheckBox,
    QTabWidget, QSlider, QListWidget, QListWidgetItem, QStyle, QMenu, QMenuBar,
    QSizePolicy, QSplitter, QFrame, QTreeWidget, QTreeWidgetItem, QInputDialog,
    QScrollArea, QToolButton, QGridLayout, QSpacerItem, QTimeEdit
)
from PySide6.QtCore import (
    Qt, QUrl, QTime, QTimer, QSettings, QRegularExpression, QThread, QObject, Signal,
    QProcess, QSize, QPoint, QByteArray, QMimeData
)
from PySide6.QtGui import (
    QFont, QIcon, QTextCursor, QColor, QAction, QKeySequence, QShortcut,
    QDragEnterEvent, QDropEvent, QSyntaxHighlighter, QTextCharFormat, QFontMetrics,
    QPixmap, QPainter, QLinearGradient
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

# Optional AI Imports
try:
    import torch
    from heartlib import HeartMuLaGenPipeline, HeartTranscriptorPipeline
    HAS_AI_LIBS = True
    
    # Dtype mapping for UI dropdowns
    DTYPE_MAP = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32
    }
except ImportError:
    HAS_AI_LIBS = False
    DTYPE_MAP = {}

try:
    from PySide6.QtWidgets import QSystemTrayIcon
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


# ==============================================================================
# CONSTANTS & CONFIGURATIONS
# ==============================================================================
APP_NAME = "HeartMuLa Studio Pro"
APP_ORG = "HeartMuLa"
APP_VERSION = "2.1.3"

DEFAULT_MODEL_PATH = "E:/cacheAI"
DEFAULT_OUTPUT_PATH = "./output.mp3"
DEFAULT_MAX_LENGTH_MS = 240000

CONFIG_FILE = "config.json"
DRAFT_FILE = "draft.json"
TAGS_DB_FILE = "tags_db.json"
QUEUE_FILE = "queue.json"
LOG_FILE_NAME = "studio.log"
PROJECT_FILE_EXT = ".hmp"

AUTOSAVE_INTERVAL_MS = 30000
VRAM_CHECK_INTERVAL_MS = 3000
GEN_TIMER_INTERVAL_MS = 1000

# UI & Console Constants
COLOR_ERROR = "#f44336"
COLOR_WARNING = "#ff9800"
COLOR_SUCCESS = "#4CAF50"
COLOR_INFO = "#d4d4d4"
COLOR_ACCENT = "#2196F3"
COLOR_BG = "#1e1e2e"
COLOR_PANEL = "#252535"
COLOR_BORDER = "#3d3d5c"

VRAM_WARN_THRESHOLD = 90
VRAM_CLEAR_THRESHOLD = 80

# Pre-compiled Regex for Console Formatting
_ERROR_RE = re.compile(r"(?i)(error|traceback|exception|failed)")
_WARN_RE = re.compile(r"(?i)(warning|warn)")
_SUCCESS_RE = re.compile(r"(?i)(success|complete|done|loaded)")
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

DEFAULT_TAG_DB: Dict[str, List[str]] = {
    "Genres": ["pop", "rock", "lofi", "cinematic", "edm", "jazz", "classical",
               "blues", "metal", "country", "rnb", "folk", "reggae", "punk",
               "ambient", "trap", "house", "techno", "dnb", "soul", "funk"],
    "Instruments": ["piano", "guitar", "synth", "drums", "strings", "cello",
                    "violin", "808", "flute", "trumpet", "saxophone", "bass",
                    "accordion", "harp", "organ", "marimba", "xylophone",
                    "kick", "snare", "hihat", "tom", "cymbal", "clap"],
    "Moods": ["happy", "sad", "epic", "chill", "aggressive", "romantic",
              "melancholic", "uplifting", "dark", "ethereal", "energetic",
              "dreamy", "tense", "peaceful", "nostalgic", "mysterious",
              "hopeful", "angry", "calm", "euphoric"],
    "Vocals": ["male_vocal", "female_vocal", "choir", "no_vocal", "high_pitch",
               "deep_voice", "whisper", "spoken_word", "vocoder", "autotune",
               "harmonies", "ad_libs", "falsetto", "growl", "clean_vocal"],
    "Era": ["80s", "90s", "retro", "modern", "vintage", "futuristic",
            "70s", "2000s", "2010s", "medieval", "ancient"],
    "Production": ["vinyl_crackle", "reverb", "distortion", "clean", "lofi_aesthetic",
                   "wide_stereo", "compressed", "sidechain", "tape_saturation",
                   "high_quality", "demo", "remastered", "acoustic", "electric"],
    "Tempo": ["slow", "mid_tempo", "fast", "uptempo", "downtempo", "ballad",
              "allegro", "presto", "largo", "moderato"],
    "Structure": ["intro", "verse", "chorus", "bridge", "outro", "drop",
                  "buildup", "breakdown", "solo", "interlude"]
}

SONG_TEMPLATES: Dict[str, Dict[str, str]] = {
    "Lo-Fi Chill": {
        "tags": "lofi, chill, mellow, vinyl_crackle, piano, soft_drums, nostalgic, rainy, study_music",
        "lyrics": "[Intro]\n(mellow piano melody)\n\n[Verse 1]\nWrite your verses here...\n\n[Chorus]\nWrite your chorus here...\n\n[Outro]\n(fade out)"
    },
    "Epic Rock Anthem": {
        "tags": "rock, epic, electric_guitar, powerful_drums, anthemic, energetic, distorted, male_vocal",
        "lyrics": "[Intro]\n(powerful guitar riff)\n\n[Verse 1]\nWrite your verses here...\n\n[Prechorus]\nBuilding up...\n\n[Chorus]\nEpic chorus here...\n\n[Guitar Solo]\n(solo)\n\n[Outro]\n(big finish)"
    },
    "Acoustic Pop": {
        "tags": "pop, acoustic_guitar, warm, melodic, male_vocal, clean, heartfelt, soft",
        "lyrics": "[Intro]\n(acoustic guitar strumming)\n\n[Verse 1]\nWrite your verses here...\n\n[Chorus]\nWrite your chorus here...\n\n[Verse 2]\nMore verses...\n\n[Chorus]\nRepeat chorus...\n\n[Outro]\n(soft ending)"
    },
    "EDM Drop": {
        "tags": "edm, electronic, synth, 808, energetic, festival, drop, buildup, dance, uptempo",
        "lyrics": "[Intro]\n(atmospheric pad)\n\n[Buildup]\nRising energy...\n\n[Drop]\n(heavy bass drop)\n\n[Verse]\nVocals here...\n\n[Drop]\n(another drop)\n\n[Outro]\n(fade out)"
    },
    "Cinematic Orchestral": {
        "tags": "cinematic, orchestral, strings, epic, dramatic, choir, emotional, film_score, powerful",
        "lyrics": "[Intro]\n(soft strings)\n\n[Buildup]\n(adding percussion)\n\n[Climax]\n(full orchestra)\n\n[Resolution]\n(fading strings)"
    },
    "Jazz Lounge": {
        "tags": "jazz, smooth, saxophone, piano, brush_drums, upright_bass, lounge, sophisticated, swing",
        "lyrics": "[Intro]\n(piano and bass)\n\n[Verse 1]\nSmooth vocals here...\n\n[Sax Solo]\n(improvisation)\n\n[Outro]\n(cool ending)"
    }
}

# Audio patch to handle MP3 saving safely (executed locally)
AUDIO_PATCH_CODE = '''
import torchaudio, torch, numpy as np, os, shutil
import soundfile as sf
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

_original_save = torchaudio.save

def patched_save(filepath, src, sample_rate, channels_first=True, *args, **kwargs):
    if not isinstance(src, torch.Tensor):
        raise TypeError("src must be a Tensor")
    src_np = src.to(torch.float32).cpu().numpy()
    if src_np.ndim == 2 and channels_first:
        src_np = src_np.T
    src_np = np.clip(src_np, -1.0, 1.0).astype(np.float32)

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mp3":
        if not HAS_PYDUB:
            print("WARNING: pydub is not installed. Saving as WAV instead.")
            filepath = os.path.splitext(filepath)[0] + ".wav"
            sf.write(filepath, src_np, sample_rate)
            return

        temp_wav = filepath + ".tmp.wav"
        sf.write(temp_wav, src_np, sample_rate)
        try:
            audio = AudioSegment.from_wav(temp_wav)
            audio.export(filepath, format="mp3")
            os.remove(temp_wav)
        except Exception as e:
            print(f"WARNING: MP3 export failed ({e}). Saving as WAV instead.")
            filepath = os.path.splitext(filepath)[0] + ".wav"
            shutil.move(temp_wav, filepath)
            return
    else:
        sf.write(filepath, src_np, sample_rate)

torchaudio.save = patched_save
'''


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class GenerationParams:
    variations: int = 1
    max_len: int = DEFAULT_MAX_LENGTH_MS
    topk: int = 50
    temp: float = 1.0
    cfg: float = 1.5
    format: str = "mp3"

@dataclass
class ModelConfig:
    path: str = DEFAULT_MODEL_PATH
    version: str = "3B"
    mula_device: str = "cuda:0"
    codec_device: str = "cuda:0"
    mula_dtype: str = "bfloat16"
    codec_dtype: str = "float32"
    lazy_load: bool = True

@dataclass
class QueueItem:
    lyrics: str
    tags: str
    temp: float
    topk: int
    cfg: float
    max_len: int
    format: str = "mp3"
    output_path: str = ""
    variations: int = 1
    label: str = ""
    mula_device: str = "cuda:0"
    codec_device: str = "cuda:0"
    mula_dtype: str = "bfloat16"
    codec_dtype: str = "float32"


# ==============================================================================
# STDOUT REDIRECTOR FOR WORKERS
# ==============================================================================
class QtStreamRedirector(QObject):
    """Redirects stdout/stderr to a Qt signal for console logging."""
    message = Signal(str)
    
    def __init__(self, original_stdout):
        super().__init__()
        self.original_stdout = original_stdout

    def write(self, text):
        if text and text.strip():
            self.message.emit(text)
        if self.original_stdout:
            try:
                self.original_stdout.write(text)
            except: pass

    def flush(self):
        if self.original_stdout:
            try:
                self.original_stdout.flush()
            except: pass

    def isatty(self):
        return False


# ==============================================================================
# THREAD WORKERS
# ==============================================================================
class GenerationWorker(QObject):
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)
    
    def __init__(self, model_path, version, lyrics_path, tags_path, save_path, 
                 max_len, topk, temp, cfg, mula_device, codec_device, mula_dtype, codec_dtype, lazy_load):
        super().__init__()
        self.model_path = model_path
        self.version = version
        self.lyrics_path = lyrics_path
        self.tags_path = tags_path
        self.save_path = save_path
        self.max_len = max_len
        self.topk = topk
        self.temp = temp
        self.cfg = cfg
        self.mula_device = mula_device
        self.codec_device = codec_device
        self.mula_dtype = mula_dtype
        self.codec_dtype = codec_dtype
        self.lazy_load = lazy_load

    def run(self):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirector = QtStreamRedirector(old_stdout)
        redirector.message.connect(self.progress)
        sys.stdout = redirector
        sys.stderr = redirector
        
        try:
            # Apply audio patch to handle MP3 saving safely
            exec(AUDIO_PATCH_CODE, globals())
            
            print("Loading HeartMuLa Pipeline...")
            pipe = HeartMuLaGenPipeline.from_pretrained(
                self.model_path,
                device={
                    "mula": torch.device(self.mula_device),
                    "codec": torch.device(self.codec_device),
                },
                dtype={
                    "mula": DTYPE_MAP.get(self.mula_dtype, torch.bfloat16),
                    "codec": DTYPE_MAP.get(self.codec_dtype, torch.float32),
                },
                version=self.version,
                lazy_load=self.lazy_load,
            )
            print("Pipeline loaded. Generating...")
            with torch.no_grad():
                pipe(
                    {
                        "lyrics": self.lyrics_path,
                        "tags": self.tags_path,
                    },
                    max_audio_length_ms=self.max_len,
                    save_path=self.save_path,
                    topk=self.topk,
                    temperature=self.temp,
                    cfg_scale=self.cfg,
                )
            print(f"Generated music saved to {self.save_path}")
            self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            try:
                torch.cuda.empty_cache()
            except:
                pass

class TranscriptionWorker(QObject):
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)
    
    def __init__(self, model_path, music_path):
        super().__init__()
        self.model_path = model_path
        self.music_path = music_path

    def run(self):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirector = QtStreamRedirector(old_stdout)
        redirector.message.connect(self.progress)
        sys.stdout = redirector
        sys.stderr = redirector
        
        try:
            print("Loading HeartTranscriptor Pipeline...")
            pipe = HeartTranscriptorPipeline.from_pretrained(
                self.model_path,
                device=torch.device("cuda"),
                dtype=torch.float16,
            )
            print("Pipeline loaded. Transcribing...")
            with torch.no_grad():
                result = pipe(
                    self.music_path,
                    max_new_tokens=256,
                    num_beams=2,
                    task="transcribe",
                    condition_on_prev_tokens=False,
                    compression_ratio_threshold=1.8,
                    temperature=(0.0, 0.1, 0.2, 0.4),
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.4,
                )
            print("\n--- Transcription Result ---")
            print(result)
            self.finished.emit(str(result))
        except Exception as e:
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            try:
                torch.cuda.empty_cache()
            except:
                pass


class SongStructureHighlighter(QSyntaxHighlighter):
    """Highlights [Section] and (stage) markers in the lyrics editor."""
    def __init__(self, document):
        super().__init__(document)
        self.mapping: Dict[QRegularExpression, QTextCharFormat] = {}

        fmt_section = QTextCharFormat()
        fmt_section.setForeground(QColor("#569cd6"))
        fmt_section.setFontWeight(QFont.Bold)
        self.mapping[QRegularExpression(r"\[.*?\]")] = fmt_section

        fmt_stage = QTextCharFormat()
        fmt_stage.setForeground(QColor("#6a9955"))
        fmt_stage.setFontItalic(True)
        self.mapping[QRegularExpression(r"\(.*?\)")] = fmt_stage

        fmt_tag = QTextCharFormat()
        fmt_tag.setForeground(QColor("#ce9178"))
        self.mapping[QRegularExpression(r"#\w+")] = fmt_tag

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.mapping.items():
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


# ==============================================================================
# MAIN APPLICATION WINDOW
# ==============================================================================
class HeartMuLaStudio(QMainWindow):
    """Main window for the HeartMuLa Studio Pro application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setGeometry(100, 100, 1500, 1000)
        self.setMinimumSize(1000, 700)

        self.config_file = CONFIG_FILE
        self.history_dir = Path("./history")
        self.history_dir.mkdir(exist_ok=True)

        self.temp_dir = Path("./temp")
        self.temp_dir.mkdir(exist_ok=True)

        self._setup_logger()

        # State
        self.current_variation: int = 0
        self.total_variations: int = 1
        self.queue_running: bool = False
        self.queue_items: List[QueueItem] = []
        self.current_output_path: str = ""
        self.lyrics_file: Optional[str] = None
        self.tags_file: Optional[str] = None
        self.recent_projects: List[str] = []
        self.favorite_tags: List[str] = []
        self.current_gen_log: str = ""
        self.last_generation_params: Optional[Dict[str, Any]] = None
        self.current_project_path: Optional[str] = None
        self.is_modified: bool = False
        
        self._full_console_log: str = ""
        self._vram_warned: bool = False
        self._seeking: bool = False

        self.settings = QSettings(APP_ORG, "StudioPro")

        # Thread references
        self.gen_thread = None
        self.gen_worker = None
        self.trans_thread = None
        self.trans_worker = None

        # VRAM Monitor Process
        self.vram_process = QProcess(self)
        self.vram_process.finished.connect(self.parse_vram)
        self.vram_process.errorOccurred.connect(self.on_vram_error)
        self.vram_timer = QTimer(self)
        self.vram_timer.timeout.connect(self.check_vram)
        self.vram_timer.start(VRAM_CHECK_INTERVAL_MS)
        self.vram_available: bool = True

        # Audio Player
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)
        self.media_player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.media_player.errorOccurred.connect(self.on_media_error)

        self.init_ui()
        self.apply_dark_theme()
        self.load_tag_db()
        self.load_app_state()
        self.load_draft()
        self.load_queue()
        self.setup_tray_icon()
        self.setup_shortcuts()
        self.refresh_history()
        self.refresh_favorites()
        self.restore_window_state()
        self.setAcceptDrops(True)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.save_draft)
        self.autosave_timer.start(AUTOSAVE_INTERVAL_MS)

        self._history_filter_timer = QTimer(self)
        self._history_filter_timer.setSingleShot(True)
        self._history_filter_timer.setInterval(200)
        self._history_filter_timer.timeout.connect(self._do_filter_history)

        if not HAS_AI_LIBS:
            QTimer.singleShot(500, self._show_ai_warning)

    def _show_ai_warning(self):
        QMessageBox.warning(self, "Missing AI Libraries", 
            "Could not import 'torch' or 'heartlib'.\n"
            "Generation features are disabled until these are installed "
            "in your Python environment.")
        self.generate_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.regen_btn.setEnabled(False)

    def _setup_logger(self) -> None:
        self.logger = logging.getLogger(APP_NAME)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        log_path = Path.cwd() / LOG_FILE_NAME
        try:
            # Using mode='w' to overwrite the log file on every application start
            file_handler = logging.handlers.RotatingFileHandler(
                log_path, mode='w', maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to initialize log file: {e}")

    # --- UI CONSTRUCTION ---
    # -------------------------------------------------------------------------
    def init_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)

        left_panel_widget = self.create_config_panel()
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_panel_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setMinimumWidth(320)
        left_scroll.setMaximumWidth(450)

        right_panel = self.create_right_tabs()
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)
        
        # Initialize menubar and status bar AFTER UI components are created
        self.init_menubar()
        self.init_status_bar()

    def init_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet(f"QStatusBar {{ background-color: {COLOR_PANEL}; border-top: 1px solid {COLOR_BORDER}; }}")

        self.mini_play_btn = QPushButton()
        self.mini_play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.mini_play_btn.setFixedSize(24, 24)
        self.mini_play_btn.setToolTip("Play/Pause (Space)")
        self.mini_play_btn.clicked.connect(self.toggle_play)
        self.mini_play_btn.setEnabled(False)

        self.mini_track_label = QLabel("No track loaded")
        self.mini_track_label.setStyleSheet("color: #aaa; padding: 0 5px;")
        self.mini_track_label.setMaximumWidth(180)

        self.mini_time_label = QLabel("00:00 / 00:00")
        self.mini_time_label.setStyleSheet("color: #aaa; padding: 0 5px;")

        self.status_bar.addWidget(self.mini_play_btn)
        self.status_bar.addWidget(self.mini_track_label)
        self.status_bar.addWidget(self.mini_time_label)

        self.vram_label = QLabel("VRAM: N/A")
        self.vram_label.setStyleSheet("font-weight: bold; padding: 0 10px;")
        self.vram_label.setToolTip("GPU memory usage")

        self.gen_timer_label = QLabel("Elapsed: 00:00")
        self.gen_timer_label.setStyleSheet("font-weight: bold; padding: 0 10px;")

        self.queue_label = QLabel("Queue: 0 items")
        self.queue_label.setStyleSheet("padding: 0 10px;")

        self.autosave_label = QLabel("")
        self.autosave_label.setStyleSheet("color: #888; padding: 0 10px;")

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("padding: 0 10px;")

        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.autosave_label)
        self.status_bar.addPermanentWidget(self.queue_label)
        self.status_bar.addPermanentWidget(self.gen_timer_label)
        self.status_bar.addPermanentWidget(self.vram_label)

        self.gen_timer = QTimer(self)
        self.gen_timer.timeout.connect(self.update_gen_timer)
        self.gen_start_time: float = 0.0

    def init_menubar(self) -> None:
        menubar = self.menuBar()
        menubar.setStyleSheet(f"QMenuBar {{ background-color: {COLOR_PANEL}; }}")

        # File Menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction(self.style().standardIcon(QStyle.SP_FileIcon), "&New Project", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)

        open_action = QAction(self.style().standardIcon(QStyle.SP_DirOpenIcon), "&Open Project...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)

        save_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "&Save Project", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Project &As...", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(lambda: self.save_project(save_as=True))
        file_menu.addAction(save_as_action)

        self.recent_menu = file_menu.addMenu("Open &Recent")
        file_menu.addSeparator()

        regen_action = QAction("🔄 &Regenerate Last", self)
        regen_action.setShortcut(QKeySequence("Ctrl+R"))
        regen_action.triggered.connect(self.regenerate_last)
        file_menu.addAction(regen_action)

        file_menu.addSeparator()

        exit_action = QAction(self.style().standardIcon(QStyle.SP_DialogCloseButton), "E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        clear_lyrics_action = QAction("Clear &Lyrics", self)
        clear_lyrics_action.triggered.connect(lambda: self.lyrics_edit.clear())
        edit_menu.addAction(clear_lyrics_action)
        
        clear_tags_action = QAction("Clear &Tags", self)
        clear_tags_action.triggered.connect(lambda: self.tags_edit.clear())
        edit_menu.addAction(clear_tags_action)
        
        edit_menu.addSeparator()
        
        clear_console_action = QAction("Clear &Console", self)
        clear_console_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_console_action.triggered.connect(self.console_output.clear)
        edit_menu.addAction(clear_console_action)

        # Settings Menu
        settings_menu = menubar.addMenu("&Settings")
        hist_action = QAction("Set History &Folder...", self)
        hist_action.triggered.connect(self.set_history_folder)
        settings_menu.addAction(hist_action)

        clear_temp_action = QAction("Clear &Temp Files", self)
        clear_temp_action.triggered.connect(self.cleanup_temp_files)
        settings_menu.addAction(clear_temp_action)
        
        settings_menu.addSeparator()
        
        self.always_tray_check = QAction("Minimize to &Tray", self)
        self.always_tray_check.setCheckable(True)
        self.always_tray_check.setChecked(True)
        settings_menu.addAction(self.always_tray_check)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.setShortcut(QKeySequence("F1"))
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        help_menu.addSeparator()
        about_action = QAction(f"&About {APP_NAME}", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        self.update_recent_menu()

    def show_shortcuts(self) -> None:
        shortcuts_text = (
            "<h3>Keyboard Shortcuts</h3><table cellpadding='4'>"
            "<tr><td><b>Ctrl+Enter</b></td><td>Start generation</td></tr>"
            "<tr><td><b>Ctrl+R</b></td><td>Regenerate last track</td></tr>"
            "<tr><td><b>Ctrl+Q</b></td><td>Add to queue</td></tr>"
            "<tr><td><b>Ctrl+N</b></td><td>New project</td></tr>"
            "<tr><td><b>Ctrl+O</b></td><td>Open project</td></tr>"
            "<tr><td><b>Ctrl+S</b></td><td>Save project</td></tr>"
            "<tr><td><b>Ctrl+L</b></td><td>Clear console</td></tr>"
            "<tr><td><b>Ctrl+1..6</b></td><td>Switch tabs</td></tr>"
            "<tr><td><b>Space</b></td><td>Play/Pause</td></tr>"
            "<tr><td><b>F1</b></td><td>Show this help</td></tr>"
            "</table>"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    def show_about(self) -> None:
        QMessageBox.about(self, f"About {APP_NAME}", 
            f"<h3>{APP_NAME}</h3>"
            f"<p>Version {APP_VERSION}</p>"
            f"<p>AI Music Generation Studio</p>"
            f"<p>AI Libraries: {'Available' if HAS_AI_LIBS else 'Not Found'}</p>")

    def set_history_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select History Directory")
        if d:
            self.history_dir = Path(d)
            self.history_dir.mkdir(exist_ok=True)
            self.settings.setValue("history_dir", str(self.history_dir))
            self.refresh_history()
            self.log_console(f"History directory changed to: {d}\n", "success")

    def create_config_panel(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet(f"QWidget {{ background-color: {COLOR_PANEL}; }}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Model Configuration
        model_group = QGroupBox("Model Configuration")
        model_layout = QFormLayout()

        self.model_path_edit = QLineEdit(DEFAULT_MODEL_PATH)
        btn_browse_model = QPushButton("...")
        btn_browse_model.setFixedWidth(40)
        btn_browse_model.clicked.connect(lambda: self.browse_dir(self.model_path_edit))
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.model_path_edit)
        path_layout.addWidget(btn_browse_model)
        model_layout.addRow("Model Path:", path_layout)

        self.version_combo = QComboBox()
        self.version_combo.addItems(["3B", "7B"])
        model_layout.addRow("Version:", self.version_combo)

        dev_dtype_layout = QHBoxLayout()
        dev_dtype_layout.addWidget(QLabel("MuLa:"))
        self.mula_device_combo = QComboBox()
        self.mula_device_combo.addItems(["cuda:0", "cuda:1", "cpu"])
        dev_dtype_layout.addWidget(self.mula_device_combo)
        self.mula_dtype_combo = QComboBox()
        self.mula_dtype_combo.addItems(["bfloat16", "float16", "float32"])
        dev_dtype_layout.addWidget(self.mula_dtype_combo)
        model_layout.addRow("Device/Dtype:", dev_dtype_layout)

        dev_dtype_layout2 = QHBoxLayout()
        dev_dtype_layout2.addWidget(QLabel("Codec:"))
        self.codec_device_combo = QComboBox()
        self.codec_device_combo.addItems(["cuda:0", "cuda:1", "cpu"])
        dev_dtype_layout2.addWidget(self.codec_device_combo)
        self.codec_dtype_combo = QComboBox()
        self.codec_dtype_combo.addItems(["float32", "float16", "bfloat16"])
        dev_dtype_layout2.addWidget(self.codec_dtype_combo)
        model_layout.addRow("Device/Dtype:", dev_dtype_layout2)

        self.lazy_load_check = QCheckBox("Enable Lazy Loading (Prevents VRAM Crashes)")
        self.lazy_load_check.setChecked(True)
        model_layout.addRow("Optimization:", self.lazy_load_check)
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # Generation Parameters
        gen_group = QGroupBox("Generation Parameters")
        gen_layout = QFormLayout()

        self.variations_spin = QSpinBox()
        self.variations_spin.setRange(1, 20)
        self.variations_spin.setValue(1)
        self.variations_spin.setToolTip("Number of variations to generate")
        gen_layout.addRow("Variations:", self.variations_spin)

        self.max_length_spin = QSpinBox()
        self.max_length_spin.setRange(10000, 600000)
        self.max_length_spin.setSingleStep(10000)
        self.max_length_spin.setValue(DEFAULT_MAX_LENGTH_MS)
        self.max_length_spin.setSuffix(" ms")
        gen_layout.addRow("Max Length:", self.max_length_spin)

        params_btn_layout = QHBoxLayout()
        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 100)
        self.topk_spin.setValue(50)
        params_btn_layout.addWidget(self.topk_spin)
        self.randomize_btn = QPushButton("🎲")
        self.randomize_btn.setFixedWidth(40)
        self.randomize_btn.setToolTip("Randomize parameters")
        self.randomize_btn.clicked.connect(self.randomize_params)
        params_btn_layout.addWidget(self.randomize_btn)
        gen_layout.addRow("Top-K:", params_btn_layout)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.1, 2.0)
        self.temperature_spin.setValue(1.0)
        self.temperature_spin.setSingleStep(0.1)
        gen_layout.addRow("Temperature:", self.temperature_spin)

        self.cfg_scale_spin = QDoubleSpinBox()
        self.cfg_scale_spin.setRange(0.1, 3.0)
        self.cfg_scale_spin.setValue(1.5)
        self.cfg_scale_spin.setSingleStep(0.1)
        gen_layout.addRow("CFG Scale:", self.cfg_scale_spin)
        
        self.save_log_check = QCheckBox("Save full console log with track")
        self.save_log_check.setChecked(True)
        gen_layout.addRow("Debugging:", self.save_log_check)
        
        gen_group.setLayout(gen_layout)
        layout.addWidget(gen_group)

        # Output Configuration
        out_group = QGroupBox("Output")
        out_layout = QVBoxLayout()
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp3", "wav"])
        self.format_combo.currentTextChanged.connect(self.update_output_extension)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        out_layout.addLayout(format_layout)

        path_browse_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit(DEFAULT_OUTPUT_PATH)
        btn_browse_out = QPushButton("...")
        btn_browse_out.setFixedWidth(40)
        btn_browse_out.clicked.connect(self.browse_output)
        path_browse_layout.addWidget(self.output_path_edit)
        path_browse_layout.addWidget(btn_browse_out)
        out_layout.addLayout(path_browse_layout)
        out_group.setLayout(out_layout)
        layout.addWidget(out_group)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("🎵 Generate\n(Ctrl+Enter)")
        self.generate_btn.setMinimumHeight(55)
        self.generate_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.generate_btn.setStyleSheet(f"font-size: 14px; font-weight: bold; background-color: {COLOR_SUCCESS}; color: white; border: none; border-radius: 4px;")
        self.generate_btn.clicked.connect(self.start_generation)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setMinimumHeight(55)
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.setStyleSheet(f"font-size: 14px; font-weight: bold; background-color: {COLOR_ERROR}; color: white; border: none; border-radius: 4px;")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_generation)

        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        secondary_btn_layout = QHBoxLayout()
        self.regen_btn = QPushButton("🔄 Regenerate Last")
        self.regen_btn.setToolTip("Regenerate with last parameters")
        self.regen_btn.clicked.connect(self.regenerate_last)
        secondary_btn_layout.addWidget(self.regen_btn)
        
        self.add_queue_btn = QPushButton("➕ Queue")
        self.add_queue_btn.setToolTip("Add to queue (Ctrl+Q)")
        self.add_queue_btn.clicked.connect(self.add_to_queue)
        secondary_btn_layout.addWidget(self.add_queue_btn)
        layout.addLayout(secondary_btn_layout)

        self.gen_progress_bar = QProgressBar()
        self.gen_progress_bar.setRange(0, 1)
        self.gen_progress_bar.setVisible(False)
        self.gen_progress_bar.setTextVisible(False)
        self.gen_progress_bar.setFixedHeight(8)
        layout.addWidget(self.gen_progress_bar)

        layout.addStretch()
        return container

    def create_right_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"QTabWidget::pane {{ border: 1px solid {COLOR_BORDER}; }}")

        # === Tab 1: Editor ===
        editor_tab = QWidget()
        editor_layout = QVBoxLayout(editor_tab)
        
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Quick Start:"))
        self.template_combo = QComboBox()
        self.template_combo.addItems(["Select a template..."] + list(SONG_TEMPLATES.keys()))
        self.template_combo.currentTextChanged.connect(self.apply_template)
        template_layout.addWidget(self.template_combo, 1)
        
        btn_word_count = QPushButton("📊 Stats")
        btn_word_count.clicked.connect(self.show_detailed_stats)
        template_layout.addWidget(btn_word_count)
        
        editor_layout.addLayout(template_layout)

        editor_split = QSplitter(Qt.Horizontal)
        
        # Left: Lyrics Editor
        lyrics_container = QWidget()
        lyrics_layout = QVBoxLayout(lyrics_container)

        toolbar_layout = QHBoxLayout()
        for s in ["[Intro]", "[Verse]", "[Prechorus]", "[Chorus]", "[Bridge]", "[Outro]"]:
            btn = QPushButton(s)
            btn.setMaximumHeight(28)
            btn.clicked.connect(lambda checked, st=s: self.insert_structure(st))
            toolbar_layout.addWidget(btn)
        toolbar_layout.addStretch()
        btn_import_lyrics = QPushButton("📁 Import")
        btn_import_lyrics.setMaximumHeight(28)
        btn_import_lyrics.clicked.connect(self.import_lyrics)
        toolbar_layout.addWidget(btn_import_lyrics)
        
        btn_clear_lyrics = QPushButton("🗑 Clear")
        btn_clear_lyrics.setMaximumHeight(28)
        btn_clear_lyrics.clicked.connect(lambda: self.lyrics_edit.clear())
        toolbar_layout.addWidget(btn_clear_lyrics)
        lyrics_layout.addLayout(toolbar_layout)

        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setFont(QFont("Consolas", 11))
        self.lyrics_edit.textChanged.connect(self.update_lyrics_stats)
        self.lyrics_edit.textChanged.connect(self._mark_modified)
        self.highlighter = SongStructureHighlighter(self.lyrics_edit.document())
        lyrics_layout.addWidget(self.lyrics_edit)

        self.lyrics_stats_label = QLabel("Words: 0 | Lines: 0 | Est. Time: 00:00")
        self.lyrics_stats_label.setStyleSheet("color: #888; font-size: 10px;")
        lyrics_layout.addWidget(self.lyrics_stats_label)

        # Right: Tags Panel
        tags_container = QWidget()
        tags_layout = QVBoxLayout(tags_container)
        
        tags_layout.addWidget(QLabel("Active Tags:"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setFont(QFont("Consolas", 11))
        self.tags_edit.setPlaceholderText("Enter tags separated by commas...")
        self.tags_edit.textChanged.connect(self._mark_modified)
        tags_layout.addWidget(self.tags_edit)
        
        # Tag database browser
        tags_browser_layout = QHBoxLayout()
        
        # Favorites panel
        fav_group = QGroupBox("⭐ Favorites")
        fav_layout = QVBoxLayout()
        self.favorites_list = QListWidget()
        self.favorites_list.setMaximumHeight(120)
        self.favorites_list.itemDoubleClicked.connect(self._add_tag_from_favorites)
        fav_layout.addWidget(self.favorites_list)
        
        fav_btn_layout = QHBoxLayout()
        btn_add_fav = QPushButton("➕ Add")
        btn_add_fav.clicked.connect(self.add_current_tag_to_favorites)
        btn_remove_fav = QPushButton("➖ Remove")
        btn_remove_fav.clicked.connect(self.remove_favorite_tag)
        fav_btn_layout.addWidget(btn_add_fav)
        fav_btn_layout.addWidget(btn_remove_fav)
        fav_layout.addLayout(fav_btn_layout)
        fav_group.setLayout(fav_layout)
        tags_browser_layout.addWidget(fav_group)
        
        # Tag categories
        cat_group = QGroupBox("Tag Database")
        cat_layout = QVBoxLayout()
        self.tag_tree = QTreeWidget()
        self.tag_tree.setHeaderHidden(True)
        self.tag_tree.itemDoubleClicked.connect(self._add_tag_from_tree)
        cat_layout.addWidget(self.tag_tree)
        cat_group.setLayout(cat_layout)
        tags_browser_layout.addWidget(cat_group)
        
        tags_layout.addLayout(tags_browser_layout)
        
        editor_split.addWidget(lyrics_container)
        editor_split.addWidget(tags_container)
        editor_split.setStretchFactor(0, 3)
        editor_split.setStretchFactor(1, 2)
        editor_layout.addWidget(editor_split)
        self.tabs.addTab(editor_tab, "📝 Editor")

        # === Tab 2: Transcription ===
        trans_tab = QWidget()
        trans_layout = QVBoxLayout(trans_tab)
        
        trans_toolbar = QHBoxLayout()
        trans_toolbar.addWidget(QLabel("Audio File:"))
        self.trans_audio_edit = QLineEdit()
        self.trans_audio_edit.setPlaceholderText("Drop audio file here or browse...")
        trans_toolbar.addWidget(self.trans_audio_edit)
        btn_browse_trans = QPushButton("...")
        btn_browse_trans.setFixedWidth(40)
        btn_browse_trans.clicked.connect(self.browse_trans_audio)
        trans_toolbar.addWidget(btn_browse_trans)

        self.transcribe_btn = QPushButton("▶ Transcribe")
        self.transcribe_btn.setStyleSheet(f"background-color: {COLOR_SUCCESS}; color: white; font-weight: bold;")
        self.transcribe_btn.clicked.connect(self.start_transcription)
        trans_toolbar.addWidget(self.transcribe_btn)

        self.stop_trans_btn = QPushButton("⏹ Stop")
        self.stop_trans_btn.setStyleSheet(f"background-color: {COLOR_ERROR}; color: white;")
        self.stop_trans_btn.setEnabled(False)
        self.stop_trans_btn.clicked.connect(self.stop_transcription)
        trans_toolbar.addWidget(self.stop_trans_btn)
        trans_layout.addLayout(trans_toolbar)

        self.trans_output = QTextEdit()
        self.trans_output.setReadOnly(True)
        self.trans_output.setFont(QFont("Consolas", 11))
        self.trans_output.setPlaceholderText("Transcription results will appear here...")
        trans_layout.addWidget(self.trans_output)

        trans_btn_layout = QHBoxLayout()
        btn_copy_trans = QPushButton("📋 Copy")
        btn_copy_trans.clicked.connect(self.copy_transcription)
        btn_export_trans = QPushButton("💾 Export to File")
        btn_export_trans.clicked.connect(self.export_transcription)
        btn_clear_trans = QPushButton("🗑 Clear")
        btn_clear_trans.clicked.connect(self.trans_output.clear)
        trans_btn_layout.addWidget(btn_copy_trans)
        trans_btn_layout.addWidget(btn_export_trans)
        trans_btn_layout.addWidget(btn_clear_trans)
        trans_btn_layout.addStretch()
        trans_layout.addLayout(trans_btn_layout)

        self.tabs.addTab(trans_tab, "🎙 Transcription")

        # === Tab 3: Queue Manager ===
        queue_tab = QWidget()
        queue_layout = QVBoxLayout(queue_tab)
        
        queue_info_label = QLabel("Queue items will be generated sequentially with their own parameters.")
        queue_info_label.setStyleSheet("color: #888; font-size: 11px;")
        queue_layout.addWidget(queue_info_label)
        
        queue_btn_layout = QHBoxLayout()
        btn_add_queue = QPushButton("➕ Add Current")
        btn_add_queue.setToolTip("Add current lyrics/tags to queue (Ctrl+Q)")
        btn_add_queue.clicked.connect(self.add_to_queue)
        btn_start_queue = QPushButton("▶ Start Queue")
        btn_start_queue.setStyleSheet(f"background-color: {COLOR_SUCCESS}; color: white; font-weight: bold;")
        btn_start_queue.clicked.connect(self.start_queue)
        btn_remove_queue = QPushButton("➖ Remove Selected")
        btn_remove_queue.clicked.connect(self.remove_queue_item)
        btn_clear_queue = QPushButton("🗑 Clear All")
        btn_clear_queue.clicked.connect(self.clear_queue)
        queue_btn_layout.addWidget(btn_add_queue)
        queue_btn_layout.addWidget(btn_start_queue)
        queue_btn_layout.addWidget(btn_remove_queue)
        queue_btn_layout.addWidget(btn_clear_queue)
        queue_layout.addLayout(queue_btn_layout)

        self.queue_list = QListWidget()
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self._queue_context_menu)
        queue_layout.addWidget(self.queue_list)
        self.tabs.addTab(queue_tab, "📋 Queue Manager")

        # === Tab 4: Console ===
        console_tab = QWidget()
        console_layout = QVBoxLayout(console_tab)

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Consolas", 10))
        self.console_output.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        console_layout.addWidget(self.console_output)
        
        console_btn_layout = QHBoxLayout()
        btn_clear_console = QPushButton("🗑 Clear")
        btn_clear_console.clicked.connect(self.console_output.clear)
        btn_save_log = QPushButton("💾 Save Log")
        btn_save_log.clicked.connect(self.save_console_log)
        console_btn_layout.addWidget(btn_clear_console)
        console_btn_layout.addWidget(btn_save_log)
        console_btn_layout.addStretch()
        console_layout.addLayout(console_btn_layout)
        
        self.tabs.addTab(console_tab, "🖥 Console")

        # === Tab 5: Player & History ===
        player_tab = QWidget()
        player_layout = QHBoxLayout(player_tab)
        
        # History panel
        history_group = QGroupBox("History")
        history_layout = QVBoxLayout()
        
        search_layout = QHBoxLayout()
        self.history_search_edit = QLineEdit()
        self.history_search_edit.setPlaceholderText("🔍 Search history...")
        self.history_search_edit.textChanged.connect(self._on_history_search_changed)
        search_layout.addWidget(self.history_search_edit)
        btn_refresh_history = QPushButton("🔄")
        btn_refresh_history.setFixedWidth(40)
        btn_refresh_history.clicked.connect(self.refresh_history)
        search_layout.addWidget(btn_refresh_history)
        history_layout.addLayout(search_layout)
        
        self.history_list = QListWidget()
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._history_context_menu)
        self.history_list.itemDoubleClicked.connect(self.load_history_item)
        history_layout.addWidget(self.history_list)
        
        history_btn_layout = QHBoxLayout()
        btn_open_history_folder = QPushButton("📁 Open Folder")
        btn_open_history_folder.clicked.connect(self.open_history_folder)
        btn_delete_history = QPushButton("🗑 Delete")
        btn_delete_history.clicked.connect(self.delete_history_item)
        history_btn_layout.addWidget(btn_open_history_folder)
        history_btn_layout.addWidget(btn_delete_history)
        history_layout.addLayout(history_btn_layout)
        
        history_group.setLayout(history_layout)
        player_layout.addWidget(history_group, 1)

        # Player controls
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        
        self.track_label = QLabel("No track loaded.")
        self.track_label.setAlignment(Qt.AlignCenter)
        self.track_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        controls_layout.addWidget(self.track_label)
        
        # Position slider
        slider_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setFixedWidth(50)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setFixedWidth(50)
        slider_layout.addWidget(self.current_time_label)
        slider_layout.addWidget(self.position_slider)
        slider_layout.addWidget(self.total_time_label)
        controls_layout.addLayout(slider_layout)
        
        # Playback controls
        playback_layout = QHBoxLayout()
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(40, 40)
        self.prev_btn.clicked.connect(self.play_previous)
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(50, 50)
        self.play_btn.setStyleSheet(f"font-size: 20px; background-color: {COLOR_ACCENT}; color: white; border: none; border-radius: 25px;")
        self.play_btn.clicked.connect(self.toggle_play)
        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(40, 40)
        self.next_btn.clicked.connect(self.play_next)
        playback_layout.addStretch()
        playback_layout.addWidget(self.prev_btn)
        playback_layout.addWidget(self.play_btn)
        playback_layout.addWidget(self.next_btn)
        playback_layout.addStretch()
        controls_layout.addLayout(playback_layout)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("🔊"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_layout.addWidget(self.volume_slider)
        controls_layout.addLayout(volume_layout)
        
        controls_layout.addStretch()
        player_layout.addWidget(controls_container, 2)
        self.tabs.addTab(player_tab, "🎵 Player & History")

        # === Tab 6: Tag Manager ===
        tag_manager_tab = QWidget()
        tag_manager_layout = QVBoxLayout(tag_manager_tab)
        
        tag_info = QLabel("Manage your tag database. Double-click tags in Editor to add them.")
        tag_info.setStyleSheet("color: #888;")
        tag_manager_layout.addWidget(tag_info)
        
        add_tag_layout = QHBoxLayout()
        add_tag_layout.addWidget(QLabel("Category:"))
        self.new_tag_category = QComboBox()
        self.new_tag_category.addItems(list(DEFAULT_TAG_DB.keys()))
        add_tag_layout.addWidget(self.new_tag_category)
        add_tag_layout.addWidget(QLabel("Tag:"))
        self.new_tag_text = QLineEdit()
        self.new_tag_text.setPlaceholderText("Enter new tag...")
        add_tag_layout.addWidget(self.new_tag_text)
        btn_add_tag = QPushButton("➕ Add Tag")
        btn_add_tag.clicked.connect(self.add_tag_to_db)
        add_tag_layout.addWidget(btn_add_tag)
        tag_manager_layout.addLayout(add_tag_layout)
        
        btn_reset_db = QPushButton("🔄 Reset to Default Database")
        btn_reset_db.clicked.connect(self.reset_tag_db)
        tag_manager_layout.addWidget(btn_reset_db)
        
        self.tag_manager_tree = QTreeWidget()
        self.tag_manager_tree.setHeaderLabels(["Category", "Tags"])
        self.tag_manager_tree.itemDoubleClicked.connect(self._remove_tag_from_db)
        tag_manager_layout.addWidget(self.tag_manager_tree)
        
        self.refresh_tag_manager()
        self.tabs.addTab(tag_manager_tab, "🏷 Tag Manager")

        return self.tabs

    # --- LOGGING ---
    # -------------------------------------------------------------------------
    def log_console(self, text: str, level: str = "info") -> None:
        safe = text.replace("<", "&lt;").replace(">", "&gt;")
        safe = _ANSI_RE.sub('', safe)
        
        if level == "error":
            color = COLOR_ERROR
            weight = "bold"
        elif level == "warning":
            color = COLOR_WARNING
            weight = "normal"
        elif level == "success":
            color = COLOR_SUCCESS
            weight = "normal"
        else:
            # Auto-detect based on content
            if _ERROR_RE.search(text):
                color = COLOR_ERROR
                weight = "bold"
            elif _WARN_RE.search(text):
                color = COLOR_WARNING
                weight = "normal"
            elif _SUCCESS_RE.search(text):
                color = COLOR_SUCCESS
                weight = "normal"
            else:
                color = COLOR_INFO
                weight = "normal"
        
        html = f'<span style="color:{color};font-weight:{weight};white-space:pre-wrap;">{safe}</span>'
        self.console_output.moveCursor(QTextCursor.End)
        self.console_output.insertHtml(html)
        self.console_output.ensureCursorVisible()
        
        # Log to file
        if level == "error":
            self.logger.error(text.strip())
        elif level == "warning":
            self.logger.warning(text.strip())
        else:
            self.logger.info(text.strip())

    def save_console_log(self) -> None:
        f, _ = QFileDialog.getSaveFileName(self, "Save Console Log", f"console_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", "Log Files (*.log);;Text Files (*.txt)")
        if f:
            try:
                with open(f, "w", encoding="utf-8") as file:
                    file.write(self.console_output.toPlainText())
                self.log_console(f"Console log saved to {f}\n", "success")
            except Exception as e:
                self.log_console(f"Failed to save log: {e}\n", "error")

    # --- GENERATION ENGINE ---
    # -------------------------------------------------------------------------
    def start_generation(self) -> None:
        if not HAS_AI_LIBS:
            self._show_ai_warning()
            return
        if self.gen_thread is not None and self.gen_thread.isRunning():
            self.log_console("Generation is already running.\n", "warning")
            return
            
        lyrics = self.lyrics_edit.toPlainText()
        tags = self.tags_edit.text()
        base_output = self.output_path_edit.text()
        if not lyrics:
            self.log_console("Lyrics cannot be empty.\n", "error")
            return
        if not tags:
            self.log_console("Tags cannot be empty.\n", "error")
            return
        if not base_output:
            self.log_console("Output path cannot be empty.\n", "error")
            return

        # Save last generation params
        self.last_generation_params = {
            'lyrics': lyrics,
            'tags': tags,
            'output': base_output,
            'variations': self.variations_spin.value(),
            'max_len': self.max_length_spin.value(),
            'topk': self.topk_spin.value(),
            'temp': self.temperature_spin.value(),
            'cfg': self.cfg_scale_spin.value(),
            'format': self.format_combo.currentText(),
            'mula_device': self.mula_device_combo.currentText(),
            'codec_device': self.codec_device_combo.currentText(),
            'mula_dtype': self.mula_dtype_combo.currentText(),
            'codec_dtype': self.codec_dtype_combo.currentText(),
        }

        self.total_variations = self.variations_spin.value()
        self.current_variation = 0
        self._full_console_log = ""
        self.prepare_and_run(lyrics, tags, base_output)

    def prepare_and_run(self, lyrics: str, tags: str, base_output: str) -> None:
        if self.total_variations > 1:
            base, _ = os.path.splitext(base_output)
            output = f"{base}_v{self.current_variation + 1}"
        else:
            output = os.path.splitext(base_output)[0]
        output += f".{self.format_combo.currentText()}"

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="lyrics_", dir=str(self.temp_dir), delete=False, encoding='utf-8') as f:
                f.write(lyrics)
                self.lyrics_file = f.name
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="tags_", dir=str(self.temp_dir), delete=False, encoding='utf-8') as f:
                f.write(tags)
                self.tags_file = f.name
        except Exception as e:
            self.log_console(f"Failed to create temp files: {e}\n", "error")
            return

        self.log_console(f"\n{'='*60}\n--- Starting Variation {self.current_variation + 1}/{self.total_variations} ---\n{'='*60}\n")
        self.log_console(f"Output: {output}\n")
        self.log_console(f"Params: topk={self.topk_spin.value()}, temp={self.temperature_spin.value()}, cfg={self.cfg_scale_spin.value()}, max_len={self.max_length_spin.value()}ms\n\n")
        
        self.generate_btn.setEnabled(False)
        self.regen_btn.setEnabled(False)
        self.add_queue_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.gen_progress_bar.setVisible(True)
        self.gen_progress_bar.setRange(0, 0)
        self.gen_start_time = time.time()
        self.gen_timer.start(GEN_TIMER_INTERVAL_MS)
        self.current_output_path = output
        self.status_label.setText(f"Generating variation {self.current_variation + 1}/{self.total_variations}...")

        # Setup Thread
        self.gen_thread = QThread()
        self.gen_worker = GenerationWorker(
            self.model_path_edit.text(), self.version_combo.currentText(),
            self.lyrics_file, self.tags_file, output,
            self.max_length_spin.value(), self.topk_spin.value(),
            self.temperature_spin.value(), self.cfg_scale_spin.value(),
            self.mula_device_combo.currentText(), self.codec_device_combo.currentText(),
            self.mula_dtype_combo.currentText(), self.codec_dtype_combo.currentText(),
            self.lazy_load_check.isChecked()
        )
        self.gen_worker.moveToThread(self.gen_thread)
        
        self.gen_thread.started.connect(self.gen_worker.run)
        self.gen_worker.finished.connect(self.on_gen_finished)
        self.gen_worker.error.connect(self.on_gen_error)
        self.gen_worker.progress.connect(self.log_console)
        self.gen_thread.start()

    def on_gen_finished(self, save_path: str) -> None:
        self.gen_thread.quit()
        self.gen_thread.wait()
        
        self.log_console(f"\n✅ Variation {self.current_variation + 1} generated successfully!\n", "success")
        
        # Save log if enabled
        if self.save_log_check.isChecked():
            log_path = os.path.splitext(save_path)[0] + "_log.txt"
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(self._full_console_log)
            except:
                pass
        
        # Copy to history
        try:
            history_path = self.history_dir / os.path.basename(save_path)
            shutil.copy2(save_path, history_path)
        except:
            pass
        
        self.current_variation += 1
        
        if self.current_variation < self.total_variations:
            self.prepare_and_run(self.lyrics_edit.toPlainText(), self.tags_edit.text(), self.output_path_edit.text())
            return
            
        self.gen_timer.stop()
        self.gen_progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.regen_btn.setEnabled(True)
        self.add_queue_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Ready")
        
        self.track_label.setText(f"🎵 {os.path.basename(save_path)}")
        self.mini_track_label.setText(os.path.basename(save_path))
        self.media_player.setSource(QUrl.fromLocalFile(save_path))
        self.play_btn.setEnabled(True)
        self.mini_play_btn.setEnabled(True)
        self.refresh_history()
        
        # Switch to player tab
        self.tabs.setCurrentIndex(4)
        
        # Process queue if running
        if self.queue_running:
            QTimer.singleShot(1000, self.process_next_queue_item)

    def on_gen_error(self, error_msg: str) -> None:
        self.gen_thread.quit()
        self.gen_thread.wait()
        
        self.log_console(f"\n❌ ERROR: {error_msg}\n", "error")
        self.gen_timer.stop()
        self.gen_progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.regen_btn.setEnabled(True)
        self.add_queue_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Error occurred")
        
        if self.queue_running:
            self.log_console("Queue stopped due to error.\n", "warning")
            self.queue_running = False

    def stop_generation(self) -> None:
        if self.gen_thread and self.gen_thread.isRunning():
            self.log_console("⚠ Cannot interrupt active AI inference. Stop will take effect after current variation completes.\n", "warning")
            self.current_variation = self.total_variations
            self.queue_running = False
            self.queue_items.clear()
            self.queue_list.clear()
            self.update_queue_label()

    # --- TRANSCRIPTION ENGINE ---
    # -------------------------------------------------------------------------
    def start_transcription(self) -> None:
        if not HAS_AI_LIBS:
            self._show_ai_warning()
            return
        if self.trans_thread is not None and self.trans_thread.isRunning():
            self.log_console("Transcription is already running.\n", "warning")
            return
            
        audio_path = self.trans_audio_edit.text().strip()
        if not audio_path or not os.path.exists(audio_path):
            self.log_console("Please select a valid audio file to transcribe.\n", "error")
            return
            
        self.trans_output.clear()
        self.transcribe_btn.setEnabled(False)
        self.stop_trans_btn.setEnabled(True)
        self.status_label.setText("Transcribing...")
        
        self.trans_thread = QThread()
        self.trans_worker = TranscriptionWorker(self.model_path_edit.text(), audio_path)
        self.trans_worker.moveToThread(self.trans_thread)
        
        self.trans_thread.started.connect(self.trans_worker.run)
        self.trans_worker.finished.connect(self.on_trans_finished)
        self.trans_worker.error.connect(self.on_trans_error)
        self.trans_worker.progress.connect(self.log_console)
        self.trans_thread.start()

    def on_trans_finished(self, result: str) -> None:
        self.trans_thread.quit()
        self.trans_thread.wait()
        self.trans_output.setPlainText(result)
        self.transcribe_btn.setEnabled(True)
        self.stop_trans_btn.setEnabled(False)
        self.status_label.setText("Ready")
        self.log_console("✅ Transcription completed.\n", "success")

    def on_trans_error(self, error_msg: str) -> None:
        self.trans_thread.quit()
        self.trans_thread.wait()
        self.transcribe_btn.setEnabled(True)
        self.stop_trans_btn.setEnabled(False)
        self.status_label.setText("Ready")
        self.log_console(f"❌ Transcription failed: {error_msg}\n", "error")

    def stop_transcription(self) -> None:
        self.log_console("⚠ Cannot interrupt active AI inference.\n", "warning")

    def copy_transcription(self) -> None:
        text = self.trans_output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.log_console("Transcription copied to clipboard.\n", "success")

    def export_transcription(self) -> None:
        text = self.trans_output.toPlainText()
        if not text:
            self.log_console("No transcription to export.\n", "warning")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Export Transcription", "transcription.txt", "Text Files (*.txt)")
        if f:
            try:
                with open(f, "w", encoding="utf-8") as file:
                    file.write(text)
                self.log_console(f"Transcription exported to {f}\n", "success")
            except Exception as e:
                self.log_console(f"Failed to export: {e}\n", "error")

    # --- MISC & EVENT HANDLERS ---
    # -------------------------------------------------------------------------
    def _mark_modified(self) -> None:
        self.is_modified = True
        self.autosave_label.setText("● Unsaved changes")

    def _clear_modified(self) -> None:
        self.is_modified = False
        self.autosave_label.setText("✓ Saved")

    def update_gen_timer(self) -> None:
        elapsed = int(time.time() - self.gen_start_time)
        self.gen_timer_label.setText(f"⏱ Elapsed: {time.strftime('%M:%S', time.gmtime(elapsed))}")

    def browse_trans_audio(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.mp3 *.wav *.flac *.ogg)")
        if f:
            self.trans_audio_edit.setText(f)

    def cleanup_temp_files(self) -> None:
        if not self.temp_dir.exists(): 
            return
        cleaned = 0
        for f in self.temp_dir.glob("*"):
            try:
                if f.is_file(): 
                    f.unlink()
                    cleaned += 1
                elif f.is_dir(): 
                    shutil.rmtree(f, ignore_errors=True)
                    cleaned += 1
            except Exception:
                pass
        self.log_console(f"Cleaned {cleaned} temp file(s).\n", "info")

    def check_vram(self) -> None:
        if self.vram_available and self.vram_process.state() == QProcess.NotRunning:
            self.vram_process.start("nvidia-smi", ["--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"])

    def parse_vram(self) -> None:
        output = self.vram_process.readAllStandardOutput().data().decode().strip()
        if not output: 
            return
        try:
            parts = output.split('\n')[0].split(', ')
            used, total = int(parts[0]), int(parts[1])
            percent = (used / total) * 100
            self.vram_label.setText(f"VRAM: {used}/{total}MB ({percent:.0f}%)")
            
            if percent > VRAM_WARN_THRESHOLD and not self._vram_warned:
                self.vram_label.setStyleSheet(f"font-weight: bold; padding: 0 10px; color: {COLOR_ERROR};")
                self.log_console(f"⚠ VRAM usage at {percent:.0f}%! Consider reducing max length or enabling lazy loading.\n", "warning")
                self._vram_warned = True
            elif percent < VRAM_CLEAR_THRESHOLD and self._vram_warned:
                self.vram_label.setStyleSheet("font-weight: bold; padding: 0 10px;")
                self._vram_warned = False
        except:
            pass

    def on_vram_error(self, error) -> None:
        self.vram_available = False
        self.vram_label.setText("VRAM: N/A")
        self.vram_timer.stop()

    # --- MEDIA PLAYER ---
    # -------------------------------------------------------------------------
    def toggle_play(self) -> None:
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def update_position(self, position: int) -> None:
        if not self._seeking:
            self.position_slider.setValue(position)
        self.current_time_label.setText(time.strftime('%M:%S', time.gmtime(position / 1000)))
        self.mini_time_label.setText(f"{time.strftime('%M:%S', time.gmtime(position / 1000))} / {time.strftime('%M:%S', time.gmtime(self.media_player.duration() / 1000))}")

    def update_duration(self, duration: int) -> None:
        self.position_slider.setRange(0, duration)
        self.total_time_label.setText(time.strftime('%M:%S', time.gmtime(duration / 1000)))

    def handle_media_status(self, status) -> None:
        if status == QMediaPlayer.EndOfMedia:
            self.play_btn.setText("▶")
            self.mini_play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def on_playback_state_changed(self, state) -> None:
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("⏸")
            self.mini_play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_btn.setText("▶")
            self.mini_play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def on_media_error(self, error, error_string="") -> None:
        if error != QMediaPlayer.NoError:
            self.log_console(f"Media error: {error_string}\n", "error")

    def _on_slider_pressed(self) -> None:
        self._seeking = True

    def _on_slider_released(self) -> None:
        self._seeking = False
        self.media_player.setPosition(self.position_slider.value())

    def _on_slider_moved(self, position: int) -> None:
        self.current_time_label.setText(time.strftime('%M:%S', time.gmtime(position / 1000)))

    def _on_volume_changed(self, value: int) -> None:
        self.audio_output.setVolume(value / 100.0)

    def play_previous(self) -> None:
        current_row = self.history_list.currentRow()
        if current_row > 0:
            self.history_list.setCurrentRow(current_row - 1)
            item = self.history_list.currentItem()
            if item:
                self.load_history_item(item)

    def play_next(self) -> None:
        current_row = self.history_list.currentRow()
        if current_row < self.history_list.count() - 1:
            self.history_list.setCurrentRow(current_row + 1)
            item = self.history_list.currentItem()
            if item:
                self.load_history_item(item)

    def load_history_item(self, item) -> None:
        path = item.data(Qt.UserRole)
        if path and os.path.exists(path):
            self.media_player.setSource(QUrl.fromLocalFile(path))
            self.track_label.setText(f"🎵 {os.path.basename(path)}")
            self.mini_track_label.setText(os.path.basename(path))
            self.play_btn.setEnabled(True)
            self.mini_play_btn.setEnabled(True)

    def open_history_folder(self) -> None:
        if sys.platform == "win32":
            os.startfile(str(self.history_dir))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(self.history_dir)])
        else:
            subprocess.Popen(["xdg-open", str(self.history_dir)])

    def delete_history_item(self) -> None:
        item = self.history_list.currentItem()
        if not item:
            return
        path = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete File", f"Delete {os.path.basename(path)}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                os.remove(path)
                self.refresh_history()
                self.log_console(f"Deleted {path}\n", "info")
            except Exception as e:
                self.log_console(f"Failed to delete: {e}\n", "error")

    def _history_context_menu(self, pos: QPoint) -> None:
        item = self.history_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        action_load = menu.addAction("▶ Load")
        action_delete = menu.addAction("🗑 Delete")
        action_copy = menu.addAction("📋 Copy Path")
        action = menu.exec(self.history_list.mapToGlobal(pos))
        if action == action_load:
            self.load_history_item(item)
        elif action == action_delete:
            self.delete_history_item()
        elif action == action_copy:
            QApplication.clipboard().setText(item.data(Qt.UserRole))

    # --- HISTORY ---
    # -------------------------------------------------------------------------
    def refresh_history(self) -> None:
        self.history_list.clear()
        files = []
        for ext in ["*.mp3", "*.wav", "*.flac"]:
            files.extend(self.history_dir.glob(ext))
        files.sort(key=os.path.getmtime, reverse=True)
        for file in files:
            mod_time = datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            size_mb = file.stat().st_size / (1024 * 1024)
            item = QListWidgetItem(f"{file.name}\n  {mod_time} | {size_mb:.1f} MB")
            item.setData(Qt.UserRole, str(file))
            self.history_list.addItem(item)

    def _on_history_search_changed(self) -> None:
        self._history_filter_timer.start()

    def _do_filter_history(self) -> None:
        query = self.history_search_edit.text().lower().strip()
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            item.setHidden(query not in item.text().lower())

    # --- QUEUE MANAGEMENT ---
    # -------------------------------------------------------------------------
    def update_queue_label(self) -> None:
        self.queue_label.setText(f"📋 Queue: {len(self.queue_items)} items")

    def add_to_queue(self) -> None:
        if not self.lyrics_edit.toPlainText() or not self.tags_edit.text():
            self.log_console("Cannot add empty item to queue.\n", "warning")
            return
        item = QueueItem(
            lyrics=self.lyrics_edit.toPlainText(),
            tags=self.tags_edit.text(),
            temp=self.temperature_spin.value(),
            topk=self.topk_spin.value(),
            cfg=self.cfg_scale_spin.value(),
            max_len=self.max_length_spin.value(),
            format=self.format_combo.currentText(),
            output_path=self.output_path_edit.text(),
            variations=self.variations_spin.value(),
            mula_device=self.mula_device_combo.currentText(),
            codec_device=self.codec_device_combo.currentText(),
            mula_dtype=self.mula_dtype_combo.currentText(),
            codec_dtype=self.codec_dtype_combo.currentText(),
            label=f"Track {len(self.queue_items) + 1}"
        )
        self.queue_items.append(item)
        self.queue_list.addItem(f"{item.label}: {item.tags[:40]}...")
        self.update_queue_label()
        self.save_queue()
        self.log_console(f"Added to queue: {item.label}\n", "success")

    def remove_queue_item(self) -> None:
        row = self.queue_list.currentRow()
        if row >= 0 and not self.queue_running:
            self.queue_list.takeItem(row)
            if row < len(self.queue_items):
                self.queue_items.pop(row)
            self.update_queue_label()
            self.save_queue()

    def _queue_context_menu(self, pos: QPoint) -> None:
        item = self.queue_list.itemAt(pos)
        if not item or self.queue_running:
            return
        menu = QMenu(self)
        action_remove = menu.addAction("➖ Remove")
        action_clear = menu.addAction("🗑 Clear All")
        action = menu.exec(self.queue_list.mapToGlobal(pos))
        if action == action_remove:
            self.remove_queue_item()
        elif action == action_clear:
            self.clear_queue()

    def clear_queue(self) -> None:
        if self.queue_running:
            self.log_console("Cannot clear queue while running.\n", "warning")
            return
        self.queue_items.clear()
        self.queue_list.clear()
        self.update_queue_label()
        self.save_queue()

    def start_queue(self) -> None:
        if not self.queue_items:
            self.log_console("Queue is empty.\n", "warning")
            return
        if not HAS_AI_LIBS:
            self._show_ai_warning()
            return
        self.queue_running = True
        self.log_console(f"\n{'='*60}\n🎬 Starting queue with {len(self.queue_items)} items\n{'='*60}\n")
        self.process_next_queue_item()

    def process_next_queue_item(self) -> None:
        if not self.queue_items or not self.queue_running:
            self.queue_running = False
            self.log_console("✅ Queue Complete!\n", "success")
            return
        item = self.queue_items.pop(0)
        self.queue_list.takeItem(0)
        self.update_queue_label()
        
        self.log_console(f"\n--- Processing: {item.label} ---\n")
        
        # Set UI from queue item
        self.lyrics_edit.setPlainText(item.lyrics)
        self.tags_edit.setText(item.tags)
        self.output_path_edit.setText(item.output_path)
        self.temperature_spin.setValue(item.temp)
        self.topk_spin.setValue(item.topk)
        self.cfg_scale_spin.setValue(item.cfg)
        self.max_length_spin.setValue(item.max_len)
        self.format_combo.setCurrentText(item.format)
        self.variations_spin.setValue(item.variations)
        self.mula_device_combo.setCurrentText(item.mula_device)
        self.codec_device_combo.setCurrentText(item.codec_device)
        self.mula_dtype_combo.setCurrentText(item.mula_dtype)
        self.codec_dtype_combo.setCurrentText(item.codec_dtype)
        
        self.start_generation()

    # --- TAG DATABASE ---
    # -------------------------------------------------------------------------
    def load_tag_db(self) -> None:
        """Load tag database from file or use defaults."""
        if os.path.exists(TAGS_DB_FILE):
            try:
                with open(TAGS_DB_FILE, "r", encoding="utf-8") as f:
                    self.tag_db = json.load(f)
            except:
                self.tag_db = DEFAULT_TAG_DB.copy()
        else:
            self.tag_db = DEFAULT_TAG_DB.copy()
        self.refresh_tag_tree()

    def save_tag_db(self) -> None:
        try:
            with open(TAGS_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.tag_db, f, indent=2)
        except Exception as e:
            self.log_console(f"Failed to save tag DB: {e}\n", "error")

    def refresh_tag_tree(self) -> None:
        self.tag_tree.clear()
        for category, tags in self.tag_db.items():
            cat_item = QTreeWidgetItem([f"📁 {category} ({len(tags)})"])
            for tag in tags:
                tag_item = QTreeWidgetItem([f"  #{tag}"])
                cat_item.addChild(tag_item)
            self.tag_tree.addTopLevelItem(cat_item)

    def refresh_tag_manager(self) -> None:
        if not hasattr(self, 'tag_db'):
            return
        self.tag_manager_tree.clear()
        for category, tags in self.tag_db.items():
            cat_item = QTreeWidgetItem([category, f"{len(tags)} tags"])
            for tag in tags:
                tag_item = QTreeWidgetItem(["", tag])
                cat_item.addChild(tag_item)
            self.tag_manager_tree.addTopLevelItem(cat_item)
            self.tag_manager_tree.expandItem(cat_item)

    def add_tag_to_db(self) -> None:
        category = self.new_tag_category.currentText()
        tag = self.new_tag_text.text().strip().lower().replace(" ", "_")
        if not tag:
            return
        if category not in self.tag_db:
            self.tag_db[category] = []
        if tag not in self.tag_db[category]:
            self.tag_db[category].append(tag)
            self.save_tag_db()
            self.refresh_tag_tree()
            self.refresh_tag_manager()
            self.log_console(f"Added tag '{tag}' to '{category}'\n", "success")
        else:
            self.log_console(f"Tag '{tag}' already exists in '{category}'\n", "warning")
        self.new_tag_text.clear()

    def _remove_tag_from_db(self, item, column) -> None:
        if item.parent() is None:
            return
        category = item.parent().text(0)
        tag = item.text(1) if item.text(1) else item.text(0).strip()
        reply = QMessageBox.question(self, "Remove Tag", f"Remove '{tag}' from '{category}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes and category in self.tag_db:
            if tag in self.tag_db[category]:
                self.tag_db[category].remove(tag)
                self.save_tag_db()
                self.refresh_tag_tree()
                self.refresh_tag_manager()
                self.log_console(f"Removed tag '{tag}'\n", "info")

    def reset_tag_db(self) -> None:
        reply = QMessageBox.question(self, "Reset Tag Database", "Reset to default tag database? This will lose all custom tags.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.tag_db = DEFAULT_TAG_DB.copy()
            self.save_tag_db()
            self.refresh_tag_tree()
            self.refresh_tag_manager()
            self.log_console("Tag database reset to defaults.\n", "success")

    def _add_tag_from_tree(self, item, column) -> None:
        if item.parent() is None:
            return
        tag = item.text(0).strip().replace("#", "").strip()
        self._add_tag_to_edit(tag)

    def _add_tag_to_edit(self, tag: str) -> None:
        current = self.tags_edit.text().strip()
        if current:
            if tag not in current.split(","):
                self.tags_edit.setText(f"{current}, {tag}")
        else:
            self.tags_edit.setText(tag)

    # --- FAVORITES ---
    # -------------------------------------------------------------------------
    def refresh_favorites(self) -> None:
        self.favorites_list.clear()
        for tag in self.favorite_tags:
            item = QListWidgetItem(f"⭐ {tag}")
            self.favorites_list.addItem(item)

    def add_current_tag_to_favorites(self) -> None:
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        if not tags:
            return
        tag, ok = QInputDialog.getItem(self, "Add to Favorites", "Select tag to add:", tags, 0, False)
        if ok and tag and tag not in self.favorite_tags:
            self.favorite_tags.append(tag)
            self.refresh_favorites()
            self.save_app_state()
            self.log_console(f"Added '{tag}' to favorites\n", "success")

    def remove_favorite_tag(self) -> None:
        item = self.favorites_list.currentItem()
        if not item:
            return
        tag = item.text().replace("⭐ ", "")
        if tag in self.favorite_tags:
            self.favorite_tags.remove(tag)
            self.refresh_favorites()
            self.save_app_state()
            self.log_console(f"Removed '{tag}' from favorites\n", "info")

    def _add_tag_from_favorites(self, item) -> None:
        tag = item.text().replace("⭐ ", "")
        self._add_tag_to_edit(tag)

    # --- UI HANDLERS ---
    # -------------------------------------------------------------------------
    def browse_dir(self, line_edit): 
        d = QFileDialog.getExistingDirectory(self, "Select Directory")
        if d: 
            line_edit.setText(d)

    def browse_output(self): 
        f, _ = QFileDialog.getSaveFileName(self, "Save Output", self.output_path_edit.text(), "Audio Files (*.mp3 *.wav)")
        if f: 
            self.output_path_edit.setText(f)

    def update_output_extension(self, text):
        current = self.output_path_edit.text()
        if current:
            base = os.path.splitext(current)[0]
            self.output_path_edit.setText(f"{base}.{text}")

    def insert_structure(self, text): 
        cursor = self.lyrics_edit.textCursor()
        if not cursor.atBlockStart():
            self.lyrics_edit.insertPlainText("\n")
        self.lyrics_edit.insertPlainText(f"{text}\n")
        self.lyrics_edit.setFocus()

    def import_lyrics(self): 
        f, _ = QFileDialog.getOpenFileName(self, "Import Lyrics", "", "Text Files (*.txt);;All Files (*.*)")
        if f:
            try:
                with open(f, "r", encoding="utf-8") as file: 
                    self.lyrics_edit.setPlainText(file.read())
                self.log_console(f"Lyrics imported from {f}\n", "success")
            except Exception as e:
                self.log_console(f"Failed to import: {e}\n", "error")

    def update_lyrics_stats(self):
        text = self.lyrics_edit.toPlainText()
        words = len(text.split())
        lines = len([l for l in text.split('\n') if l.strip()])
        # Estimate: ~150 BPM, ~2 words per second
        est_seconds = words / 2.5 if words > 0 else 0
        est_time = time.strftime('%M:%S', time.gmtime(est_seconds))
        self.lyrics_stats_label.setText(f"Words: {words} | Lines: {lines} | Est. Time: {est_time}")

    def show_detailed_stats(self) -> None:
        text = self.lyrics_edit.toPlainText()
        words = len(text.split())
        lines = len([l for l in text.split('\n') if l.strip()])
        chars = len(text)
        sections = len(re.findall(r'\[.*?\]', text))
        stages = len(re.findall(r'\(.*?\)', text))
        tags = len([t for t in self.tags_edit.text().split(',') if t.strip()])
        est_seconds = words / 2.5 if words > 0 else 0
        est_time = time.strftime('%M:%S', time.gmtime(est_seconds))
        
        msg = (
            f"<h3>Lyrics Statistics</h3>"
            f"<table cellpadding='4'>"
            f"<tr><td>Words:</td><td><b>{words}</b></td></tr>"
            f"<tr><td>Lines:</td><td><b>{lines}</b></td></tr>"
            f"<tr><td>Characters:</td><td><b>{chars}</b></td></tr>"
            f"<tr><td>Sections:</td><td><b>{sections}</b></td></tr>"
            f"<tr><td>Stage directions:</td><td><b>{stages}</b></td></tr>"
            f"<tr><td>Active tags:</td><td><b>{tags}</b></td></tr>"
            f"<tr><td>Estimated duration:</td><td><b>{est_time}</b></td></tr>"
            f"</table>"
        )
        QMessageBox.information(self, "Statistics", msg)

    def randomize_params(self):
        """Randomize generation parameters with sensible ranges."""
        self.topk_spin.setValue(random.randint(20, 80))
        self.temperature_spin.setValue(round(random.uniform(0.7, 1.5), 1))
        self.cfg_scale_spin.setValue(round(random.uniform(1.0, 2.5), 1))
        self.log_console(f"🎲 Randomized: topk={self.topk_spin.value()}, temp={self.temperature_spin.value()}, cfg={self.cfg_scale_spin.value()}\n", "info")

    def regenerate_last(self):
        if not self.last_generation_params:
            self.log_console("No previous generation to regenerate.\n", "warning")
            return
        p = self.last_generation_params
        self.lyrics_edit.setPlainText(p['lyrics'])
        self.tags_edit.setText(p['tags'])
        self.output_path_edit.setText(p['output'])
        self.variations_spin.setValue(p['variations'])
        self.max_length_spin.setValue(p['max_len'])
        self.topk_spin.setValue(p['topk'])
        self.temperature_spin.setValue(p['temp'])
        self.cfg_scale_spin.setValue(p['cfg'])
        self.format_combo.setCurrentText(p['format'])
        self.mula_device_combo.setCurrentText(p['mula_device'])
        self.codec_device_combo.setCurrentText(p['codec_device'])
        self.mula_dtype_combo.setCurrentText(p['mula_dtype'])
        self.codec_dtype_combo.setCurrentText(p['codec_dtype'])
        self.start_generation()

    def apply_template(self, template_name: str):
        if template_name == "Select a template..." or template_name not in SONG_TEMPLATES:
            return
        reply = QMessageBox.question(self, "Apply Template", 
            f"Apply '{template_name}' template? This will replace current lyrics and tags.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            tpl = SONG_TEMPLATES[template_name]
            self.lyrics_edit.setPlainText(tpl['lyrics'])
            self.tags_edit.setText(tpl['tags'])
            self.log_console(f"Applied template: {template_name}\n", "success")

    # --- PROJECT MANAGEMENT ---
    # -------------------------------------------------------------------------
    def new_project(self):
        if self.is_modified:
            reply = QMessageBox.question(self, "New Project", "Discard unsaved changes?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        self.lyrics_edit.clear()
        self.tags_edit.clear()
        self.output_path_edit.setText(DEFAULT_OUTPUT_PATH)
        self.current_project_path = None
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - Untitled")
        self._clear_modified()

    def open_project(self):
        f, _ = QFileDialog.getOpenFileName(self, "Open Project", "", f"HeartMuLa Projects (*{PROJECT_FILE_EXT});;All Files (*.*)")
        if f:
            self._load_project_file(f)

    def _load_project_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.lyrics_edit.setPlainText(data.get('lyrics', ''))
            self.tags_edit.setText(data.get('tags', ''))
            self.output_path_edit.setText(data.get('output_path', DEFAULT_OUTPUT_PATH))
            self.model_path_edit.setText(data.get('model_path', DEFAULT_MODEL_PATH))
            self.version_combo.setCurrentText(data.get('version', '3B'))
            self.variations_spin.setValue(data.get('variations', 1))
            self.max_length_spin.setValue(data.get('max_len', DEFAULT_MAX_LENGTH_MS))
            self.topk_spin.setValue(data.get('topk', 50))
            self.temperature_spin.setValue(data.get('temp', 1.0))
            self.cfg_scale_spin.setValue(data.get('cfg', 1.5))
            self.format_combo.setCurrentText(data.get('format', 'mp3'))
            self.mula_device_combo.setCurrentText(data.get('mula_device', 'cuda:0'))
            self.codec_device_combo.setCurrentText(data.get('codec_device', 'cuda:0'))
            self.mula_dtype_combo.setCurrentText(data.get('mula_dtype', 'bfloat16'))
            self.codec_dtype_combo.setCurrentText(data.get('codec_dtype', 'float32'))
            
            self.current_project_path = path
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - {os.path.basename(path)}")
            self._clear_modified()
            
            # Add to recent
            if path in self.recent_projects:
                self.recent_projects.remove(path)
            self.recent_projects.insert(0, path)
            self.recent_projects = self.recent_projects[:10]
            self.update_recent_menu()
            self.save_app_state()
            
            self.log_console(f"Project loaded: {path}\n", "success")
        except Exception as e:
            self.log_console(f"Failed to load project: {e}\n", "error")

    def save_project(self, save_as: bool = False):
        if not self.current_project_path or save_as:
            f, _ = QFileDialog.getSaveFileName(self, "Save Project", "", f"HeartMuLa Projects (*{PROJECT_FILE_EXT})")
            if not f:
                return
            if not f.endswith(PROJECT_FILE_EXT):
                f += PROJECT_FILE_EXT
            self.current_project_path = f
        
        data = {
            'lyrics': self.lyrics_edit.toPlainText(),
            'tags': self.tags_edit.text(),
            'output_path': self.output_path_edit.text(),
            'model_path': self.model_path_edit.text(),
            'version': self.version_combo.currentText(),
            'variations': self.variations_spin.value(),
            'max_len': self.max_length_spin.value(),
            'topk': self.topk_spin.value(),
            'temp': self.temperature_spin.value(),
            'cfg': self.cfg_scale_spin.value(),
            'format': self.format_combo.currentText(),
            'mula_device': self.mula_device_combo.currentText(),
            'codec_device': self.codec_device_combo.currentText(),
            'mula_dtype': self.mula_dtype_combo.currentText(),
            'codec_dtype': self.codec_dtype_combo.currentText(),
        }
        try:
            with open(self.current_project_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - {os.path.basename(self.current_project_path)}")
            self._clear_modified()
            
            if self.current_project_path in self.recent_projects:
                self.recent_projects.remove(self.current_project_path)
            self.recent_projects.insert(0, self.current_project_path)
            self.recent_projects = self.recent_projects[:10]
            self.update_recent_menu()
            self.save_app_state()
            
            self.log_console(f"Project saved: {self.current_project_path}\n", "success")
        except Exception as e:
            self.log_console(f"Failed to save: {e}\n", "error")

    def update_recent_menu(self):
        self.recent_menu.clear()
        if not self.recent_projects:
            self.recent_menu.addAction("(No recent projects)").setEnabled(False)
            return
        for path in self.recent_projects:
            action = QAction(os.path.basename(path), self)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self._load_project_file(p))
            self.recent_menu.addAction(action)
        self.recent_menu.addSeparator()
        clear_action = QAction("Clear Recent List", self)
        clear_action.triggered.connect(self._clear_recent)
        self.recent_menu.addAction(clear_action)

    def _clear_recent(self):
        self.recent_projects.clear()
        self.update_recent_menu()
        self.save_app_state()

    # --- DRAFT & STATE ---
    # -------------------------------------------------------------------------
    def load_draft(self):
        if os.path.exists(DRAFT_FILE):
            try:
                with open(DRAFT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.lyrics_edit.setPlainText(data.get('lyrics', ''))
                self.tags_edit.setText(data.get('tags', ''))
                self.output_path_edit.setText(data.get('output_path', DEFAULT_OUTPUT_PATH))
                self.model_path_edit.setText(data.get('model_path', DEFAULT_MODEL_PATH))
                self.version_combo.setCurrentText(data.get('version', '3B'))
                self.mula_device_combo.setCurrentText(data.get('mula_device', 'cuda:0'))
                self.codec_device_combo.setCurrentText(data.get('codec_device', 'cuda:0'))
                self.mula_dtype_combo.setCurrentText(data.get('mula_dtype', 'bfloat16'))
                self.codec_dtype_combo.setCurrentText(data.get('codec_dtype', 'float32'))
                self.lazy_load_check.setChecked(data.get('lazy_load', True))
                self.variations_spin.setValue(data.get('variations', 1))
                self.max_length_spin.setValue(data.get('max_len', DEFAULT_MAX_LENGTH_MS))
                self.topk_spin.setValue(data.get('topk', 50))
                self.temperature_spin.setValue(data.get('temp', 1.0))
                self.cfg_scale_spin.setValue(data.get('cfg', 1.5))
                self.format_combo.setCurrentText(data.get('format', 'mp3'))
                self.log_console("Draft restored.\n", "info")
            except:
                pass
        self._clear_modified()

    def save_draft(self):
        data = {
            'lyrics': self.lyrics_edit.toPlainText(),
            'tags': self.tags_edit.text(),
            'output_path': self.output_path_edit.text(),
            'model_path': self.model_path_edit.text(),
            'version': self.version_combo.currentText(),
            'mula_device': self.mula_device_combo.currentText(),
            'codec_device': self.codec_device_combo.currentText(),
            'mula_dtype': self.mula_dtype_combo.currentText(),
            'codec_dtype': self.codec_dtype_combo.currentText(),
            'lazy_load': self.lazy_load_check.isChecked(),
            'variations': self.variations_spin.value(),
            'max_len': self.max_length_spin.value(),
            'topk': self.topk_spin.value(),
            'temp': self.temperature_spin.value(),
            'cfg': self.cfg_scale_spin.value(),
            'format': self.format_combo.currentText(),
        }
        try:
            with open(DRAFT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except:
            pass

    def load_app_state(self):
        # History directory
        hist_dir = self.settings.value("history_dir", "")
        if hist_dir:
            self.history_dir = Path(hist_dir)
            self.history_dir.mkdir(exist_ok=True)
        
        # Recent projects
        self.recent_projects = list(self.settings.value("recent_projects", []) or [])
        
        # Favorites
        self.favorite_tags = list(self.settings.value("favorite_tags", []) or [])
        
        # Tray setting
        if hasattr(self, 'always_tray_check'):
            self.always_tray_check.setChecked(self.settings.value("minimize_to_tray", True, type=bool))

    def save_app_state(self):
        self.settings.setValue("history_dir", str(self.history_dir))
        self.settings.setValue("recent_projects", self.recent_projects)
        self.settings.setValue("favorite_tags", self.favorite_tags)
        if hasattr(self, 'always_tray_check'):
            self.settings.setValue("minimize_to_tray", self.always_tray_check.isChecked())

    def restore_window_state(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(QByteArray(geometry))
        state = self.settings.value("window_state")
        if state:
            self.restoreState(QByteArray(state))

    def load_queue(self):
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    items = json.load(f)
                for item_data in items:
                    item = QueueItem(**item_data)
                    self.queue_items.append(item)
                    self.queue_list.addItem(f"{item.label}: {item.tags[:40]}...")
                self.update_queue_label()
            except:
                pass

    def save_queue(self):
        try:
            items = [asdict(item) for item in self.queue_items]
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
        except:
            pass

    # --- TRAY & SHORTCUTS ---
    # -------------------------------------------------------------------------
    def setup_tray_icon(self):
        if not HAS_TRAY:
            return
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.tray_icon.setToolTip(APP_NAME)
        
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self.show_normal)
        tray_menu.addSeparator()
        play_action = tray_menu.addAction("▶ Play/Pause")
        play_action.triggered.connect(self.toggle_play)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_normal()

    def show_normal(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def setup_shortcuts(self):
        # Tab switching
        for i in range(6):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self.tabs.setCurrentIndex(idx))
        
        # Other shortcuts
        QShortcut(QKeySequence("Ctrl+Enter"), self, self.start_generation)
        QShortcut(QKeySequence("Ctrl+R"), self, self.regenerate_last)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.add_to_queue)
        QShortcut(QKeySequence("Space"), self, self.toggle_play)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, lambda: self.save_project(save_as=True))

    # --- DRAG & DROP ---
    # -------------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if path.lower().endswith(('.mp3', '.wav', '.flac', '.ogg')):
                self.trans_audio_edit.setText(path)
                self.tabs.setCurrentIndex(1)
            elif path.lower().endswith('.txt'):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.lyrics_edit.setPlainText(f.read())
                    self.tabs.setCurrentIndex(0)
                except:
                    pass
            elif path.lower().endswith(PROJECT_FILE_EXT):
                self._load_project_file(path)

    # --- THEME ---
    # -------------------------------------------------------------------------
    def apply_dark_theme(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {COLOR_BG}; }}
            QWidget {{ background-color: {COLOR_BG}; color: #e0e0e0; }}
            QGroupBox {{ 
                background-color: {COLOR_PANEL}; 
                border: 1px solid {COLOR_BORDER}; 
                border-radius: 6px; 
                margin-top: 12px; 
                padding-top: 8px;
                font-weight: bold;
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px;
                color: {COLOR_ACCENT};
            }}
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: #2a2a3e;
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 4px;
                color: #e0e0e0;
            }}
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 1px solid {COLOR_ACCENT};
            }}
            QPushButton {{
                background-color: #3a3a5c;
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 6px 12px;
                color: #e0e0e0;
            }}
            QPushButton:hover {{
                background-color: #4a4a6c;
                border: 1px solid {COLOR_ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {COLOR_ACCENT};
            }}
            QPushButton:disabled {{
                background-color: #2a2a3e;
                color: #666;
            }}
            QListWidget, QTreeWidget {{
                background-color: #2a2a3e;
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                color: #e0e0e0;
            }}
            QListWidget::item:selected, QTreeWidget::item:selected {{
                background-color: {COLOR_ACCENT};
            }}
            QTabWidget::pane {{ 
                border: 1px solid {COLOR_BORDER}; 
                background-color: {COLOR_BG};
            }}
            QTabBar::tab {{ 
                background-color: {COLOR_PANEL}; 
                color: #aaa; 
                padding: 8px 16px; 
                border: 1px solid {COLOR_BORDER};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{ 
                background-color: {COLOR_BG}; 
                color: #fff;
                border-bottom: 2px solid {COLOR_ACCENT};
            }}
            QTabBar::tab:hover {{
                background-color: #3a3a5c;
                color: #fff;
            }}
            QScrollBar:vertical {{
                background: {COLOR_PANEL};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: #4a4a6c;
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLOR_ACCENT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QSlider::groove:horizontal {{
                background: {COLOR_PANEL};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {COLOR_ACCENT};
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #64b5f6;
            }}
            QMenu {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_BORDER};
                color: #e0e0e0;
            }}
            QMenu::item:selected {{
                background-color: {COLOR_ACCENT};
            }}
            QStatusBar {{
                background-color: {COLOR_PANEL};
                border-top: 1px solid {COLOR_BORDER};
            }}
            QMenuBar {{
                background-color: {COLOR_PANEL};
                border-bottom: 1px solid {COLOR_BORDER};
            }}
            QMenuBar::item:selected {{
                background-color: {COLOR_ACCENT};
            }}
        """)

    # --- CLOSE EVENT ---
    # -------------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        if (self.gen_thread and self.gen_thread.isRunning()) or (self.trans_thread and self.trans_thread.isRunning()):
            reply = QMessageBox.question(self, "Process in Progress", 
                "A process is still running. Stop and exit?", 
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
        
        if self.is_modified:
            reply = QMessageBox.question(self, "Unsaved Changes", 
                "Save changes before closing?", 
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.Yes:
                self.save_project()
        
        self.save_app_state()
        self.save_draft()
        self.save_queue()
        self.settings.setValue("geometry", self.saveGeometry().data())
        self.settings.setValue("window_state", self.saveState().data())
        
        # Clean temp files only if no process is running
        if not (self.gen_thread and self.gen_thread.isRunning()):
            self.cleanup_temp_files()
        
        event.accept()


# ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setApplicationVersion(APP_VERSION)
    
    try:
        window = HeartMuLaStudio()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"CRITICAL ERROR DURING STARTUP: {e}")
        traceback.print_exc()
        sys.exit(1)