"""
╔══════════════════════════════════════════════════════════════════╗
║  AMRIT RESEARCH OS v4.5 — Voice Agent                           ║
║  core/voice/voice_agent.py                                      ║
║                                                                 ║
║  ਆਵਾਜ਼ ਨਾਲ ਪੂਰਾ ਸਿਸਟਮ ਕੰਟਰੋਲ ਕਰੋ                            ║
║                                                                 ║
║  Stack (ਸਭ ਪਹਿਲਾਂ ਤੋਂ ਤੁਹਾਡੇ ਕੋਲ ਹੈ):                       ║
║    STT  → faster-whisper (offline, local)                       ║
║    LLM  → Ollama qwen3:8b (intent detection)                    ║
║    TTS  → Kokoro-82M ONNX (offline, local)                      ║
║    MIC  → sounddevice / pyaudio                                 ║
║                                                                 ║
║  Install:                                                       ║
║    pip install faster-whisper sounddevice pyaudio numpy         ║
║    ollama pull qwen3:8b                                         ║
║                                                                 ║
║  Commands (Punjabi + English):                                  ║
║    "DNA ਵਿਸ਼ਲੇਸ਼ਣ ਕਰੋ"       → DNA Analysis                   ║
║    "ਖੂਨ ਰਿਪੋਰਟ ਦੱਸੋ"         → Blood Report                   ║
║    "ਰਿਪੋਰਟ ਬਣਾਓ"             → Generate PDF                   ║
║    "ਭੇਜੋ"                    → Dispatch to Medical Center      ║
║    "ਅਲਰਟ ਦਿਖਾਓ"             → Show Active Alerts              ║
║    "ਮਰੀਜ਼ ਦੀ ਜਾਣਕਾਰੀ"        → Patient Status                  ║
║    "ਖੋਜ ਕਰੋ [topic]"         → Research Query                  ║
║    "ਬੰਦ ਕਰੋ"                 → Stop Voice Mode                 ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import io
import json
import logging
import threading
import time
import queue
import tempfile
import numpy as np
import requests
from datetime import datetime
from typing import Optional, Callable

log = logging.getLogger("AmritVoice")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

OLLAMA = "http://localhost:11434"
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION = 1.5   # seconds of silence = end of speech


# ══════════════════════════════════════════════════════════════
# STT — faster-whisper (offline)
# ══════════════════════════════════════════════════════════════
class WhisperSTT:
    """
    Local speech-to-text using faster-whisper.
    Supports Punjabi, Hindi, English.
    No internet required.
    """

    def __init__(self, model_size: str = "base",
                 language: str = None):  # None = auto-detect
        self.model_size = model_size
        self.language   = language
        self._model     = None
        log.info(f"🎤 WhisperSTT ready (model={model_size}, lang={language or 'auto'})")

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",   # Apple M-series optimized
                )
                log.info("  ✅ Whisper model loaded")
            except ImportError:
                raise ImportError("Run: pip install faster-whisper")

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file → text."""
        self._load()
        segments, info = self._model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
            vad_filter=True,       # remove silence
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        text = " ".join(s.text for s in segments).strip()
        log.info(f"  🗣️  Transcribed ({info.language}): {text}")
        return text

    def transcribe_bytes(self, audio_bytes: bytes,
                          sample_rate: int = SAMPLE_RATE) -> str:
        """Transcribe raw audio bytes."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            import wave, struct
            with wave.open(f, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)
            tmp = f.name
        try:
            return self.transcribe(tmp)
        finally:
            os.unlink(tmp)


# ══════════════════════════════════════════════════════════════
# MICROPHONE RECORDER
# ══════════════════════════════════════════════════════════════
class MicRecorder:
    """
    Records from microphone until silence.
    VAD (Voice Activity Detection) built-in.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE,
                 silence_threshold: float = SILENCE_THRESHOLD,
                 silence_duration: float = SILENCE_DURATION):
        self.rate      = sample_rate
        self.threshold = silence_threshold
        self.silence_s = silence_duration

    def record_until_silence(self) -> Optional[bytes]:
        """
        Record microphone until silence detected.
        Returns raw PCM bytes or None if sounddevice unavailable.
        """
        try:
            import sounddevice as sd
        except ImportError:
            log.warning("sounddevice not installed: pip install sounddevice")
            return None

        log.info("  🎙️  Listening… (speak now)")
        frames = []
        silence_frames = 0
        frames_per_chunk = int(self.rate * 0.1)  # 100ms chunks
        max_silence = int(self.silence_s / 0.1)
        recording_started = False

        with sd.InputStream(samplerate=self.rate, channels=1,
                            dtype='int16') as stream:
            while True:
                chunk, _ = stream.read(frames_per_chunk)
                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2)) / 32768.0

                if rms > self.threshold:
                    recording_started = True
                    silence_frames = 0
                    frames.append(chunk.tobytes())
                elif recording_started:
                    frames.append(chunk.tobytes())
                    silence_frames += 1
                    if silence_frames >= max_silence:
                        break

                if len(frames) > 600:  # max 60 seconds
                    break

        if not frames:
            return None

        log.info(f"  ✅ Recorded {len(frames)*0.1:.1f}s of audio")
        return b"".join(frames)


