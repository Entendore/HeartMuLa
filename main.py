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
    QScrollArea, QToolButton, QGridLayout, QSpacerItem, QTimeEdit, QDialog, 
    QDockWidget, QDialogButtonBox
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
APP_VERSION = "2.5.0"

DEFAULT_MODEL_PATH = "E:/cacheAI"
DEFAULT_OUTPUT_PATH = "./output.mp3"
DEFAULT_MAX_LENGTH_MS = 240000

CONFIG_FILE = "config.json"
DRAFT_FILE = "draft.json"
TAGS_DB_FILE = "tags_db.json"
QUEUE_FILE = "queue.json"
PRESETS_FILE = "presets.json"
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

PRESET_CATEGORIES = {
    "Lo-Fi & Chill": ["Lo-Fi Chill", "Lo-Fi Hip-Hop", "Study Ambient", "Rainy Day Jazz"],
    "Rock & Metal": ["Epic Rock Anthem", "Soft Rock Ballad", "Heavy Metal", "Grunge Alternative"],
    "Pop & R&B": ["Acoustic Pop", "Synthwave Pop", "R&B Soul", "K-Pop Style"],
    "Electronic & Dance": ["EDM Drop", "House Dance", "Techno Underground", "Synthwave Retro"],
    "Cinematic & Orchestral": ["Cinematic Orchestral", "Cinematic Tension", "Epic Trailer", "Emotional Score"],
    "Hip-Hop & Trap": ["Trap Beat", "Boom Bap Old School", "Drill Dark", "Lo-Fi Rap"],
    "Jazz & Blues": ["Jazz Lounge", "Smooth Jazz", "Slow Blues", "Swing Big Band"],
    "World & Folk": ["Country Acoustic", "Folk Ballad", "Reggae Vibes", "Latin Pop"],
    "Experimental": ["Ambient Soundscape", "Industrial Dark", "Vaporwave", "Folktronica"]
}

