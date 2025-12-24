"""
Audio Processor Service.

Wraps the AudioNormalizer and provides audio processing capabilities.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Callable

from loguru import logger

from yoto_up.normalization import AudioNormalizer


class AudioProcessorService:
    """
    Service for audio processing operations.
    
    Provides normalization, trimming, and waveform generation.
    """
    
    def __init__(
        self,
        target_level: float = -23.0,
        true_peak: float = -1.0,
    ) -> None:
        self.target_level = target_level
        self.true_peak = true_peak
        self._temp_dir = Path(tempfile.gettempdir()) / "yoto_up_audio"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
    
    def normalize(
        self,
        input_paths: List[str],
        output_dir: Optional[str] = None,
        batch_mode: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> List[str]:
        """
        Normalize audio files.
        
        Args:
            input_paths: List of paths to audio files.
            output_dir: Directory for normalized files. Uses temp dir if not specified.
            batch_mode: If True, analyze all files together for consistent loudness.
            progress_callback: Optional callback for progress updates (message, fraction).
        
        Returns:
            List of paths to normalized files.
        """
        if not input_paths:
            return []
        
        if output_dir is None:
            output_dir = str(self._temp_dir / "normalized")
        
        os.makedirs(output_dir, exist_ok=True)
        
        normalizer = AudioNormalizer(
            target_level=self.target_level,
            true_peak=self.true_peak,
            batch_mode=batch_mode,
        )
        
        try:
            return normalizer.normalize(
                input_paths=input_paths,
                output_dir=output_dir,
                progress_callback=progress_callback,
            )
        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            raise
    
    def trim_silence(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        threshold_db: float = -40.0,
        min_silence_duration: float = 0.5,
    ) -> str:
        """
        Trim silence from the beginning and end of an audio file.
        
        Args:
            input_path: Path to the audio file.
            output_path: Output path. Uses temp file if not specified.
            threshold_db: Silence threshold in dB.
            min_silence_duration: Minimum silence duration in seconds.
        
        Returns:
            Path to trimmed file.
        """
        try:
            from pydub import AudioSegment
            from pydub.silence import detect_leading_silence
        except ImportError:
            logger.warning("pydub not available for silence trimming")
            return input_path
        
        if output_path is None:
            ext = Path(input_path).suffix
            output_path = str(self._temp_dir / f"trimmed_{Path(input_path).stem}{ext}")
        
        try:
            audio = AudioSegment.from_file(input_path)
            
            # Detect and trim leading/trailing silence
            start_trim = detect_leading_silence(audio, silence_threshold=threshold_db)
            end_trim = detect_leading_silence(audio.reverse(), silence_threshold=threshold_db)
            
            trimmed = audio[start_trim:len(audio) - end_trim]
            
            # Export with appropriate format
            ext = Path(output_path).suffix.lower()
            if ext == ".mp3":
                trimmed.export(output_path, format="mp3")
            elif ext in (".m4a", ".aac"):
                trimmed.export(output_path, format="mp4")
            else:
                trimmed.export(output_path, format="wav")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Silence trimming failed: {e}")
            return input_path
    
    def generate_waveform(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        width: int = 800,
        height: int = 100,
        color: str = "#4CAF50",
    ) -> Optional[str]:
        """
        Generate a waveform image for an audio file.
        
        Args:
            input_path: Path to the audio file.
            output_path: Output path for PNG. Uses temp file if not specified.
            width: Image width in pixels.
            height: Image height in pixels.
            color: Waveform color.
        
        Returns:
            Path to waveform image, or None if generation failed.
        """
        try:
            from yoto_up.waveform_utils import generate_waveform_image
        except ImportError:
            logger.warning("waveform_utils not available")
            return None
        
        if output_path is None:
            output_path = str(self._temp_dir / f"waveform_{Path(input_path).stem}.png")
        
        try:
            generate_waveform_image(
                input_path=input_path,
                output_path=output_path,
                width=width,
                height=height,
                color=color,
            )
            return output_path
            
        except Exception as e:
            logger.error(f"Waveform generation failed: {e}")
            return None
    
    def cleanup_temp_files(self):
        """Clean up temporary files."""
        import shutil
        try:
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir)
                self._temp_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {e}")