# ══════════════════════════════════════════════════════════════
# TTS — Kokoro-82M ONNX
# ══════════════════════════════════════════════════════════════
class KokoroTTS:
    """
    Local text-to-speech using Kokoro-82M ONNX.
    Speaks AMRIT's responses aloud.
    Falls back to pyttsx3 if Kokoro not available.
    """

    def __init__(self, model_path: str = "models/kokoro-v0_19.onnx",
                 voices_path: str = "models/voices.bin",
                 voice: str = "af_sarah"):
        self.model_path  = model_path
        self.voices_path = voices_path
        self.voice       = voice
        self._kokoro     = None
        self._fallback   = None
        log.info(f"🔊 KokoroTTS ready (voice={voice})")

    def _load(self):
        if self._kokoro is not None:
            return True
        try:
            from kokoro_onnx import Kokoro
            self._kokoro = Kokoro(self.model_path, self.voices_path)
            log.info("  ✅ Kokoro ONNX loaded")
            return True
        except Exception:
            # Fallback to pyttsx3
            try:
                import pyttsx3
                self._fallback = pyttsx3.init()
                self._fallback.setProperty('rate', 160)
                log.info("  ⚠️  Kokoro unavailable — using pyttsx3")
                return True
            except Exception:
                log.warning("  ❌ No TTS available. pip install pyttsx3")
                return False

    def speak(self, text: str, play: bool = True) -> Optional[bytes]:
        """
        Convert text to speech and optionally play it.
        Returns audio bytes.
        """
        if not self._load():
            print(f"  [AMRIT says]: {text}")
            return None

        if self._kokoro:
            try:
                samples, sample_rate = self._kokoro.create(
                    text, voice=self.voice, speed=1.0, lang="en-us"
                )
                if play:
                    self._play_audio(samples, sample_rate)
                audio_bytes = (samples * 32767).astype(np.int16).tobytes()
                return audio_bytes
            except Exception as e:
                log.warning(f"Kokoro speak error: {e}")

        if self._fallback:
            self._fallback.say(text)
            self._fallback.runAndWait()

        return None

    def speak_result(self, result: dict) -> None:
        """Speak a medical analysis result summary."""
        summary_parts = []

        severity = result.get("blood_analysis", {}).get("severity_summary", "")
        if severity:
            # Clean emoji for TTS
            clean = severity.replace("🚨","Critical:").replace("⚠️","Warning:").replace("✅","")
            summary_parts.append(clean)

        patterns = result.get("blood_analysis", {}).get("suspected_patterns", [])
        if patterns:
            summary_parts.append(f"Detected patterns: {', '.join(patterns)}")

        synthesis = result.get("ai_synthesis", "")
        if synthesis:
            summary_parts.append(synthesis[:200])

        text = ". ".join(summary_parts) if summary_parts else "Analysis complete."
        self.speak(text)

    def _play_audio(self, samples: np.ndarray, sample_rate: int) -> None:
        try:
            import sounddevice as sd
            sd.play(samples, sample_rate)
            sd.wait()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# INTENT ENGINE — Ollama