SONG_TEMPLATES: Dict[str, Dict[str, str]] = {
    "Lo-Fi Chill": {
        "tags": "lofi, chill, mellow, vinyl_crackle, piano, soft_drums, nostalgic, rainy, study_music, warm, dusty, 80_bpm, minor_key, cozy",
        "lyrics": "[Intro]\n(mellow piano melody with vinyl crackle)\n(soft rain sounds in background)\n\n[Verse 1]\nQuiet morning, coffee steam\nPages turn in gentle dreams\nThe world outside moves way too fast\nBut here inside, the moment lasts\n\n[Chorus]\nTake it slow, let it breathe\nFind the peace you really need\nEvery note just floats away\nOn this lazy lo-fi day\n\n[Verse 2]\nDusty records spinning round\nWarmth in every little sound\nTime slows down when vinyl plays\nBetter than the busiest days\n\n[Outro]\n(fade out with piano)\n(rain continues softly)"
    },
    "Lo-Fi Hip-Hop": {
        "tags": "lofi, hip_hop, boom_bap, jazzy_chords, vinyl_crackle, relaxed, study_beat, mellow_piano, brush_drums, warm_bass, head_nodding, 85_bpm, nostalgic, chillhop",
        "lyrics": "[Intro]\n(jazzy piano chords with vinyl crackle)\n(boom bap drums enter)\n\n[Verse 1]\nLate night writing, candle lit\nEvery verse is legit\nCity lights through window pane\nMusic flowing through my vein\n\n[Hook]\nYeah, just vibe with me\nLo-fi sounds, wild and free\nLet the beat carry you home\nIn this zone, we're never alone\n\n[Verse 2]\nSample flips and jazz progressions\nLife lessons in each session\nMPC pads, fingers drumming\nHeart and soul keep on coming\n\n[Outro]\n(beat fades with crackle)\n(piano resolves)"
    },
    "Study Ambient": {
        "tags": "ambient, study, atmospheric, ethereal, minimal, soft_pads, gentle_piano, no_drums, relaxing, focus, calm, peaceful, drone, reverb_heavy, spacious",
        "lyrics": "[Intro]\n(soft atmospheric pad)\n(gentle piano notes echoing)\n\n[Development]\n(layered ambient textures)\n(minimal melody emerging)\n\n[Climax]\n(warm swell of sound)\n(harmonies blending together)\n\n[Resolution]\n(sounds slowly fading)\n(silence returns)"
    },
    "Rainy Day Jazz": {
        "tags": "jazz, rainy, smooth, saxophone, piano, brush_drums, upright_bass, cozy, melancholic, warm, intimate, late_night, 70_bpm, minor_key, sophisticated",
        "lyrics": "[Intro]\n(saxophone melody over soft piano)\n(brush drums and upright bass)\n\n[Verse 1]\nRaindrops dance on window glass\nEchoes of a love that passed\nSaxophone cries a lonely tune\nUnderneath the silver moon\n\n[Chorus]\nEvery drop a memory\nFalling soft as melody\nJazz and rain, they blend as one\nUntil the night is done\n\n[Sax Solo]\n(expressive saxophone improvisation)\n\n[Outro]\n(rain continues, music fades)\n(final sax note lingers)"
    },
    "Epic Rock Anthem": {
        "tags": "rock, epic, electric_guitar, powerful_drums, anthemic, energetic, distorted, male_vocal, stadium_rock, soaring_chorus, guitar_solos, 140_bpm, major_key, powerful, triumphant",
        "lyrics": "[Intro]\n(powerful guitar riff with drums)\n(anthemic build-up)\n\n[Verse 1]\nStanding at the edge of time\nEvery mountain I will climb\nThunder in my veins tonight\nReady for the ultimate fight\n\n[Pre-Chorus]\nFeel the power, hear the call\nWe will never ever fall\n\n[Chorus]\nWe are the fire, we are the flame\nNothing will ever be the same\nRaise your voices to the sky\nWe were born to fly!\n\n[Verse 2]\nThrough the storm and through the rain\nWe will break every chain\nTogether we are unstoppable\nOur spirit is unbreakable\n\n[Guitar Solo]\n(epic soaring guitar solo)\n\n[Bridge]\nWhen the darkness closes in\nThat's when our light begins\n\n[Final Chorus]\nWe are the fire, we are the flame\nNothing will ever be the same\nRaise your voices to the sky\nWe were born to fly!\n\n[Outro]\n(big finish with all instruments)\n(feedback and cymbal crash)"
    },
    "Soft Rock Ballad": {
        "tags": "soft_rock, ballad, emotional, clean_guitar, warm_piano, gentle_drums, male_vocal, heartfelt, love_song, 75_bpm, major_key, tender, romantic, melodic",
        "lyrics": "[Intro]\n(clean guitar fingerpicking)\n(soft piano joins)\n\n[Verse 1]\nSunlight through the curtain falls\nI hear your voice, I hear your calls\nEvery moment that we share\nShows me how much I care\n\n[Chorus]\nYou're the song I want to sing\nYou're the joy that you bring\nIn your eyes I see forever\nWith you, nothing could be better\n\n[Verse 2]\nWalking hand in hand through town\nNever want to let you down\nEvery laugh, every tear\nMakes it perfectly clear\n\n[Guitar Solo]\n(melodic clean guitar solo)\n\n[Chorus]\nYou're the song I want to sing\nYou're the joy that you bring\nIn your eyes I see forever\nWith you, nothing could be better\n\n[Outro]\n(gentle fade with piano)\n(soft guitar arpeggios)"
    },
    "Heavy Metal": {
        "tags": "metal, heavy, distorted_guitar, double_kick_drums, aggressive, powerful, screaming_vocals, dark, intense, 180_bpm, minor_key, riff_based, headbanging, epic, aggressive",
        "lyrics": "[Intro]\n(heavy distorted riff)\n(double kick drums blast)\n\n[Verse 1]\nForged in fire, born in flames\nNo one here remembers names\nDarkness falls, the earth will shake\nEvery bond we will break\n\n[Pre-Chorus]\nFeel the fury, feel the might\nWe bring darkness to the light\n\n[Chorus]\nRaging storm, endless war\nWhat we fight for, nothing more\nMetal hearts, iron will\nBlood and steel, we will kill\n\n[Verse 2]\nThunder cracks the sky above\nFueled by anger, fueled by love\nStanding tall against the tide\nNowhere left for fear to hide\n\n[Guitar Solo]\n(shredding guitar solo)\n(tapping and sweep picking)\n\n[Bridge]\n(slow heavy breakdown)\n(brutal vocals)\n\n[Final Chorus]\nRaging storm, endless war\nWhat we fight for, nothing more\nMetal hearts, iron will\nBlood and steel, we will kill\n\n[Outro]\n(riff resolves)\n(feedback and drum fill)"
    },
    "Grunge Alternative": {
        "tags": "grunge, alternative_rock, distorted_guitar, raw, angst, 90s, male_vocal, gritty, dark, heavy_bass, 120_bpm, minor_key, dissonant, emotional, seattle_sound",
        "lyrics": "[Intro]\n(dirty guitar riff with fuzz)\n(heavy bass enters)\n\n[Verse 1]\nBroken mirrors, shattered dreams\nNothing's ever what it seems\nWash away the yesterday\nFind another way to pay\n\n[Chorus]\nI don't care anymore\nLock the door, close the door\nFeel the noise, feel the pain\nWash it down like acid rain\n\n[Verse 2]\nPlastic smiles, fake concern\nWatch the twisted river turn\nEverything I thought I knew\nDoesn't matter, nothing's true\n\n[Guitar Solo]\n(raw, feedback-heavy solo)\n\n[Outro]\n(riff repeats and fades)\n(distorted feedback)"
    },
    "Acoustic Pop": {
        "tags": "pop, acoustic_guitar, warm, melodic, male_vocal, clean, heartfelt, soft, singer_songwriter, 100_bpm, major_key, sweet, uplifting, fingerpicking",
        "lyrics": "[Intro]\n(acoustic guitar fingerpicking)\n\n[Verse 1]\nMorning light upon your face\nEvery moment I embrace\nSimple things mean everything\nLike the joy that you bring\n\n[Chorus]\nYou make my heart sing\nYou make my soul take wing\nWith you I'm complete\nYou make my life so sweet\n\n[Verse 2]\nWalking down the sunny street\nEvery person that we meet\nSees the love we share today\nIn our own special way\n\n[Bridge]\nNo need for fancy things\nJust the joy that loving brings\n\n[Chorus]\nYou make my heart sing\nYou make my soul take wing\nWith you I'm complete\nYou make my life so sweet\n\n[Outro]\n(soft guitar fade)\n(warm resolution)"
    },
    "Synthwave Pop": {
        "tags": "synthwave, pop, retro, 80s, analog_synths, drum_machine, neon, nostalgic, melodic, female_vocal, dreamy, 110_bpm, major_key, shimmering, atmospheric",
        "lyrics": "[Intro]\n(analog synth pad with arpeggios)\n(drum machine beat)\n\n[Verse 1]\nNeon lights paint the night\nCity glowing, oh so bright\nDriving down the empty street\nWhere the ocean and city meet\n\n[Chorus]\nWe are living in a dream\nNothing's ever what it seems\nSynthwave hearts beat as one\nDancing till the night is done\n\n[Verse 2]\nCassette tapes and VHS\nMemories we can't suppress\nEvery song a time machine\nTo a world we've never seen\n\n[Synth Solo]\n(shimmering analog synth solo)\n\n[Outro]\n(synth pad fades)\n(drum machine ends)"
    },
    "R&B Soul": {
        "tags": "rnb, soul, smooth, electric_piano, groovy_bass, smooth_drums, female_vocal, emotional, warm, 85_bpm, minor_key, sultry, sophisticated, neo_soul",
        "lyrics": "[Intro]\n(rhodes electric piano)\n(groovy bass line enters)\n\n[Verse 1]\nLate at night when stars align\nI can't get you off my mind\nEvery word you say to me\nOpens doors I've never seen\n\n[Chorus]\nYour love is like a melody\nPlaying soft and sweet for me\nSoul deep, running through my veins\nWashing away all my pains\n\n[Verse 2]\nSmooth like jazz on a summer night\nEverything just feels so right\nYour touch, your smile, your gentle way\nMakes me want to stay\n\n[Bridge]\n(oohs and aahs)\n(harmonies build)\n\n[Outro]\n(rhodes fade)\n(bass groove continues)"
    },
    "K-Pop Style": {
        "tags": "kpop, pop, electronic, synth, catchy, upbeat, female_vocal, harmonies, dance, energetic, 128_bpm, major_key, polished, modern_production, layered_vocals",
        "lyrics": "[Intro]\n(bright synth intro)\n(upbeat dance beat)\n\n[Verse 1]\nEvery step I take with you\nMakes my heart feel brand new\nColor my world with your light\nEverything feels so right\n\n[Pre-Chorus]\nBuilding up to something great\nCan't afford to hesitate\n\n[Chorus]\nShine shine shine, we're glowing bright\nEvery day and every night\nDance with me under the stars\nThis moment is truly ours\n\n[Verse 2]\nLaughter echoes in the air\nStyle and flair beyond compare\nWe're the trend that never ends\nWith our music and our friends\n\n[Dance Break]\n(instrumental electronic section)\n\n[Final Chorus]\nShine shine shine, we're glowing bright\nEvery day and every night\nDance with me under the stars\nThis moment is truly ours\n\n[Outro]\n(synth flourishes)\n(vocal runs fade)"
    },
    "EDM Drop": {
        "tags": "edm, electronic, synth, 808, energetic, festival, drop, buildup, dance, uptempo, 128_bpm, major_key, bass_heavy, sidechain, saw_waves, big_room",
        "lyrics": "[Intro]\n(atmospheric pad)\n(soft synth melody)\n\n[Buildup]\nRising energy, feel the heat\nMove your body to the beat\nHigher higher, we ascend\nThis night will never end\n\n[Drop]\n(heavy bass drop)\n(massive synth lead)\n\n[Verse]\nLights are flashing all around\nFeel the bass shake the ground\nHands up high, touch the sky\nWe were born to fly\n\n[Buildup]\nHere we go again, let's rise\nMusic in our eyes\n\n[Drop]\n(even bigger bass drop)\n(euphoric synth melody)\n\n[Outro]\n(music fades slowly)\n(pad lingers)"
    },
    "House Dance": {
        "tags": "house, dance, electronic, four_on_the_floor, funky_bass, synth_stabs, soulful_vocals, groovy, 124_bpm, major_key, deep_house, dancefloor, uplifting",
        "lyrics": "[Intro]\n(four-on-the-floor kick drum)\n(funky bass line)\n\n[Verse 1]\nFeel the rhythm in your soul\nLet the music take control\nHouse music sets you free\nDance with me, just you and me\n\n[Chorus]\nMove your body to the groove\nNothing left for us to prove\nHouse music all night long\nThis is where we belong\n\n[Verse 2]\nBass is thumping through the floor\nEvery heartbeat asks for more\nSoulful voices, soaring high\nWe can touch the sky\n\n[Instrumental Break]\n(synth stabs and vocal samples)\n\n[Outro]\n(beat continues)\n(fade with vocal echo)"
    },
    "Techno Underground": {
        "tags": "techno, underground, dark, minimal, industrial, repetitive, driving_beat, synth_patterns, 130_bpm, minor_key, raw, warehouse, hypnotic, electronic",
        "lyrics": "[Intro]\n(driving kick drum)\n(minimal synth pattern)\n\n[Section 1]\n(percussive elements build)\n(hypnotic synth loop)\n\n[Section 2]\n(darker synth enters)\n(intensity builds)\n\n[Section 3]\n(full arrangement)\n(driving and relentless)\n\n[Outro]\n(elements stripped away)\n(kick drum fades)"
    },
    "Synthwave Retro": {
        "tags": "synthwave, retro, 80s, analog_synths, drum_machine, neon, nostalgic, instrumental, atmospheric, 100_bpm, minor_key, cinematic, driving, arpeggiated",
        "lyrics": "[Intro]\n(sweeping synth pad)\n(arpeggiated bass line)\n\n[Verse]\n(lead synth melody)\n(drum machine pattern)\n\n[Chorus]\n(soaring synth lead)\n(harmonic layers build)\n\n[Synth Solo]\n(expressive analog synth solo)\n\n[Outro]\n(arpeggios slow down)\n(pad fades to silence)"
    },
    "Cinematic Orchestral": {
        "tags": "cinematic, orchestral, strings, epic, dramatic, choir, emotional, film_score, powerful, brass, timpani, 90_bpm, minor_to_major, sweeping, grand",
        "lyrics": "[Intro]\n(soft string section)\n(piano melody)\n\n[Buildup]\n(adding woodwinds)\n(timpani enters)\n\n[First Theme]\n(full string section)\n(French horns enter)\n\n[Climax]\n(full orchestra)\n(choir joins)\n(brass fanfare)\n\n[Resolution]\n(strings soften)\n(piano returns)\n(music fades gently)"
    },
    "Cinematic Tension": {
        "tags": "cinematic, tension, dark, suspenseful, strings, percussion, drone, minor_key, atmospheric, thriller, building, ominous, 75_bpm, dissonant, dramatic",
        "lyrics": "[Intro]\n(low drone)\n(soft dissonant strings)\n\n[Tension Build]\n(percussive hits)\n(strings rise in pitch)\n\n[Peak Tension]\n(full orchestra dissonance)\n(timpani rolls)\n(brass stabs)\n\n[Release]\n(sudden silence)\n(solo cello)\n\n[Outro]\n(drone returns)\n(fades to nothing)"
    },
    "Epic Trailer": {
        "tags": "trailer, epic, cinematic, orchestral, powerful, braams, taiko_drums, choir, dark, heroic, 120_bpm, minor_key, building, climactic, blockbuster",
        "lyrics": "[Intro]\n(deep braam sound)\n(slow taiko drums)\n\n[Buildup]\n(choir enters softly)\n(strings build tension)\n\n[Main Section]\n(full orchestra hits)\n(epic brass melody)\n(massive choir)\n\n[Climax]\n(everything at maximum)\n(cymbal crashes)\n\n[Outro]\n(sudden cut)\n(solo piano note)\n(silence)"
    },
    "Emotional Score": {
        "tags": "cinematic, emotional, piano, strings, tender, sad, beautiful, film_score, solo_violin, touching, 70_bpm, minor_key, melancholic, delicate, moving",
        "lyrics": "[Intro]\n(solo piano)\n(soft string pad)\n\n[Theme A]\n(piano melody develops)\n(cello enters)\n\n[Theme B]\n(violin takes melody)\n(strings swell)\n\n[Climax]\n(full string section)\n(emotional peak)\n\n[Resolution]\n(piano returns alone)\n(music box effect)\n(fade to silence)"
    },
    "Trap Beat": {
        "tags": "trap, hip_hop, 808_bass, hi_hat_rolls, dark, atmospheric, male_vocal, modern, 140_bpm, minor_key, heavy_808, triplet_flows, southern, street",
        "lyrics": "[Intro]\n(atmospheric pad)\n(808 bass hits)\n\n[Verse 1]\nWalking through the city lights\nEvery day another fight\nCame from nothing, now I'm here\nMake it clear, I have no fear\n\n[Hook]\nYeah we trapping every day\nGotta find another way\n808 shaking the ground\nThis is how we get down\n\n[Verse 2]\nHi-hats rolling like a river\nSuccess makes me shiver\nEvery beat tells my story\nTrying to find the glory\n\n[Outro]\n(808 fades)\n(hi-hats slow down)"
    },
    "Boom Bap Old School": {
        "tags": "boom_bap, hip_hop, old_school, 90s, jazzy_sample, hard_drums, vinyl_crackle, male_vocal, raw, authentic, 90_bpm, head_nodding, east_coast, gritty",
        "lyrics": "[Intro]\n(vinyl crackle)\n(jazzy horn sample)\n(hard boom bap drums)\n\n[Verse 1]\nBack in the days when rap was real\nEvery MC had skill to reveal\nBlock parties, cyphers on the street\nEvery verse had to be complete\n\n[Chorus]\nBoom bap, that's the sound\nWhen real hip-hop comes around\nSample loops and breakbeats raw\nThis is what we're fighting for\n\n[Verse 2]\nTurntable scratching, cutting deep\nWhile the MCs hold the crowd in leap\nEvery word a lesson, every rhyme a truth\nThis is hip-hop from its roots\n\n[Outro]\n(beat rides out)\n(sample echoes and fades)"
    },
    "Drill Dark": {
        "tags": "drill, dark, menacing, sliding_808, hi_hat_patterns, minor_key, aggressive, male_vocal, uk_drill, street, 140_bpm, ominous, intense, modern",
        "lyrics": "[Intro]\n(dark piano melody)\n(slide 808 bass)\n(fast hi-hat pattern)\n\n[Verse 1]\nStreets cold, heart colder\nEvery day I'm getting bolder\nNothing handed, everything taken\nNever been the one forsaken\n\n[Chorus]\nDrill music, that's the sound\nWhere the real ones get down\nDark beats, darker rhymes\nLiving through hard times\n\n[Verse 2]\nSlide with the bass, move with the flow\nEveryone watching, they already know\nNo pretending, just real life\nCut through struggle like a knife\n\n[Outro]\n(808 slides down)\n(beat cuts abruptly)"
    },
    "Lo-Fi Rap": {
        "tags": "lofi, rap, chill, jazzy, vinyl_crackle, boom_bap, relaxed, introspective, male_vocal, 80_bpm, warm, nostalgic, mellow, thoughtful",
        "lyrics": "[Intro]\n(warm jazz sample with crackle)\n(soft boom bap drums)\n\n[Verse 1]\nSitting back, watching time pass\nMusic playing from the past\nEvery note a memory\nOf who I used to be\n\n[Hook]\nLo-fi vibes, take it slow\nLet the peaceful feelings flow\nRhymes and beats, perfectly matched\nIn this moment, perfectlyatched\n\n[Verse 2]\nCoffee cup, notebook open\nWords that need to be spoken\nFinding beauty in the simple\nLife doesn't need to be a temple\n\n[Outro]\n(beat fades)\n(sample echoes away)"
    },
    "Jazz Lounge": {
        "tags": "jazz, smooth, saxophone, piano, brush_drums, upright_bass, lounge, sophisticated, swing, warm, 100_bpm, major_key, cool, elegant, late_night",
        "lyrics": "[Intro]\n(piano and upright bass)\n(brush drums enter softly)\n\n[Verse 1]\nSmoke rings rising to the ceiling\nEvery note with feeling\nJazz club magic in the air\nNothing else can compare\n\n[Chorus]\nSmooth and cool, that's our way\nJazz will never fade away\nEvery improv tells a story\nEvery solo brings us glory\n\n[Verse 2]\nSaxophone crying through the night\nEverything feeling just right\nPiano chords, rich and deep\nMemories we'll always keep\n\n[Sax Solo]\n(smooth saxophone improvisation)\n\n[Outro]\n(trade fours between sax and piano)\n(cool ending)"
    },
    "Smooth Jazz": {
        "tags": "smooth_jazz, saxophone, electric_piano, groovy_bass, soft_drums, mellow, romantic, sophisticated, 85_bpm, major_key, warm, polished, evening, elegant",
        "lyrics": "[Intro]\n(rhodes electric piano)\n(groovy bass line)\n(soft drums)\n\n[Verse]\n(saxophone melody enters)\n(smooth and flowing)\n\n[Chorus]\n(sax soars melodically)\n(piano comping underneath)\n\n[Sax Solo]\n(expressive smooth jazz solo)\n\n[Piano Solo]\n(rhodes improvisation)\n\n[Outro]\n(sax returns to melody)\n(gentle fade out)"
    },
    "Slow Blues": {
        "tags": "blues, slow, electric_guitar, harmonica, shuffling_drums, bass, male_vocal, emotional, 12_bar_blues, 70_bpm, minor_key, gritty, soulful, traditional",
        "lyrics": "[Intro]\n(slow guitar lick)\n(harmonica wails)\n(shuffle drums enter)\n\n[Verse 1]\nWoke up this morning, blues knocking at my door\nWoke up this morning, blues knocking at my door\nFelt like I've been here before\nMy baby don't love me no more\n\n[Verse 2]\nEvery day is just the same\nEvery day is just the same\nPlaying this lonely blues game\nAin't nobody know my name\n\n[Guitar Solo]\n(bending bluesy guitar solo)\n\n[Harmonica Solo]\n(expressive harmonica)\n\n[Outro]\n(guitar lick resolves)\n(slow fade)"
    },
    "Swing Big Band": {
        "tags": "swing, big_band, jazz, horns, brass, upright_bass, swing_drums, energetic, 30s, 40s, 160_bpm, major_key, upbeat, dancing, classic",
        "lyrics": "[Intro]\n(full brass section hit)\n(swing drum pattern)\n(upright bass walking)\n\n[Verse 1]\nCats and kittens gather round\nThe swingingest sound in town\nBrass section blowing hot\nGive it everything you've got\n\n[Chorus]\nJump and jive, swing and sway\nDance the night away\nBig band sound is in the groove\nFeel your body move\n\n[Verse 2]\nTrumpets screaming, trombones sliding\nRhythm section never hiding\nEvery note is pure delight\nSwinging through the night\n\n[Sax Solo]\n(big band sax solo with section backing)\n\n[Trumpet Solo]\n(high energy trumpet)\n\n[Outro]\n(tutti hit)\n(big finish)"
    },
    "Country Acoustic": {
        "tags": "country, acoustic_guitar, fiddle, warm, male_vocal, storytelling, heartfelt, americana, 100_bpm, major_key, rural, simple, nostalgic, front_porch",
        "lyrics": "[Intro]\n(country guitar strumming)\n(fiddle enters)\n\n[Verse 1]\nDirt road winding through the trees\nBrings back sweet memories\nFront porch sitting, watching the sun\nWondering where the time has gone\n\n[Chorus]\nCountry living, simple and true\nNothing finer than this view\nFamily, faith, and friends around\nThis is where my heart is found\n\n[Verse 2]\nMama's cooking in the kitchen\nDaddy fishing, line a-twitching\nSimple life, that's the best\nPut my worries down to rest\n\n[Fiddle Solo]\n(country fiddle breakdown)\n\n[Outro]\n(guitar strums slowly)\n(fiddle fades)"
    },
    "Folk Ballad": {
        "tags": "folk, acoustic, fingerpicking_guitar, gentle, storytelling, male_vocal, warm, intimate, 80_bpm, major_key, traditional, narrative, cozy, fireside",
        "lyrics": "[Intro]\n(fingerpicked acoustic guitar)\n\n[Verse 1]\nTraveling down a dusty road\nCarrying stories, heavy load\nEvery face that I have known\nLives in songs I call my own\n\n[Chorus]\nSing a song for the journey\nEvery mile a memory\nFolk songs carry through the years\nMusic dries the deepest tears\n\n[Verse 2]\nCampfire glowing in the night\nStrumming guitar, feeling right\nVoices joined in harmony\nThis is where I want to be\n\n[Outro]\n(guitar picks final notes)\n(warm resolution)"
    },
    "Reggae Vibes": {
        "tags": "reggae, offbeat_guitar, bass_heavy, drums, organ, male_vocal, positive, island, warm, 80_bpm, major_key, roots, laid_back, irie",
        "lyrics": "[Intro]\n(reggae guitar skank)\n(heavy bass line)\n(organ enters)\n\n[Verse 1]\nSun is shining, feeling fine\nGood vibrations every time\nOne love, one heart, one soul\nMusic makes us whole\n\n[Chorus]\nReggae rhythm, reggae beat\nMove your body, tap your feet\nPositive vibes, positive sound\nLove and peace all around\n\n[Verse 2]\nNo worries here, just irie\nLiving life so wild and free\nIsland breeze, ocean blue\nEverything feels brand new\n\n[Outro]\n(bass groove continues)\n(guitar skank fades)"
    },
    "Latin Pop": {
        "tags": "latin_pop, acoustic_guitar, percussion, warm, danceable, male_vocal, catchy, 105_bpm, major_key, romantic, energetic, tropical, festive",
        "lyrics": "[Intro]\n(acoustic guitar strumming)\n(percussion enters)\n\n[Verse 1]\nBailando bajo la luna\nDancing under the moon\nEvery step brings me closer\nTo a love coming soon\n\n[Chorus]\nMuevete con el ritmo\nMove with the rhythm\nLatin fire burning bright\nDancing through the night\n\n[Verse 2]\nGuitar playing sweet melody\nAs we dance in harmony\nEvery beat tells our story\nFull of love and glory\n\n[Guitar Solo]\n(flamenco-style acoustic solo)\n\n[Outro]\n(percussion continues)\n(guitar strums fade)"
    },
    "Ambient Soundscape": {
        "tags": "ambient, soundscape, atmospheric, drone, ethereal, minimal, evolving, spacious, meditative, no_rhythm, ambient_pads, nature_sounds, peaceful, expansive",
        "lyrics": "[Intro]\n(soft evolving pad)\n(distant nature sounds)\n\n[Development]\n(textures slowly shift)\n(new harmonic layers emerge)\n\n[Climax]\n(full ambient swell)\n(all elements blend)\n\n[Resolution]\n(sounds gradually recede)\n(return to initial pad)\n(fade to silence)"
    },
    "Industrial Dark": {
        "tags": "industrial, dark, metallic, distorted, electronic, aggressive, male_vocal, dark_ambient, 110_bpm, minor_key, harsh, mechanical, intense, bleak",
        "lyrics": "[Intro]\n(metallic clanging)\n(distorted synth bass)\n\n[Verse 1]\nMachines grinding, metal screaming\nNothing's ever as it's seeming\nFactory walls, cold and grey\nAnother day, another day\n\n[Chorus]\nIndustrial wasteland, broken dreams\nNothing here is what it seems\nSteel and concrete, iron will\nStanding still, standing still\n\n[Verse 2]\nSparks flying like dying stars\nBehind these iron bars\nEvery heartbeat mechanical\nLost in the industrial\n\n[Outro]\n(machinery sounds)\n(distortion fades)"
    },
    "Vaporwave": {
        "tags": "vaporwave, retro, 80s, slowed, chopped, dreamy, nostalgic, electronic, synth, 70_bpm, major_key, surreal, muzak, corporate, elevator",
        "lyrics": "[Intro]\n(slowed synth pad)\n(pitched-down vocals echo)\n\n[Section 1]\n(dreamy synth melody)\n(chopped and screwed samples)\n\n[Section 2]\n(elevator muzak style)\n(surreal atmosphere)\n\n[Outro]\n(sounds dissolve)\n(echo fades to nothing)"
    },
    "Folktronica": {
        "tags": "folktronica, folk, electronic, acoustic_guitar, synth_pads, glitchy_beats, warm, melodic, 90_bpm, major_key, organic, digital, hybrid, experimental",
        "lyrics": "[Intro]\n(acoustic guitar fingerpicking)\n(soft synth pad enters)\n(glitchy electronic beats)\n\n[Verse 1]\nWalking through the digital trees\nFinding peace in what I see\nNature and machine combine\nEvery moment so divine\n\n[Chorus]\nFolk and electronica blend\nAround every sonic bend\nAcoustic heart, electric soul\nTogether making me whole\n\n[Verse 2]\nFingerpicking, glitchy beats\nFinding beauty in the meets\nTechnology and nature's song\nWhere they meet, I belong\n\n[Outro]\n(guitar and synths fade together)\n(soft glitchy ending)"
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
    smart_split: bool = False
    chunk_sec: int = 45


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
# DIALOGS
# ==============================================================================
class FindReplaceDialog(QDialog):
    """A non-modal dialog for finding and replacing text in the lyrics editor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace")
        self.setModal(False)
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        form_layout.addRow("Find:", self.find_edit)
        form_layout.addRow("Replace with:", self.replace_edit)
        layout.addLayout(form_layout)
        
        btn_layout = QHBoxLayout()
        self.find_btn = QPushButton("Find Next")
        self.replace_btn = QPushButton("Replace One")
        self.replace_all_btn = QPushButton("Replace All")
        self.close_btn = QPushButton("Close")
        
        btn_layout.addWidget(self.find_btn)
        btn_layout.addWidget(self.replace_btn)
        btn_layout.addWidget(self.replace_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        self.close_btn.clicked.connect(self.close)


class TapTempoDialog(QDialog):
    """A dialog to calculate BPM and delay times by tapping."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tap Tempo & Calculator")
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)
        
        self.tap_times = []
        
        self.bpm_label = QLabel("BPM: ---")
        self.bpm_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
        self.bpm_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.bpm_label)
        
        self.tap_btn = QPushButton("TAP")
        self.tap_btn.setMinimumHeight(80)
        self.tap_btn.setStyleSheet("font-size: 20px; font-weight: bold; background-color: #4CAF50; color: white; border-radius: 8px;")
        self.tap_btn.pressed.connect(self.record_tap)
        layout.addWidget(self.tap_btn)
        
        layout.addSpacing(20)
        layout.addWidget(QLabel("Delay Times (ms):"))
        
        self.delay_labels = {}
        for note in ["1/1", "1/2", "1/4", "1/8", "1/16", "1/32"]:
            lbl = QLabel(f"{note}: --- ms")
            lbl.setStyleSheet("font-family: Consolas; font-size: 14px;")
            self.delay_labels[note] = lbl
            layout.addWidget(lbl)
            
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self.reset)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        
    def record_tap(self):
        now = time.time()
        self.tap_times.append(now)
        
        # Keep only the last 8 taps
        if len(self.tap_times) > 8:
            self.tap_times.pop(0)
            
        if len(self.tap_times) >= 2:
            # Calculate average interval
            intervals = [self.tap_times[i] - self.tap_times[i-1] for i in range(1, len(self.tap_times))]
            avg_interval = sum(intervals) / len(intervals)
            
            if avg_interval > 0:
                bpm = 60.0 / avg_interval
                self.bpm_label.setText(f"BPM: {bpm:.1f}")
                
                # Calculate delays
                quarter_note_ms = (60000.0 / bpm)
                self.delay_labels["1/1"].setText(f"1/1: {quarter_note_ms * 4:.2f} ms")
                self.delay_labels["1/2"].setText(f"1/2: {quarter_note_ms * 2:.2f} ms")
                self.delay_labels["1/4"].setText(f"1/4: {quarter_note_ms:.2f} ms")
                self.delay_labels["1/8"].setText(f"1/8: {quarter_note_ms / 2:.2f} ms")
                self.delay_labels["1/16"].setText(f"1/16: {quarter_note_ms / 4:.2f} ms")
                self.delay_labels["1/32"].setText(f"1/32: {quarter_note_ms / 8:.2f} ms")
                
    def reset(self):
        self.tap_times.clear()
        self.bpm_label.setText("BPM: ---")
        for lbl in self.delay_labels.values():
            lbl.setText(lbl.text().split(":")[0] + ": --- ms")


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


