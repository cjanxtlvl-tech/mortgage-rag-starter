# app/tts/polly.py

import hashlib
import os
import re
import html
from pathlib import Path
from typing import Optional, Dict, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class PollyTTS:
    def __init__(
        self,
        cache_dir: str = "/app/audio_cache",
        public_audio_base_url: str = "/audio",
        voice_id: str = "Joanna",
        engine: str = "neural",
        output_format: str = "mp3",
        sample_rate: str = "24000",
        region_name: Optional[str] = None,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.public_audio_base_url = public_audio_base_url.rstrip("/")
        self.voice_id = voice_id
        self.engine = engine
        self.output_format = output_format
        self.sample_rate = sample_rate

        self.client = boto3.client("polly", region_name=region_name)

    def normalize_text(self, text: str) -> str:
        """
        Normalize text so slightly different RAG formatting does not create
        unnecessary duplicate audio files.
        """
        if not text:
            return ""

        text = html.unescape(text)
        text = text.lower().strip()
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"https?://\S+|www\.\S+", "", text)
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", text)
        text = re.sub(r"\bclosing\s+costs\s+are\b", "closing costs", text)
        text = re.sub(r"\bfees\s+you\s+pay\b", "fees", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:250]

    def hash_text(self, text: str, original_question: Optional[str] = None) -> str:
        primary_input = original_question if original_question and original_question.strip() else text
        normalized = self.normalize_text(primary_input)
        hash_input = f"{self.engine}|{self.voice_id}|{self.output_format}|{normalized}"
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    def get_cache_path(self, text: str, original_question: Optional[str] = None) -> Path:
        file_hash = self.hash_text(text, original_question=original_question)
        return self.cache_dir / f"{file_hash}.{self.output_format}"

    def get_audio_url(self, file_path: Path) -> str:
        return f"{self.public_audio_base_url}/{file_path.name}"

    def synthesize(self, text: str, original_question: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns cached audio if available.
        Otherwise calls Amazon Polly, stores MP3 locally, and returns metadata.
        """
        if not text or not text.strip():
            return {
                "enabled": False,
                "cached": False,
                "audio_url": None,
                "error": "Empty text",
            }

        audio_path = self.get_cache_path(text, original_question=original_question)

        if audio_path.exists() and audio_path.stat().st_size > 0:
            return {
                "enabled": True,
                "cached": True,
                "audio_url": self.get_audio_url(audio_path),
                "file_path": str(audio_path),
                "voice": self.voice_id,
                "engine": self.engine,
            }

        try:
            response = self.client.synthesize_speech(
                Text=text,
                OutputFormat=self.output_format,
                VoiceId=self.voice_id,
                Engine=self.engine,
                SampleRate=self.sample_rate,
            )

            audio_stream = response.get("AudioStream")
            if audio_stream is None:
                raise RuntimeError("Amazon Polly returned no AudioStream")

            with open(audio_path, "wb") as f:
                f.write(audio_stream.read())

            return {
                "enabled": True,
                "cached": False,
                "audio_url": self.get_audio_url(audio_path),
                "file_path": str(audio_path),
                "voice": self.voice_id,
                "engine": self.engine,
            }

        except (BotoCoreError, ClientError, RuntimeError) as e:
            return {
                "enabled": False,
                "cached": False,
                "audio_url": None,
                "error": str(e),
            }