# ══════════════════════════════════════════════════════════════
class IntentEngine:
    """
    Parses voice command → structured intent using Ollama.

    Intents:
      analyze_dna        → DNA sequence analysis
      analyze_blood      → Blood report analysis
      generate_report    → Create PDF report
      dispatch_report    → Send to medical center
      show_alerts        → Display active alerts
      patient_status     → Patient pipeline status
      research_query     → Scientific research
      system_status      → System health check
      stop               → Exit voice mode
      unknown            → Can't understand
    """

    SYSTEM_PROMPT = """You are AMRIT's voice command interpreter.
Parse the user's spoken command and return ONLY a JSON object.

Available intents:
- analyze_dna: user wants DNA analysis
- analyze_blood: user wants blood report analysis
- generate_report: user wants PDF report generated
- dispatch_report: user wants report sent to medical center
- show_alerts: user wants to see alerts
- patient_status: user asks about a patient
- research_query: user wants scientific research
- system_status: user asks about system health
- stop: user wants to stop voice mode
- unknown: cannot understand

Commands may be in Punjabi, Hindi, or English.

Punjabi mappings:
  "DNA ਵਿਸ਼ਲੇਸ਼ਣ" = analyze_dna
  "ਖੂਨ ਰਿਪੋਰਟ" = analyze_blood
  "ਰਿਪੋਰਟ ਬਣਾਓ" = generate_report
  "ਭੇਜੋ" = dispatch_report
  "ਅਲਰਟ" = show_alerts
  "ਮਰੀਜ਼" = patient_status
  "ਖੋਜ" = research_query
  "ਬੰਦ ਕਰੋ" = stop

Return ONLY valid JSON, no explanation:
{
  "intent": "...",
  "confidence": 0.0-1.0,
  "patient_id": "..." or null,
  "query": "..." or null,
  "language": "punjabi|hindi|english"
}"""

    def __init__(self, model: str = "qwen3:8b"):
        self.model = model

    def parse(self, text: str) -> dict:
        """Parse spoken text → intent dict."""
        if not text.strip():
            return {"intent": "unknown", "confidence": 0.0}

        # Quick keyword matching (fast path, no LLM needed)
        quick = self._quick_parse(text)
        if quick["confidence"] > 0.85:
            return quick

        # LLM-based parsing
        try:
            r = requests.post(
                f"{OLLAMA}/api/generate",
                json={
                    "model":  self.model,
                    "prompt": f"Command: {text}",
                    "system": self.SYSTEM_PROMPT,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 150},
                },
                timeout=15,
            )
            raw = r.json().get("response", "").strip()
            # Extract JSON
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            log.warning(f"Intent LLM error: {e}")

        return quick if quick["confidence"] > 0.3 else {"intent": "unknown", "confidence": 0.0}

    def _quick_parse(self, text: str) -> dict:
        """Keyword-based fast intent detection."""
        t = text.lower()
        rules = [
            (["dna", "ਡੀਐਨਏ", "dna ਵਿਸ਼ਲੇਸ਼ਣ", "gene", "ਜੀਨ"], "analyze_dna"),
            (["blood", "ਖੂਨ", "haemoglobin", "ਹੀਮੋਗਲੋਬਿਨ", "cbc", "ਰਿਪੋਰਟ ਦੱਸੋ"], "analyze_blood"),
            (["report", "pdf", "ਰਿਪੋਰਟ ਬਣਾਓ", "generate"], "generate_report"),
            (["send", "ਭੇਜੋ", "dispatch", "email", "medical center"], "dispatch_report"),
            (["alert", "ਅਲਰਟ", "warning", "critical"], "show_alerts"),
            (["patient", "ਮਰੀਜ਼", "status", "pipeline"], "patient_status"),
            (["research", "ਖੋਜ", "study", "paper", "arxiv"], "research_query"),
            (["system", "ਸਿਸਟਮ", "health", "ollama", "status"], "system_status"),
            (["stop", "ਬੰਦ", "quit", "exit", "bye"], "stop"),
        ]
        for keywords, intent in rules:
            if any(k in t for k in keywords):
                return {"intent": intent, "confidence": 0.9,
                        "query": text, "language": "auto"}
        return {"intent": "unknown", "confidence": 0.2, "query": text}