class SplitGenerationWorker(QObject):
    """Handles VRAM-friendly generation by splitting lyrics into chunks and stitching audio."""
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)
    
    def __init__(self, model_path, version, lyrics_chunk_paths, tags_path, save_path, 
                 chunk_max_len, topk, temp, cfg, mula_device, codec_device, mula_dtype, codec_dtype, lazy_load):
        super().__init__()
        self.model_path = model_path
        self.version = version
        self.lyrics_chunk_paths = lyrics_chunk_paths
        self.tags_path = tags_path
        self.save_path = save_path
        self.chunk_max_len = chunk_max_len
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
            print("Pipeline loaded.")
            
            temp_audio_files = []
            temp_dir = os.path.dirname(self.lyrics_chunk_paths[0])
            
            for i, chunk_path in enumerate(self.lyrics_chunk_paths):
                print(f"\n--- Generating Chunk {i+1}/{len(self.lyrics_chunk_paths)} ---")
                temp_wav = os.path.join(temp_dir, f"chunk_audio_{i}.wav")
                
                with torch.no_grad():
                    pipe(
                        {
                            "lyrics": chunk_path,
                            "tags": self.tags_path,
                        },
                        max_audio_length_ms=self.chunk_max_len,
                        save_path=temp_wav,
                        topk=self.topk,
                        temperature=self.temp,
                        cfg_scale=self.cfg,
                    )
                temp_audio_files.append(temp_wav)
                print(f"Chunk {i+1} generated successfully.")
                
                # Clear VRAM between chunks
                try:
                    torch.cuda.empty_cache()
                except:
                    pass
            
            print("\nStitching audio chunks together...")
            try:
                from pydub import AudioSegment
            except ImportError:
                raise Exception("pydub is required for stitching audio but is not installed.")
            
            combined = AudioSegment.empty()
            for f in temp_audio_files:
                audio_seg = AudioSegment.from_wav(f)
                combined += audio_seg
            
            ext = os.path.splitext(self.save_path)[1][1:].lower()
            if not ext:
                ext = "wav"
                
            combined.export(self.save_path, format=ext)
            print(f"Stitched audio saved to {self.save_path}")
            
            # Clean up temp audio files
            for f in temp_audio_files:
                try:
                    os.remove(f)
                except:
                    pass
                    
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
        self.chunk_files: List[str] = []
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

        self.custom_presets: Dict[str, Dict[str, str]] = {}

        self.init_ui()
        self.apply_dark_theme()
        self.load_tag_db()
        self.load_custom_presets()
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
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(3)
        self.splitter.setObjectName("mainSplitter")

        left_panel_widget = self.create_config_panel()
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_panel_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setMinimumWidth(320)
        left_scroll.setMaximumWidth(450)

        right_panel = self.create_right_tabs()
        self.splitter.addWidget(left_scroll)
        self.splitter.addWidget(right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        main_layout.addWidget(self.splitter)
        
        self.init_menubar()
        self.init_status_bar()
        self.init_docks()

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

        # Add Progress Bar to Status Bar
        self.gen_progress_bar = QProgressBar()
        self.gen_progress_bar.setRange(0, 1)
        self.gen_progress_bar.setVisible(False)
        self.gen_progress_bar.setTextVisible(False)
        self.gen_progress_bar.setFixedWidth(100)
        self.gen_progress_bar.setFixedHeight(14)
        self.gen_progress_bar.setStyleSheet(f"QProgressBar {{ border: 1px solid {COLOR_BORDER}; border-radius: 4px; background-color: #2a2a3e; }} QProgressBar::chunk {{ background-color: {COLOR_ACCENT}; border-radius: 3px; }}")

        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.gen_progress_bar)
        self.status_bar.addPermanentWidget(self.autosave_label)
        self.status_bar.addPermanentWidget(self.queue_label)
        self.status_bar.addPermanentWidget(self.gen_timer_label)
        self.status_bar.addPermanentWidget(self.vram_label)

        self.gen_timer = QTimer(self)
        self.gen_timer.timeout.connect(self.update_gen_timer)
        self.gen_start_time: float = 0.0

    def init_docks(self):
        # --- Console Dock ---
        self.console_dock = QDockWidget("🖥 Console", self)
        self.console_dock.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.console_dock.setObjectName("consoleDock")
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(0,0,0,0)
        
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
        
        self.console_dock.setWidget(console_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)
        
        # --- Player Dock ---
        self.player_dock = QDockWidget("🎵 Player", self)
        self.player_dock.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.player_dock.setObjectName("playerDock")
        player_widget = QWidget()
        player_layout = QHBoxLayout(player_widget)
        player_layout.setContentsMargins(8, 8, 8, 8)
        
        self.track_label = QLabel("No track loaded.")
        self.track_label.setAlignment(Qt.AlignCenter)
        self.track_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        player_layout.addWidget(self.track_label, 1)
        
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(0,0,0,0)
        
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
        
        self.loop_btn = QPushButton("🔁")
        self.loop_btn.setFixedSize(40, 40)
        self.loop_btn.setCheckable(True)
        self.loop_btn.setToolTip("Loop current track")
        self.loop_btn.setStyleSheet("QPushButton { background-color: #3a3a5c; } QPushButton:checked { background-color: #2196F3; color: white; }")
        self.loop_btn.clicked.connect(self.toggle_loop)
        
        playback_layout.addStretch()
        playback_layout.addWidget(self.prev_btn)
        playback_layout.addWidget(self.play_btn)
        playback_layout.addWidget(self.next_btn)
        playback_layout.addStretch()
        playback_layout.addWidget(self.loop_btn)
        controls_layout.addLayout(playback_layout)
        
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("🔊"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_layout.addWidget(self.volume_slider)
        controls_layout.addLayout(volume_layout)
        
        player_layout.addWidget(controls_container, 2)
        self.player_dock.setWidget(player_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.player_dock)
        
        # Make Player dock narrower than Console dock
        self.resizeDocks([self.player_dock, self.console_dock], [250, 450], Qt.Horizontal)

    def init_menubar(self) -> None:
        menubar = self.menuBar()
        menubar.setStyleSheet(f"QMenuBar {{ background-color: {COLOR_PANEL}; }}")

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

        edit_menu = menubar.addMenu("&Edit")
        clear_lyrics_action = QAction("Clear &Lyrics", self)
        clear_lyrics_action.triggered.connect(lambda: self.lyrics_edit.clear())
        edit_menu.addAction(clear_lyrics_action)
        
        clear_tags_action = QAction("Clear &Tags", self)
        clear_tags_action.triggered.connect(lambda: self.tags_edit.clear())
        edit_menu.addAction(clear_tags_action)
        
        edit_menu.addSeparator()
        
        find_action = QAction("🔍 &Find and Replace", self)
        find_action.setShortcut(QKeySequence("Ctrl+F"))
        find_action.triggered.connect(self.show_find_replace)
        edit_menu.addAction(find_action)
        
        clear_console_action = QAction("Clear &Console", self)
        clear_console_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_console_action.triggered.connect(lambda: self.console_output.clear())
        edit_menu.addAction(clear_console_action)

        view_menu = menubar.addMenu("&View")
        action_toggle_console = QAction("Toggle &Console", self)
        action_toggle_console.setShortcut(QKeySequence("F12"))
        action_toggle_console.triggered.connect(lambda: self.console_dock.setVisible(not self.console_dock.isVisible()))
        view_menu.addAction(action_toggle_console)
        
        action_toggle_player = QAction("Toggle &Player", self)
        action_toggle_player.setShortcut(QKeySequence("F11"))
        action_toggle_player.triggered.connect(lambda: self.player_dock.setVisible(not self.player_dock.isVisible()))
        view_menu.addAction(action_toggle_player)

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

        tools_menu = menubar.addMenu("&Tools")
        tap_tempo_action = QAction("🎼 Tap Tempo & Calculator", self)
        tap_tempo_action.setShortcut(QKeySequence("Ctrl+T"))
        tap_tempo_action.triggered.connect(self.show_tap_tempo)
        tools_menu.addAction(tap_tempo_action)
        
        random_struct_action = QAction("🎲 Generate Random Song Structure", self)
        random_struct_action.triggered.connect(self.generate_random_structure)
        tools_menu.addAction(random_struct_action)

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
            "<tr><td><b>Ctrl+F</b></td><td>Find & Replace</td></tr>"
            "<tr><td><b>Ctrl+T</b></td><td>Tap Tempo tool</td></tr>"
            "<tr><td><b>Ctrl+L</b></td><td>Clear console</td></tr>"
            "<tr><td><b>Ctrl+= / Ctrl+-</b></td><td>Zoom In / Out lyrics</td></tr>"
            "<tr><td><b>Alt+Up / Alt+Down</b></td><td>Move line up/down</td></tr>"
            "<tr><td><b>Ctrl+1..4</b></td><td>Switch tabs</td></tr>"
            "<tr><td><b>F11 / F12</b></td><td>Toggle Player / Console</td></tr>"
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

        gen_group = QGroupBox("Generation Parameters")
        gen_layout = QFormLayout()

        self.variations_spin = QSpinBox()
        self.variations_spin.setRange(1, 20)
        self.variations_spin.setValue(1)
        self.variations_spin.setToolTip("Number of variations to generate")
        gen_layout.addRow("Variations:", self.variations_spin)

        self.max_length_edit = QTimeEdit()
        self.max_length_edit.setDisplayFormat("HH:mm:ss")
        self.max_length_edit.setMinimumTime(QTime(0, 0, 10))   # 10 seconds
        self.max_length_edit.setMaximumTime(QTime(0, 10, 0))   # 10 minutes
        self.max_length_edit.setTime(QTime(0, 0, 0).addMSecs(DEFAULT_MAX_LENGTH_MS))
        self.max_length_edit.setToolTip("Maximum audio length (HH:mm:ss)")
        gen_layout.addRow("Max Length:", self.max_length_edit)

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
        
        self.smart_split_check = QCheckBox("Enable Smart Splitting (VRAM Saver)")
        self.smart_split_check.setToolTip("Splits lyrics into chunks, generates separately, and stitches audio.\nHelps prevent VRAM crashes on long tracks.")
        gen_layout.addRow("Smart Split:", self.smart_split_check)

        self.chunk_sec_spin = QSpinBox()
        self.chunk_sec_spin.setRange(20, 120)
        self.chunk_sec_spin.setValue(45)
        self.chunk_sec_spin.setSuffix(" sec")
        self.chunk_sec_spin.setToolTip("Maximum length per chunk. Lower this if still hitting VRAM limits.")
        gen_layout.addRow("Chunk Size:", self.chunk_sec_spin)
        
        self.save_log_check = QCheckBox("Save full console log with track")
        self.save_log_check.setChecked(True)
        gen_layout.addRow("Debugging:", self.save_log_check)
        
        gen_group.setLayout(gen_layout)
        layout.addWidget(gen_group)

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

        layout.addStretch()
        return container

    def get_max_length_ms(self) -> int:
        """Return the max length from the QTimeEdit in milliseconds."""
        return self.max_length_edit.time().msecsSinceStartOfDay()

    def set_max_length_ms(self, ms: int) -> None:
        """Set the max length QTimeEdit from a millisecond value."""
        ms = max(10000, min(int(ms), 600000))  # clamp to valid range
        self.max_length_edit.setTime(QTime(0, 0, 0).addMSecs(ms))

    def create_right_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"QTabWidget::pane {{ border: 1px solid {COLOR_BORDER}; }}")

        editor_tab = QWidget()
        editor_layout = QVBoxLayout(editor_tab)
        
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Quick Start:"))
        self.template_combo = QComboBox()
        self.refresh_preset_combo()
        self.template_combo.currentTextChanged.connect(self.apply_template)
        template_layout.addWidget(self.template_combo, 1)
        
        btn_save_preset = QPushButton("💾 Save Preset")
        btn_save_preset.setMaximumHeight(28)
        btn_save_preset.setToolTip("Save current lyrics & tags as a reusable preset")
        btn_save_preset.clicked.connect(self.save_current_as_preset)
        template_layout.addWidget(btn_save_preset)
        
        btn_manage_presets = QPushButton("⚙ Manage")
        btn_manage_presets.setMaximumHeight(28)
        btn_manage_presets.setToolTip("Delete, import, or export presets")
        btn_manage_presets.clicked.connect(self.show_preset_manager)
        template_layout.addWidget(btn_manage_presets)
        
        btn_word_count = QPushButton("📊 Stats")
        btn_word_count.clicked.connect(self.show_detailed_stats)
        template_layout.addWidget(btn_word_count)
        
        editor_layout.addLayout(template_layout)

        editor_split = QSplitter(Qt.Horizontal)
        self.editor_split = editor_split
        
        lyrics_container = QWidget()
        lyrics_layout = QVBoxLayout(lyrics_container)

        # Expanded Toolbar Layout
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(4)
        
        self.insert_combo = QComboBox()
        self.insert_combo.addItems([
            "➕ Insert...",
            "[Intro]", "[Verse]", "[Prechorus]", "[Chorus]", 
            "[Bridge]", "[Outro]", "[Instrumental]", "[Drop]",
            "(guitar_solo)", "(drum_fill)", "(fade_out)", "(breakdown)"
        ])
        self.insert_combo.currentIndexChanged.connect(self._on_insert_combo_changed)
        toolbar_layout.addWidget(self.insert_combo)
        
        btn_random_struct = QPushButton("🎲 Structure")
        btn_random_struct.setMaximumHeight(28)
        btn_random_struct.setToolTip("Generate random song structure skeleton")
        btn_random_struct.clicked.connect(self.generate_random_structure)
        toolbar_layout.addWidget(btn_random_struct)
        
        toolbar_layout.addStretch()
        
        btn_move_up = QPushButton("⬆")
        btn_move_up.setFixedWidth(30)
        btn_move_up.setToolTip("Move line up (Alt+Up)")
        btn_move_up.clicked.connect(self.move_line_up)
        toolbar_layout.addWidget(btn_move_up)
        
        btn_move_down = QPushButton("⬇")
        btn_move_down.setFixedWidth(30)
        btn_move_down.setToolTip("Move line down (Alt+Down)")
        btn_move_down.clicked.connect(self.move_line_down)
        toolbar_layout.addWidget(btn_move_down)
        
        btn_format_tags = QPushButton("✨")
        btn_format_tags.setFixedWidth(30)
        btn_format_tags.setToolTip("Format section tags to Title Case")
        btn_format_tags.clicked.connect(self.format_section_tags)
        toolbar_layout.addWidget(btn_format_tags)
        
        btn_capitalize = QPushButton("Aa")
        btn_capitalize.setFixedWidth(30)
        btn_capitalize.setToolTip("Capitalize first letter of each line")
        btn_capitalize.clicked.connect(self.capitalize_lines)
        toolbar_layout.addWidget(btn_capitalize)
        
        btn_cleanup = QPushButton("🧹")
        btn_cleanup.setFixedWidth(30)
        btn_cleanup.setToolTip("Remove excessive empty lines")
        btn_cleanup.clicked.connect(self.format_cleanup_lyrics)
        toolbar_layout.addWidget(btn_cleanup)
        
        btn_find = QPushButton("🔍")
        btn_find.setFixedWidth(30)
        btn_find.setToolTip("Find & Replace (Ctrl+F)")
        btn_find.clicked.connect(self.show_find_replace)
        toolbar_layout.addWidget(btn_find)
        
        btn_zoom_in = QPushButton("➕")
        btn_zoom_in.setFixedWidth(30)
        btn_zoom_in.setToolTip("Zoom In (Ctrl++)")
        btn_zoom_in.clicked.connect(self.zoom_in)
        toolbar_layout.addWidget(btn_zoom_in)
        
        btn_zoom_out = QPushButton("➖")
        btn_zoom_out.setFixedWidth(30)
        btn_zoom_out.setToolTip("Zoom Out (Ctrl+-)")
        btn_zoom_out.clicked.connect(self.zoom_out)
        toolbar_layout.addWidget(btn_zoom_out)
        
        btn_import_lyrics = QPushButton("📁")
        btn_import_lyrics.setFixedWidth(30)
        btn_import_lyrics.setToolTip("Import lyrics from file")
        btn_import_lyrics.clicked.connect(self.import_lyrics)
        toolbar_layout.addWidget(btn_import_lyrics)
        
        btn_clear_lyrics = QPushButton("🗑")
        btn_clear_lyrics.setFixedWidth(30)
        btn_clear_lyrics.setToolTip("Clear lyrics")
        btn_clear_lyrics.clicked.connect(lambda: self.lyrics_edit.clear())
        toolbar_layout.addWidget(btn_clear_lyrics)
        
        lyrics_layout.addLayout(toolbar_layout)

        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setFont(QFont("Consolas", 11))
        self.lyrics_edit.textChanged.connect(self.update_lyrics_stats)
        self.lyrics_edit.textChanged.connect(self._mark_modified)
        self.highlighter = SongStructureHighlighter(self.lyrics_edit.document())
        lyrics_layout.addWidget(self.lyrics_edit)
        
        self.lyrics_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lyrics_edit.customContextMenuRequested.connect(self.show_lyrics_context_menu)

        self.lyrics_stats_label = QLabel("Words: 0 | Lines: 0 | Syllables: 0 | Est. Time: 00:00")
        self.lyrics_stats_label.setStyleSheet("color: #888; font-size: 10px;")
        lyrics_layout.addWidget(self.lyrics_stats_label)

        tags_container = QWidget()
        tags_layout = QVBoxLayout(tags_container)
        
        tags_layout.addWidget(QLabel("Active Tags:"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setFont(QFont("Consolas", 11))
        self.tags_edit.setPlaceholderText("Enter tags separated by commas...")
        self.tags_edit.textChanged.connect(self._mark_modified)
        tags_layout.addWidget(self.tags_edit)
        
        tags_browser_layout = QHBoxLayout()
        
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
        
        cat_group = QGroupBox("Tag Database")
        cat_layout = QVBoxLayout()
        
        tag_search_layout = QHBoxLayout()
        self.tag_search_edit = QLineEdit()
        self.tag_search_edit.setPlaceholderText("🔍 Filter tags...")
        self.tag_search_edit.textChanged.connect(self.filter_tag_tree)
        tag_search_layout.addWidget(self.tag_search_edit)
        cat_layout.addLayout(tag_search_layout)
        
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

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        
        history_group = QGroupBox("History")
        hist_layout = QVBoxLayout()
        
        search_layout = QHBoxLayout()
        self.history_search_edit = QLineEdit()
        self.history_search_edit.setPlaceholderText("🔍 Search history...")
        self.history_search_edit.textChanged.connect(self._on_history_search_changed)
        search_layout.addWidget(self.history_search_edit)
        btn_refresh_history = QPushButton("🔄")
        btn_refresh_history.setFixedWidth(40)
        btn_refresh_history.clicked.connect(self.refresh_history)
        search_layout.addWidget(btn_refresh_history)
        hist_layout.addLayout(search_layout)
        
        self.history_list = QListWidget()
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._history_context_menu)
        self.history_list.itemDoubleClicked.connect(self.load_history_item)
        hist_layout.addWidget(self.history_list)
        
        history_btn_layout = QHBoxLayout()
        btn_open_history_folder = QPushButton("📁 Open Folder")
        btn_open_history_folder.clicked.connect(self.open_history_folder)
        btn_delete_history = QPushButton("🗑 Delete")
        btn_delete_history.clicked.connect(self.delete_history_item)
        history_btn_layout.addWidget(btn_open_history_folder)
        history_btn_layout.addWidget(btn_delete_history)
        hist_layout.addLayout(history_btn_layout)
        
        history_group.setLayout(hist_layout)
        history_layout.addWidget(history_group)
        self.tabs.addTab(history_tab, "🎵 History")

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
        
        # FIX: Accumulate plain text for full log saving
        self._full_console_log += text
        
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

    # --- PRESET MANAGEMENT ---
    # -------------------------------------------------------------------------
    def load_custom_presets(self):
        self.custom_presets = {}
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                    self.custom_presets = json.load(f)
            except Exception as e:
                self.log_console(f"Failed to load custom presets: {e}\n", "error")
                self.custom_presets = {}
        self.refresh_preset_combo()

    def save_custom_presets(self):
        try:
            with open(PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.custom_presets, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log_console(f"Failed to save custom presets: {e}\n", "error")

    def refresh_preset_combo(self):
        if not hasattr(self, 'template_combo'): return
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem("Select a template...")
        
        for category, preset_names in PRESET_CATEGORIES.items():
            available = [p for p in preset_names if p in SONG_TEMPLATES]
            if available:
                self.template_combo.addItem(f"── {category} ──")
                self.template_combo.model().item(self.template_combo.count() - 1).setEnabled(False)
                for name in available:
                    self.template_combo.addItem(f"  🎵 {name}")
        
        if self.custom_presets:
            self.template_combo.addItem("── My Custom Presets ──")
            self.template_combo.model().item(self.template_combo.count() - 1).setEnabled(False)
            for name in self.custom_presets:
                self.template_combo.addItem(f"  ⭐ {name}")
        
        self.template_combo.blockSignals(False)

    def save_current_as_preset(self):
        lyrics = self.lyrics_edit.toPlainText()
        tags = self.tags_edit.text()
        if not lyrics and not tags:
            self.log_console("Nothing to save. Add lyrics or tags first.\n", "warning")
            return
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:", text="")
        if not ok or not name.strip(): return
        name = name.strip()
        
        if name in SONG_TEMPLATES:
            reply = QMessageBox.question(self, "Overwrite Built-in Preset",
                f"'{name}' is a built-in preset. Save as custom with this name anyway?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return
                
        if name in self.custom_presets:
            reply = QMessageBox.question(self, "Overwrite Preset",
                f"A preset named '{name}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return
        
        self.custom_presets[name] = {"tags": tags, "lyrics": lyrics}
        self.save_custom_presets()
        self.refresh_preset_combo()
        self.log_console(f"✅ Preset '{name}' saved successfully!\n", "success")

    def delete_custom_preset(self):
        if not self.custom_presets:
            self.log_console("No custom presets to delete.\n", "info")
            return
        names = list(self.custom_presets.keys())
        name, ok = QInputDialog.getItem(self, "Delete Preset", "Select preset to delete:", names, 0, False)
        if not ok or not name: return
        reply = QMessageBox.question(self, "Delete Preset", f"Delete preset '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.custom_presets[name]
            self.save_custom_presets()
            self.refresh_preset_combo()
            self.log_console(f"Deleted preset '{name}'\n", "info")

    def export_presets(self):
        if not self.custom_presets:
            self.log_console("No custom presets to export.\n", "warning")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Export Presets", f"presets_{datetime.now().strftime('%Y%m%d')}.json", "Preset Files (*.json)")
        if f:
            try:
                with open(f, "w", encoding="utf-8") as file:
                    json.dump(self.custom_presets, file, indent=2, ensure_ascii=False)
                self.log_console(f"✅ Exported {len(self.custom_presets)} presets to {f}\n", "success")
            except Exception as e:
                self.log_console(f"Failed to export: {e}\n", "error")

    def import_presets(self):
        f, _ = QFileDialog.getOpenFileName(self, "Import Presets", "", "Preset Files (*.json)")
        if not f: return
        try:
            with open(f, "r", encoding="utf-8") as file:
                imported = json.load(file)
            if not isinstance(imported, dict):
                self.log_console("Invalid preset file format.\n", "error")
                return
            count = 0
            for name, data in imported.items():
                if "tags" in data and "lyrics" in data:
                    if name not in SONG_TEMPLATES:
                        self.custom_presets[name] = data
                        count += 1
                    else:
                        self.log_console(f"Skipped '{name}' (built-in name conflict)\n", "warning")
            self.save_custom_presets()
            self.refresh_preset_combo()
            self.log_console(f"✅ Imported {count} preset(s) successfully!\n", "success")
        except Exception as e:
            self.log_console(f"Failed to import: {e}\n", "error")

    def show_preset_manager(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Preset Manager")
        dialog.setText("What would you like to do?")
        btn_delete = dialog.addButton("🗑 Delete Custom", QMessageBox.ActionRole)
        btn_export = dialog.addButton("📤 Export", QMessageBox.ActionRole)
        btn_import = dialog.addButton("📥 Import", QMessageBox.ActionRole)
        dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == btn_delete: self.delete_custom_preset()
        elif clicked == btn_export: self.export_presets()
        elif clicked == btn_import: self.import_presets()

    def apply_template(self, template_name: str):
        if template_name.startswith("  🎵 "):
            name = template_name.replace("  🎵 ", "").strip()
            is_builtin = True
        elif template_name.startswith("  ⭐ "):
            name = template_name.replace("  ⭐ ", "").strip()
            is_builtin = False
        elif template_name.startswith("── ") or template_name == "Select a template...":
            return
        else:
            name = template_name.strip()
            is_builtin = name in SONG_TEMPLATES
        
        if is_builtin and name in SONG_TEMPLATES:
            tpl = SONG_TEMPLATES[name]
        elif not is_builtin and name in self.custom_presets:
            tpl = self.custom_presets[name]
        else:
            return
        
        reply = QMessageBox.question(self, "Apply Preset", f"Apply '{name}' preset? This will replace current lyrics and tags.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.lyrics_edit.setPlainText(tpl['lyrics'])
            self.tags_edit.setText(tpl['tags'])
            self.log_console(f"✅ Applied preset: {name}\n", "success")
            self._mark_modified()

    # --- LYRICS EDITING TOOLS ---
    # -------------------------------------------------------------------------
    def _on_insert_combo_changed(self, index: int):
        if index == 0: return
        text = self.insert_combo.currentText()
        self.insert_structure(text)
        self.insert_combo.blockSignals(True)
        self.insert_combo.setCurrentIndex(0)
        self.insert_combo.blockSignals(False)

    def show_lyrics_context_menu(self, pos: QPoint):
        menu = self.lyrics_edit.createStandardContextMenu()
        menu.addSeparator()
        action_move_up = menu.addAction("⬆ Move Line Up")
        action_move_down = menu.addAction("⬇ Move Line Down")
        menu.addSeparator()
        action_format_tags = menu.addAction("✨ Format Tags")
        action_capitalize = menu.addAction("Aa Capitalize Lines")
        action_cleanup = menu.addAction("🧹 Trim Empty Lines")
        menu.addSeparator()
        action_find = menu.addAction("🔍 Find & Replace")
        action = menu.exec(self.lyrics_edit.mapToGlobal(pos))
        if action == action_move_up: self.move_line_up()
        elif action == action_move_down: self.move_line_down()
        elif action == action_format_tags: self.format_section_tags()
        elif action == action_capitalize: self.capitalize_lines()
        elif action == action_cleanup: self.format_cleanup_lyrics()
        elif action == action_find: self.show_find_replace()

    def move_line_up(self):
        cursor = self.lyrics_edit.textCursor()
        pos = cursor.position()
        text = self.lyrics_edit.toPlainText()
        lines = text.split('\n')
        line_num = text[:pos].count('\n')
        if line_num == 0: return
        lines[line_num], lines[line_num - 1] = lines[line_num - 1], lines[line_num]
        new_text = '\n'.join(lines)
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.insertText(new_text)
        cursor.endEditBlock()
        new_pos = len('\n'.join(lines[:line_num - 1]))
        if line_num > 1: new_pos += 1
        cursor.setPosition(new_pos)
        self.lyrics_edit.setTextCursor(cursor)
        self._mark_modified()

    def move_line_down(self):
        cursor = self.lyrics_edit.textCursor()
        pos = cursor.position()
        text = self.lyrics_edit.toPlainText()
        lines = text.split('\n')
        line_num = text[:pos].count('\n')
        if line_num >= len(lines) - 1: return
        lines[line_num], lines[line_num + 1] = lines[line_num + 1], lines[line_num]
        new_text = '\n'.join(lines)
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.insertText(new_text)
        cursor.endEditBlock()
        new_pos = len('\n'.join(lines[:line_num + 1]))
        if line_num + 1 > 0: new_pos += 1
        cursor.setPosition(new_pos)
        self.lyrics_edit.setTextCursor(cursor)
        self._mark_modified()

    def format_section_tags(self):
        text = self.lyrics_edit.toPlainText()
        new_text = re.sub(r'\[.*?\]', lambda m: m.group(0).title(), text)
        if text != new_text:
            cursor = self.lyrics_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            cursor.insertText(new_text)
            cursor.endEditBlock()
            self.log_console("✨ Formatted section tags.\n", "info")
            self._mark_modified()

    def capitalize_lines(self):
        text = self.lyrics_edit.toPlainText()
        lines = text.split('\n')
        capitalized_lines = []
        for line in lines:
            if line.strip() and not line.strip().startswith('('):
                line = line[0].upper() + line[1:]
            capitalized_lines.append(line)
        new_text = '\n'.join(capitalized_lines)
        if text != new_text:
            cursor = self.lyrics_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            cursor.insertText(new_text)
            cursor.endEditBlock()
            self.log_console("Aa Capitalized first letters of lines.\n", "info")
            self._mark_modified()

    def format_cleanup_lyrics(self):
        text = self.lyrics_edit.toPlainText()
        new_text = re.sub(r'\n{3,}', '\n\n', text).strip()
        if text != new_text:
            cursor = self.lyrics_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            cursor.insertText(new_text)
            cursor.endEditBlock()
            self.log_console("🧹 Cleaned up empty lines and spaces.\n", "info")
            self._mark_modified()

    def zoom_in(self):
        font = self.lyrics_edit.font()
        if font.pointSize() < 24:
            font.setPointSize(font.pointSize() + 1)
            self.lyrics_edit.setFont(font)

    def zoom_out(self):
        font = self.lyrics_edit.font()
        if font.pointSize() > 8:
            font.setPointSize(font.pointSize() - 1)
            self.lyrics_edit.setFont(font)

    def show_find_replace(self):
        if hasattr(self, 'find_dialog') and self.find_dialog.isVisible():
            self.find_dialog.raise_()
            self.find_dialog.activateWindow()
            return
        self.find_dialog = FindReplaceDialog(self)
        self.find_dialog.find_btn.clicked.connect(self.find_next)
        self.find_dialog.replace_btn.clicked.connect(self.replace_one)
        self.find_dialog.replace_all_btn.clicked.connect(self.replace_all)
        self.find_dialog.show()

    def find_next(self):
        if not hasattr(self, 'find_dialog'): return
        text = self.find_dialog.find_edit.text()
        if not text: return
        editor = self.lyrics_edit
        cursor = editor.textCursor()
        new_cursor = editor.document().find(text, cursor)
        if not new_cursor.isNull():
            editor.setTextCursor(new_cursor)
        else:
            cursor.movePosition(QTextCursor.Start)
            new_cursor = editor.document().find(text, cursor)
            if not new_cursor.isNull():
                editor.setTextCursor(new_cursor)
            else:
                self.log_console("Text not found.\n", "info")

    def replace_one(self):
        if not hasattr(self, 'find_dialog'): return
        find_text = self.find_dialog.find_edit.text()
        replace_text = self.find_dialog.replace_edit.text()
        if not find_text: return
        editor = self.lyrics_edit
        cursor = editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == find_text:
            cursor.insertText(replace_text)
            self.find_next()
        else:
            self.find_next()
            cursor = editor.textCursor()
            if cursor.hasSelection() and cursor.selectedText() == find_text:
                cursor.insertText(replace_text)

    def replace_all(self):
        if not hasattr(self, 'find_dialog'): return
        find_text = self.find_dialog.find_edit.text()
        replace_text = self.find_dialog.replace_edit.text()
        if not find_text: return
        text = self.lyrics_edit.toPlainText()
        new_text = text.replace(find_text, replace_text)
        if text != new_text:
            cursor = self.lyrics_edit.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            cursor.insertText(new_text)
            cursor.endEditBlock()
            self.log_console(f"Replaced all occurrences of '{find_text}'.\n", "success")
            self._mark_modified()

    def _count_syllables(self, word: str) -> int:
        word = word.lower()
        if not word: return 0
        vowels = "aeiouy"
        count = 0
        if word[0] in vowels: count += 1
        for i in range(1, len(word)):
            if word[i] in vowels and word[i-1] not in vowels:
                count += 1
        if word.endswith("e"): count -= 1
        if count == 0: count = 1
        return count

    def _estimate_syllables(self, text: str) -> int:
        words = re.findall(r'\b[A-Za-z]+\b', text)
        return sum(self._count_syllables(w) for w in words)

    def update_lyrics_stats(self):
        text = self.lyrics_edit.toPlainText()
        words = len(text.split())
        lines = len([l for l in text.split('\n') if l.strip()])
        syl = self._estimate_syllables(text)
        est_seconds = syl / 3.0 if syl > 0 else 0
        est_time = time.strftime('%M:%S', time.gmtime(est_seconds))
        self.lyrics_stats_label.setText(f"Words: {words} | Lines: {lines} | Syllables: {syl} | Est. Time: {est_time}")

    def show_detailed_stats(self) -> None:
        text = self.lyrics_edit.toPlainText()
        words = len(text.split())
        lines = len([l for l in text.split('\n') if l.strip()])
        chars = len(text)
        syl = self._estimate_syllables(text)
        sections = len(re.findall(r'\[.*?\]', text))
        stages = len(re.findall(r'\(.*?\)', text))
        tags = len([t for t in self.tags_edit.text().split(',') if t.strip()])
        est_seconds = syl / 3.0 if syl > 0 else 0
        est_time = time.strftime('%M:%S', time.gmtime(est_seconds))
        msg = (
            f"<h3>Lyrics Statistics</h3><table cellpadding='4'>"
            f"<tr><td>Words:</td><td><b>{words}</b></td></tr>"
            f"<tr><td>Lines:</td><td><b>{lines}</b></td></tr>"
            f"<tr><td>Syllables:</td><td><b>{syl}</b></td></tr>"
            f"<tr><td>Characters:</td><td><b>{chars}</b></td></tr>"
            f"<tr><td>Sections:</td><td><b>{sections}</b></td></tr>"
            f"<tr><td>Stage directions:</td><td><b>{stages}</b></td></tr>"
            f"<tr><td>Active tags:</td><td><b>{tags}</b></td></tr>"
            f"<tr><td>Estimated duration:</td><td><b>{est_time}</b></td></tr>"
            f"</table>"
        )
        QMessageBox.information(self, "Statistics", msg)

    def generate_random_structure(self):
        sections = ["[Intro]", "[Verse 1]", "[Verse 2]", "[Prechorus]", "[Chorus]", "[Bridge]", "[Guitar Solo]", "[Drop]", "[Outro]"]
        structure = ["[Intro]", "[Verse 1]", "[Chorus]", "[Verse 2]", "[Chorus]"]
        if random.random() > 0.3:
            structure.insert(4, "[Prechorus]")
            structure.insert(2, "[Prechorus]")
        if random.random() > 0.5: structure.append("[Bridge]")
        elif random.random() > 0.5: structure.append("[Guitar Solo]")
        structure.append("[Chorus]")
        structure.append("[Outro]")
        lines = []
        for sec in structure:
            lines.append(sec)
            if "Solo" in sec or "Drop" in sec or "Intro" in sec or "Outro" in sec:
                lines.append("(instrumental)")
            else:
                lines.append("Write your lyrics here...")
                lines.append("And another line here...")
            lines.append("")
        reply = QMessageBox.question(self, "Generate Structure", "Generate a random song structure? This will replace current lyrics.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.lyrics_edit.setPlainText("\n".join(lines))
            self.log_console("🎲 Generated random song structure.\n", "success")
            self._mark_modified()

    # --- GENERATION ENGINE ---
    # -------------------------------------------------------------------------
    def _get_lyrics_chunks(self, lyrics: str) -> List[str]:
        max_sec = self.chunk_sec_spin.value()
        max_words = int(max_sec * 2.5)
        parts = re.split(r'(?=\[.*?\])', lyrics)
        parts = [p.strip() for p in parts if p.strip()]
        chunks = []
        current_chunk = ""
        current_words = 0
        for part in parts:
            part_words = len(part.split())
            if part_words > max_words:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                    current_words = 0
                lines = part.split('\n')
                sub_chunk = ""
                sub_words = 0
                for line in lines:
                    line_words = len(line.split())
                    if sub_words + line_words > max_words and sub_chunk:
                        chunks.append(sub_chunk)
                        sub_chunk = line
                        sub_words = line_words
                    else:
                        if sub_chunk: sub_chunk += "\n" + line
                        else: sub_chunk = line
                        sub_words += line_words
                if sub_chunk: chunks.append(sub_chunk)
            elif current_words + part_words > max_words and current_chunk:
                chunks.append(current_chunk)
                current_chunk = part
                current_words = part_words
            else:
                if current_chunk: current_chunk += "\n\n" + part
                else: current_chunk = part
                current_words += part_words
        if current_chunk: chunks.append(current_chunk)
        return chunks

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

        self.last_generation_params = {
            'lyrics': lyrics,
            'tags': tags,
            'output': base_output,
            'variations': self.variations_spin.value(),
            'max_len': self.get_max_length_ms(),
            'topk': self.topk_spin.value(),
            'temp': self.temperature_spin.value(),
            'cfg': self.cfg_scale_spin.value(),
            'format': self.format_combo.currentText(),
            'mula_device': self.mula_device_combo.currentText(),
            'codec_device': self.codec_device_combo.currentText(),
            'mula_dtype': self.mula_dtype_combo.currentText(),
            'codec_dtype': self.codec_dtype_combo.currentText(),
            'smart_split': self.smart_split_check.isChecked(),
            'chunk_sec': self.chunk_sec_spin.value()
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

        output_dir = os.path.dirname(output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        use_smart_split = self.smart_split_check.isChecked()
        chunks = []

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="tags_", dir=str(self.temp_dir), delete=False, encoding='utf-8') as f:
                f.write(tags)
                self.tags_file = f.name
        except Exception as e:
            self.log_console(f"Failed to create temp files: {e}\n", "error")
            return

        if use_smart_split:
            chunks = self._get_lyrics_chunks(lyrics)
            if len(chunks) <= 1:
                self.log_console("Smart Split enabled, but lyrics are short enough for 1 chunk. Generating normally.\n")
                use_smart_split = False
            else:
                self.log_console(f"Smart Split: Divided lyrics into {len(chunks)} chunks.\n")

        try:
            if use_smart_split:
                self.lyrics_file = None
                self.chunk_files = []
                for i, chunk in enumerate(chunks):
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix=f"lyrics_chunk_{i}_", dir=str(self.temp_dir), delete=False, encoding='utf-8') as f:
                        f.write(chunk)
                        self.chunk_files.append(f.name)
            else:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="lyrics_", dir=str(self.temp_dir), delete=False, encoding='utf-8') as f:
                    f.write(lyrics)
                    self.lyrics_file = f.name
        except Exception as e:
            self.log_console(f"Failed to create temp files: {e}\n", "error")
            return

        self.log_console(f"\n{'='*60}\n--- Starting Variation {self.current_variation + 1}/{self.total_variations} ---\n{'='*60}\n")
        self.log_console(f"Output: {output}\n")
        
        _max_ms = self.get_max_length_ms()
        _max_str = time.strftime('%H:%M:%S', time.gmtime(_max_ms / 1000))
        self.log_console(
            f"Params: topk={self.topk_spin.value()}, temp={self.temperature_spin.value()}, "
            f"cfg={self.cfg_scale_spin.value()}, max_len={_max_str} ({_max_ms} ms)\n\n"
        )
        
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

        self.gen_thread = QThread()
        
        if use_smart_split:
            chunk_max_ms = self.chunk_sec_spin.value() * 1000
            self.gen_worker = SplitGenerationWorker(
                self.model_path_edit.text(), self.version_combo.currentText(),
                self.chunk_files, self.tags_file, output,
                chunk_max_ms, self.topk_spin.value(),
                self.temperature_spin.value(), self.cfg_scale_spin.value(),
                self.mula_device_combo.currentText(), self.codec_device_combo.currentText(),
                self.mula_dtype_combo.currentText(), self.codec_dtype_combo.currentText(),
                self.lazy_load_check.isChecked()
            )
        else:
            self.gen_worker = GenerationWorker(
                self.model_path_edit.text(), self.version_combo.currentText(),
                self.lyrics_file, self.tags_file, output,
                self.get_max_length_ms(), self.topk_spin.value(),
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
        
        # Save Metadata JSON
        try:
            meta_path = os.path.splitext(save_path)[0] + "_meta.json"
            meta_data = {
                "lyrics": self.lyrics_edit.toPlainText(),
                "tags": self.tags_edit.text(),
                "params": self.last_generation_params
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log_console(f"Warning: Could not save metadata file: {e}\n", "warning")
        
        if self.save_log_check.isChecked():
            log_path = os.path.splitext(save_path)[0] + "_log.txt"
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(self._full_console_log)
            except:
                pass
        
        try:
            history_path = self.history_dir / os.path.basename(save_path)
            shutil.copy2(save_path, history_path)
        except:
            pass
        
        # FIX: Cleanup temporary lyrics/tags files
        for f in [self.lyrics_file, self.tags_file] + self.chunk_files:
            if f and os.path.exists(f):
                try: os.remove(f)
                except: pass
        self.lyrics_file = None
        self.tags_file = None
        self.chunk_files = []
        
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
        
        self.tabs.setCurrentIndex(3) # Switch to History tab
        
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
        
        # FIX: Cleanup temporary lyrics/tags files on error as well
        for f in [self.lyrics_file, self.tags_file] + self.chunk_files:
            if f and os.path.exists(f):
                try: os.remove(f)
                except: pass
        self.lyrics_file = None
        self.tags_file = None
        self.chunk_files = []
        
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
                self.log_console(f"⚠ VRAM usage at {percent:.0f}%! Consider reducing max length, enabling smart split, or enabling lazy loading.\n", "warning")
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

    def toggle_loop(self):
        is_looped = self.loop_btn.isChecked()
        if is_looped:
            self.media_player.setLoops(QMediaPlayer.InfiniteLoop)
            self.log_console("Looping enabled.\n", "info")
        else:
            self.media_player.setLoops(1)
            self.log_console("Looping disabled.\n", "info")

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
            if not self.loop_btn.isChecked():
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
            max_len=self.get_max_length_ms(),
            format=self.format_combo.currentText(),
            output_path=self.output_path_edit.text(),
            variations=self.variations_spin.value(),
            mula_device=self.mula_device_combo.currentText(),
            codec_device=self.codec_device_combo.currentText(),
            mula_dtype=self.mula_dtype_combo.currentText(),
            codec_dtype=self.codec_dtype_combo.currentText(),
            smart_split=self.smart_split_check.isChecked(),
            chunk_sec=self.chunk_sec_spin.value(),
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
        
        self.lyrics_edit.setPlainText(item.lyrics)
        self.tags_edit.setText(item.tags)
        self.output_path_edit.setText(item.output_path)
        self.temperature_spin.setValue(item.temp)
        self.topk_spin.setValue(item.topk)
        self.cfg_scale_spin.setValue(item.cfg)
        self.set_max_length_ms(item.max_len)
        self.format_combo.setCurrentText(item.format)
        self.variations_spin.setValue(item.variations)
        self.mula_device_combo.setCurrentText(item.mula_device)
        self.codec_device_combo.setCurrentText(item.codec_device)
        self.mula_dtype_combo.setCurrentText(item.mula_dtype)
        self.codec_dtype_combo.setCurrentText(item.codec_dtype)
        self.smart_split_check.setChecked(item.smart_split)
        self.chunk_sec_spin.setValue(item.chunk_sec)
        
        self.start_generation()

    # --- TAG DATABASE ---
    # -------------------------------------------------------------------------
    def load_tag_db(self) -> None:
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
        if not hasattr(self, 'tag_tree'): return
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

    def filter_tag_tree(self):
        if not hasattr(self, 'tag_tree'): return
        query = self.tag_search_edit.text().lower().strip()
        for i in range(self.tag_tree.topLevelItemCount()):
            cat_item = self.tag_tree.topLevelItem(i)
            cat_visible = False
            for j in range(cat_item.childCount()):
                tag_item = cat_item.child(j)
                tag_text = tag_item.text(0).lower().replace("#", "").strip()
                is_match = query in tag_text
                tag_item.setHidden(not is_match)
                if is_match: cat_visible = True
            cat_item.setHidden(not cat_visible)

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

    def randomize_params(self):
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
        self.set_max_length_ms(p['max_len'])
        self.topk_spin.setValue(p['topk'])
        self.temperature_spin.setValue(p['temp'])
        self.cfg_scale_spin.setValue(p['cfg'])
        self.format_combo.setCurrentText(p['format'])
        self.mula_device_combo.setCurrentText(p['mula_device'])
        self.codec_device_combo.setCurrentText(p['codec_device'])
        self.mula_dtype_combo.setCurrentText(p['mula_dtype'])
        self.codec_dtype_combo.setCurrentText(p['codec_dtype'])
        self.smart_split_check.setChecked(p.get('smart_split', False))
        self.chunk_sec_spin.setValue(p.get('chunk_sec', 45))
        self.start_generation()

    def show_tap_tempo(self):
        dialog = TapTempoDialog(self)
        dialog.exec()

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
            self.set_max_length_ms(data.get('max_len', DEFAULT_MAX_LENGTH_MS))
            self.topk_spin.setValue(data.get('topk', 50))
            self.temperature_spin.setValue(data.get('temp', 1.0))
            self.cfg_scale_spin.setValue(data.get('cfg', 1.5))
            self.format_combo.setCurrentText(data.get('format', 'mp3'))
            self.mula_device_combo.setCurrentText(data.get('mula_device', 'cuda:0'))
            self.codec_device_combo.setCurrentText(data.get('codec_device', 'cuda:0'))
            self.mula_dtype_combo.setCurrentText(data.get('mula_dtype', 'bfloat16'))
            self.codec_dtype_combo.setCurrentText(data.get('codec_dtype', 'float32'))
            self.smart_split_check.setChecked(data.get('smart_split', False))
            self.chunk_sec_spin.setValue(data.get('chunk_sec', 45))
            
            self.current_project_path = path
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - {os.path.basename(path)}")
            self._clear_modified()
            
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
            'max_len': self.get_max_length_ms(),
            'topk': self.topk_spin.value(),
            'temp': self.temperature_spin.value(),
            'cfg': self.cfg_scale_spin.value(),
            'format': self.format_combo.currentText(),
            'mula_device': self.mula_device_combo.currentText(),
            'codec_device': self.codec_device_combo.currentText(),
            'mula_dtype': self.mula_dtype_combo.currentText(),
            'codec_dtype': self.codec_dtype_combo.currentText(),
            'smart_split': self.smart_split_check.isChecked(),
            'chunk_sec': self.chunk_sec_spin.value()
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
                self.set_max_length_ms(data.get('max_len', DEFAULT_MAX_LENGTH_MS))
                self.topk_spin.setValue(data.get('topk', 50))
                self.temperature_spin.setValue(data.get('temp', 1.0))
                self.cfg_scale_spin.setValue(data.get('cfg', 1.5))
                self.format_combo.setCurrentText(data.get('format', 'mp3'))
                self.smart_split_check.setChecked(data.get('smart_split', False))
                self.chunk_sec_spin.setValue(data.get('chunk_sec', 45))
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
            'max_len': self.get_max_length_ms(),
            'topk': self.topk_spin.value(),
            'temp': self.temperature_spin.value(),
            'cfg': self.cfg_scale_spin.value(),
            'format': self.format_combo.currentText(),
            'smart_split': self.smart_split_check.isChecked(),
            'chunk_sec': self.chunk_sec_spin.value()
        }
        try:
            with open(DRAFT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except:
            pass

    def load_app_state(self):
        hist_dir = self.settings.value("history_dir", "")
        if hist_dir:
            self.history_dir = Path(hist_dir)
            self.history_dir.mkdir(exist_ok=True)
        
        self.recent_projects = list(self.settings.value("recent_projects", []) or [])
        self.favorite_tags = list(self.settings.value("favorite_tags", []) or [])
        
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
            
        main_splitter_state = self.settings.value("main_splitter_state")
        if main_splitter_state:
            self.splitter.restoreState(QByteArray(main_splitter_state))
            
        editor_splitter_state = self.settings.value("editor_splitter_state")
        if editor_splitter_state and hasattr(self, 'editor_split'):
            self.editor_split.restoreState(QByteArray(editor_splitter_state))

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
        for i in range(4):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self.tabs.setCurrentIndex(idx))
        
        QShortcut(QKeySequence("Ctrl+Enter"), self, self.start_generation)
        QShortcut(QKeySequence("Ctrl+R"), self, self.regenerate_last)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.add_to_queue)
        QShortcut(QKeySequence("Space"), self, self.toggle_play)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, lambda: self.save_project(save_as=True))
        QShortcut(QKeySequence("Ctrl+F"), self, self.show_find_replace)
        QShortcut(QKeySequence("Ctrl+="), self, self.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self.zoom_out)
        QShortcut(QKeySequence("Alt+Up"), self, self.move_line_up)
        QShortcut(QKeySequence("Alt+Down"), self, self.move_line_down)
        QShortcut(QKeySequence("Ctrl+T"), self, self.show_tap_tempo)

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
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {{
                background-color: #2a2a3e;
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 4px;
                color: #e0e0e0;
            }}
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTimeEdit:focus {{
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
            QDockWidget {{
                titlebar-background-color: {COLOR_PANEL};
                titlebar-border-color: {COLOR_BORDER};
            }}
            QDockWidget::title {{
                padding: 6px;
                color: {COLOR_ACCENT};
                font-weight: bold;
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
        self.save_custom_presets()
        self.settings.setValue("geometry", self.saveGeometry().data())
        self.settings.setValue("window_state", self.saveState().data())
        self.settings.setValue("main_splitter_state", self.splitter.saveState().data())
        if hasattr(self, 'editor_split'):
            self.settings.setValue("editor_splitter_state", self.editor_split.saveState().data())
        
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