# ══════════════════════════════════════════════════════════════
# COMMAND ROUTER
# ══════════════════════════════════════════════════════════════
class CommandRouter:
    """
    Routes parsed intents to the right AMRIT modules.
    All doctor approval removed — PDF is generated and dispatched automatically.
    Doctor reads PDF independently.
    """

    RESPONSES = {
        "analyze_dna":     "DNA ਵਿਸ਼ਲੇਸ਼ਣ ਸ਼ੁਰੂ ਕਰ ਰਿਹਾ ਹਾਂ। ਕਿਰਪਾ ਉਡੀਕ ਕਰੋ।",
        "analyze_blood":   "ਖੂਨ ਰਿਪੋਰਟ ਦਾ ਵਿਸ਼ਲੇਸ਼ਣ ਕਰ ਰਿਹਾ ਹਾਂ।",
        "generate_report": "PDF ਰਿਪੋਰਟ ਬਣਾ ਰਿਹਾ ਹਾਂ।",
        "dispatch_report": "ਰਿਪੋਰਟ ਮੈਡੀਕਲ ਸੈਂਟਰ ਨੂੰ ਭੇਜ ਰਿਹਾ ਹਾਂ।",
        "show_alerts":     "ਐਕਟਿਵ ਅਲਰਟ ਦਿਖਾ ਰਿਹਾ ਹਾਂ।",
        "patient_status":  "ਮਰੀਜ਼ ਦੀ ਸਥਿਤੀ ਚੈੱਕ ਕਰ ਰਿਹਾ ਹਾਂ।",
        "research_query":  "ਖੋਜ ਕਰ ਰਿਹਾ ਹਾਂ।",
        "system_status":   "ਸਿਸਟਮ ਸਥਿਤੀ ਚੈੱਕ ਕਰ ਰਿਹਾ ਹਾਂ।",
        "stop":            "AMRIT Voice Mode ਬੰਦ ਕਰ ਰਿਹਾ ਹਾਂ। ਧੰਨਵਾਦ।",
        "unknown":         "ਮਾਫ਼ ਕਰਨਾ, ਮੈਂ ਸਮਝਿਆ ਨਹੀਂ। ਕਿਰਪਾ ਦੁਬਾਰਾ ਕਹੋ।",
    }

    def __init__(self, medical_pipeline=None, alert_engine=None,
                 timeline=None, dispatcher=None):
        self.pipeline   = medical_pipeline
        self.alerts     = alert_engine
        self.timeline   = timeline
        self.dispatcher = dispatcher

    def execute(self, intent: dict,
                context: dict = None) -> dict:
        """
        Execute command based on intent.
        Returns result dict with 'spoken_response' key.
        """
        action = intent.get("intent", "unknown")
        ctx    = context or {}
        result = {"intent": action, "success": False}

        spoken = self.RESPONSES.get(action, self.RESPONSES["unknown"])
        result["spoken_response"] = spoken

        if action == "analyze_dna":
            result.update(self._run_dna_analysis(ctx))

        elif action == "analyze_blood":
            result.update(self._run_blood_analysis(ctx))

        elif action == "generate_report":
            result.update(self._generate_report(ctx))

        elif action == "dispatch_report":
            result.update(self._dispatch(ctx))

        elif action == "show_alerts":
            result.update(self._get_alerts())

        elif action == "patient_status":
            result.update(self._patient_status(ctx))

        elif action == "system_status":
            result.update(self._system_status())

        elif action == "research_query":
            query = intent.get("query", ctx.get("query", ""))
            result.update(self._research(query))

        elif action == "stop":
            result["stop_voice"] = True
            result["success"]    = True

        return result

    def _run_dna_analysis(self, ctx: dict) -> dict:
        seq = ctx.get("dna_sequence", "")
        if not seq:
            return {"spoken_response": "ਕਿਰਪਾ DNA sequence ਦੱਸੋ।", "success": False}
        if self.pipeline:
            try:
                result = self.pipeline.dna.analyze_sequence(seq, ctx.get("patient_name","Patient"))
                gc     = result.get("gc_content_pct", 0)
                orfs   = len(result.get("open_reading_frames", []))
                repeats= len(result.get("repeat_regions", []))
                spoken = (f"DNA ਵਿਸ਼ਲੇਸ਼ਣ ਮੁਕੰਮਲ। "
                          f"GC ਸਮੱਗਰੀ {gc}%। "
                          f"{orfs} ਓਪਨ ਰੀਡਿੰਗ ਫ੍ਰੇਮ। "
                          f"{repeats} repeat regions। "
                          + (result.get("clinical_notes") or [""])[0][:100])
                return {"dna_result": result, "spoken_response": spoken, "success": True}
            except Exception as e:
                return {"spoken_response": f"DNA ਵਿਸ਼ਲੇਸ਼ਣ ਵਿੱਚ ਗਲਤੀ: {str(e)[:50]}", "success": False}
        return {"spoken_response": "ਸਿਸਟਮ ਤਿਆਰ ਨਹੀਂ।", "success": False}

    def _run_blood_analysis(self, ctx: dict) -> dict:
        report = ctx.get("blood_report_text", "")
        if not report:
            return {"spoken_response": "ਕਿਰਪਾ blood report ਦੱਸੋ।", "success": False}
        if self.pipeline:
            try:
                result = self.pipeline.blood.parse_report(
                    report, ctx.get("gender","male"), ctx.get("age", 40)
                )
                severity = result.get("severity_summary","")
                patterns = result.get("suspected_patterns", [])
                flags    = result.get("abnormal_flags", [])
                spoken   = (f"ਖੂਨ ਰਿਪੋਰਟ ਵਿਸ਼ਲੇਸ਼ਣ ਮੁਕੰਮਲ। "
                           f"{len(flags)} ਅਸਾਧਾਰਨ ਮੁੱਲ। "
                           + (f"ਸੰਭਾਵਿਤ: {', '.join(patterns)}। " if patterns else "")
                           + severity.replace("🚨","ਜ਼ਰੂਰੀ: ").replace("⚠️","ਚੇਤਾਵਨੀ: ").replace("✅","")[:100])
                return {"blood_result": result, "spoken_response": spoken, "success": True}
            except Exception as e:
                return {"spoken_response": f"ਖੂਨ ਵਿਸ਼ਲੇਸ਼ਣ ਗਲਤੀ: {str(e)[:50]}", "success": False}
        return {"spoken_response": "ਸਿਸਟਮ ਤਿਆਰ ਨਹੀਂ।", "success": False}

    def _generate_report(self, ctx: dict) -> dict:
        if self.dispatcher:
            try:
                path = self.dispatcher.analyse_and_report(
                    ctx.get("patient_info", {"name":"Patient","id":"P001"}),
                    ctx.get("blood_report_text",""),
                    ctx.get("dna_sequence",""),
                )
                return {
                    "pdf_path": path,
                    "spoken_response": f"PDF ਰਿਪੋਰਟ ਤਿਆਰ ਹੈ। ਫਾਈਲ: {os.path.basename(path)}। ਡਾਕਟਰ ਨੂੰ ਭੇਜਣ ਲਈ ਕਹੋ।",
                    "success": True,
                }
            except Exception as e:
                return {"spoken_response": f"ਰਿਪੋਰਟ ਬਣਾਉਣ ਵਿੱਚ ਗਲਤੀ: {str(e)[:50]}", "success": False}
        return {"spoken_response": "Report module ਤਿਆਰ ਨਹੀਂ।", "success": False}

    def _dispatch(self, ctx: dict) -> dict:
        """Send PDF to medical center — NO doctor approval in system."""
        pdf   = ctx.get("pdf_path", "")
        pinfo = ctx.get("patient_info", {})
        if self.dispatcher and pdf:
            result = self.dispatcher.dispatch.send(pdf, pinfo)
            if result.get("sent"):
                return {
                    "spoken_response": "ਰਿਪੋਰਟ ਮੈਡੀਕਲ ਸੈਂਟਰ ਨੂੰ ਭੇਜ ਦਿੱਤੀ। ਮਰੀਜ਼ ਉੱਥੋਂ ਦਵਾਈ ਲੈ ਸਕਦਾ ਹੈ।",
                    "success": True,
                }
            return {"spoken_response": f"ਭੇਜਣ ਵਿੱਚ ਗਲਤੀ। {result.get('reason','')}","success":False}
        return {"spoken_response": "PDF ਫਾਈਲ ਨਹੀਂ ਮਿਲੀ। ਪਹਿਲਾਂ ਰਿਪੋਰਟ ਬਣਾਓ।", "success": False}

    def _get_alerts(self) -> dict:
        if self.alerts:
            active = self.alerts.get_active_alerts(limit=5)
            summary= self.alerts.dashboard_summary()
            spoken = (f"ਕੁੱਲ {summary.get('total',0)} ਐਕਟਿਵ ਅਲਰਟ। "
                     f"{summary.get('critical',0)} ਗੰਭੀਰ, {summary.get('moderate',0)} ਮੱਧਮ। ")
            if active:
                spoken += f"ਸਭ ਤੋਂ ਨਵਾਂ: {active[0].get('message','')[:80]}"
            return {"alerts": active, "spoken_response": spoken, "success": True}
        return {"spoken_response": "Alert engine ਤਿਆਰ ਨਹੀਂ।", "success": False}

    def _patient_status(self, ctx: dict) -> dict:
        if self.timeline:
            stats = self.timeline.get_dashboard_stats()
            queue = self.timeline.get_pending_doctor_queue()
            spoken = (f"ਕੁੱਲ {stats.get('total_patients',0)} ਮਰੀਜ਼। "
                     f"{stats.get('pending',0)} ਅਜੇ ਚੱਲ ਰਹੇ ਹਨ। "
                     f"{stats.get('dispatched',0)} ਮੈਡੀਕਲ ਸੈਂਟਰ ਨੂੰ ਭੇਜੇ। "
                     f"{stats.get('critical_alerts',0)} ਗੰਭੀਰ ਕੇਸ।")
            return {"stats": stats, "queue": queue, "spoken_response": spoken, "success": True}
        return {"spoken_response": "Timeline module ਤਿਆਰ ਨਹੀਂ।", "success": False}

    def _system_status(self) -> dict:
        status = {"ollama": False, "models": []}
        try:
            r = requests.get(f"{OLLAMA}/api/tags", timeout=3)
            status["ollama"]  = True
            status["models"]  = [m["name"] for m in r.json().get("models",[])]
        except Exception:
            pass
        spoken = ("Ollama " + ("ਚੱਲ ਰਿਹਾ ਹੈ" if status["ollama"] else "ਬੰਦ ਹੈ") +
                 f"। {len(status['models'])} ਮਾਡਲ ਉਪਲਬਧ।")
        return {"system": status, "spoken_response": spoken, "success": True}

    def _research(self, query: str) -> dict:
        if not query:
            return {"spoken_response": "ਖੋਜ ਲਈ ਕੋਈ ਵਿਸ਼ਾ ਦੱਸੋ।", "success": False}
        try:
            r = requests.post(
                f"{OLLAMA}/api/generate",
                json={
                    "model":  "qwen3:8b",
                    "prompt": f"Medical/scientific question: {query}\nAnswer in 2-3 sentences.",
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 200},
                },
                timeout=30,
            )
            answer = r.json().get("response","")[:300]
            return {"answer": answer, "spoken_response": answer, "success": True}
        except Exception as e:
            return {"spoken_response": f"ਖੋਜ ਵਿੱਚ ਗਲਤੀ: {e}", "success": False}


# ══════════════════════════════════════════════════════════════
# MAIN VOICE AGENT
# ══════════════════════════════════════════════════════════════
class AMRITVoiceAgent:
    """
    Main Voice Agent — orchestrates STT + Intent + Route + TTS.

    Usage:
        agent = AMRITVoiceAgent()
        agent.start()           # Start listening loop
        agent.run_once()        # One command
        agent.process_text("DNA ਵਿਸ਼ਲੇਸ਼ਣ ਕਰੋ")  # Text input
    """

    WAKE_WORDS = ["amrit", "ਅੰਮ੍ਰਿਤ", "hey amrit", "doctor", "ਡਾਕਟਰ"]

    def __init__(self,
                 whisper_model: str = "base",
                 tts_voice: str    = "af_sarah",
                 ollama_model: str = "qwen3:8b",
                 medical_pipeline  = None,
                 alert_engine      = None,
                 timeline          = None,
                 dispatcher        = None):

        self.stt     = WhisperSTT(whisper_model)
        self.tts     = KokoroTTS(voice=tts_voice)
        self.intent  = IntentEngine(ollama_model)
        self.router  = CommandRouter(medical_pipeline, alert_engine,
                                     timeline, dispatcher)
        self.mic     = MicRecorder()
        self._context: dict = {}
        self._running = False

        log.info("🤖 AMRIT Voice Agent ready")
        log.info(f"   STT: faster-whisper ({whisper_model})")
        log.info(f"   TTS: Kokoro-82M ({tts_voice})")
        log.info(f"   LLM: {ollama_model}")

    def speak(self, text: str) -> None:
        """Speak text aloud."""
        log.info(f"  [AMRIT]: {text}")
        self.tts.speak(text)

    def process_text(self, text: str, context: dict = None) -> dict:
        """Process a text command (useful for testing without mic)."""
        ctx    = {**self._context, **(context or {})}
        intent = self.intent.parse(text)
        log.info(f"  Intent: {intent.get('intent')} (conf={intent.get('confidence',0):.2f})")
        result = self.router.execute(intent, ctx)
        self.speak(result.get("spoken_response", ""))
        return result

    def run_once(self) -> Optional[dict]:
        """Record one voice command and process it."""
        audio = self.mic.record_until_silence()
        if not audio:
            self.speak("ਕੋਈ ਆਵਾਜ਼ ਨਹੀਂ ਸੁਣਿਆ।")
            return None
        text = self.stt.transcribe_bytes(audio)
        if not text:
            return None
        return self.process_text(text)

    def start(self) -> None:
        """Start continuous listening loop."""
        self._running = True
        self.speak("ਨਮਸਤੇ। AMRIT Voice Agent ਤਿਆਰ ਹੈ। ਬੋਲੋ।")
        log.info("▶️  Voice loop started")

        while self._running:
            try:
                result = self.run_once()
                if result and result.get("stop_voice"):
                    self._running = False
                    break
                time.sleep(0.5)
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"Voice loop error: {e}")
                time.sleep(1)

        self.speak("AMRIT Voice Mode ਬੰਦ।")
        log.info("⏹️  Voice loop stopped")

    def set_context(self, **kwargs) -> None:
        """Set persistent context (patient info, current DNA, etc.)."""
        self._context.update(kwargs)


# ══════════════════════════════════════════════════════════════
# DEMO
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════╗
║  AMRIT Voice Agent — Text Mode Demo          ║
║  (Mic demo: agent.start())                   ║
╚══════════════════════════════════════════════╝
""")
    agent = AMRITVoiceAgent()

    test_commands = [
        ("ਸਿਸਟਮ ਦੀ ਸਥਿਤੀ ਦੱਸੋ", {}),
        ("DNA ਵਿਸ਼ਲੇਸ਼ਣ ਕਰੋ",
         {"dna_sequence": "ATGCAGCAGCAGCAGCAGCAGCAGCAGTAA",
          "patient_name": "Gurpreet Singh"}),
        ("ਖੂਨ ਰਿਪੋਰਟ ਦੱਸੋ",
         {"blood_report_text": "Hemoglobin: 7.5 g/dL\nGlucose: 380 mg/dL\nHbA1c: 8.9%",
          "gender": "male", "age": 45}),
        ("ਅਲਰਟ ਦਿਖਾਓ", {}),
        ("ਬੰਦ ਕਰੋ", {}),
    ]

    for cmd, ctx in test_commands:
        print(f"\n  ▶ Command: {cmd}")
        result = agent.process_text(cmd, ctx)
        print(f"  ✅ Intent: {result.get('intent')} | Success: {result.get('success')}")
        if result.get("stop_voice"):
            print("  [Voice mode stopped]")
            break

    print("\n📋 To use with real microphone:")
    print("   agent = AMRITVoiceAgent()")
    print("   agent.start()  # continuous listening")
    print("\n📋 Install voice deps:")
    print("   pip install faster-whisper sounddevice pyaudio")
    print("   pip install kokoro-onnx  # or pip install pyttsx3 (fallback)")
