import os
import io
import base64
import numpy as np
import contextlib
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt


def audio_stats(filepath, waveform_cache):
    """
    Calculate waveform, max amplitude, average amplitude, LUFS, extension, and filepath for an audio file.
    Uses cache if available.
    Returns (audio, max_amp, avg_amp, lufs, ext, filepath)
    """
    if filepath in waveform_cache:
        return waveform_cache[filepath]
    ext = os.path.splitext(filepath)[1].lower()
    try:
        audio = None
        framerate = 44100
        if ext == ".wav":
            with contextlib.closing(wave.open(filepath, "rb")) as wf:
                n_frames = wf.getnframes()
                framerate = wf.getframerate()
                frames = wf.readframes(n_frames)
                sampwidth = wf.getsampwidth()
                nchannels = wf.getnchannels()
                if sampwidth == 2:
                    dtype = np.int16
                elif sampwidth == 1:
                    dtype = np.uint8
                else:
                    dtype = np.int16
                audio = np.frombuffer(frames, dtype=dtype)
                if nchannels > 1:
                    audio = audio.reshape(-1, nchannels).mean(axis=1)
                # Normalize
                if dtype == np.int16:
                    audio = audio.astype(np.float32) / 32768.0
                elif dtype == np.uint8:
                    audio = (audio.astype(np.float32) - 128) / 128.0
        elif ext == ".mp3":
            try:
                from pydub import AudioSegment

                audio_seg = AudioSegment.from_file(filepath, format="mp3")
                samples = np.array(audio_seg.get_array_of_samples())
                if audio_seg.channels > 1:
                    samples = samples.reshape((-1, audio_seg.channels)).mean(axis=1)
                audio = samples.astype(np.float32)
                # Normalize
                if audio_seg.sample_width == 2:
                    audio = audio / 32768.0
                elif audio_seg.sample_width == 1:
                    audio = (audio - 128) / 128.0
                framerate = audio_seg.frame_rate
            except Exception:
                try:
                    import librosa

                    audio, framerate = librosa.load(filepath, sr=None, mono=True)
                except Exception:
                    return None, None, None, None, None, None
        else:
            return None, None, None, None, None, None
        if audio is None or len(audio) == 0:
            result = (None, None, None, None, ext, filepath)
            waveform_cache[filepath] = result
            return result
        # Remove DC offset and check for silence
        audio = audio - np.mean(audio)
        if np.allclose(audio, 0):
            lufs = None
        else:
            try:
                import pyloudnorm as pyln

                meter = pyln.Meter(framerate)
                lufs = float(meter.integrated_loudness(audio))
            except Exception:
                lufs = None
        max_amp = float(np.max(np.abs(audio)))
        avg_amp = float(np.mean(np.abs(audio)))
        result = (audio, max_amp, avg_amp, lufs, ext, filepath)
        waveform_cache[filepath] = result
        return result
    except Exception:
        result = (None, None, None, None, None, None)
        waveform_cache[filepath] = result
        return result


def batch_audio_stats(files, waveform_cache, progress_callback=None):
    """
    Calculate audio stats for a list of files in parallel, updating progress via callback.
    Returns a list of results in the same order as files.
    """
    from concurrent.futures import as_completed

    stats_results = [None] * len(files)
    with ThreadPoolExecutor() as executor:
        future_to_idx = {
            executor.submit(audio_stats, f, waveform_cache): i for i, f in enumerate(files)
        }
        completed = 0
        total = len(files)
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            stats_results[idx] = future.result()
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
    return stats_results


def generate_waveform_image(
    input_path: str,
    output_path: str,
    width: int = 800,
    height: int = 100,
    color: str = "#4CAF50",
) -> None:
    """
    Generate a waveform image for an audio file.
    """
    # Use a temporary cache for this single operation
    cache = {}
    audio, max_amp, avg_amp, lufs, ext, filepath = audio_stats(input_path, cache)

    if audio is None:
        raise ValueError(f"Could not load audio from {input_path}")

    # Downsample for plotting
    max_points = width * 2  # 2 points per pixel column roughly
    n = len(audio)
    if n > max_points:
        idx = np.linspace(0, n - 1, max_points).astype(int)
        audio_plot = audio[idx]
    else:
        audio_plot = audio

    # Create plot
    # Convert hex color to matplotlib color

    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    # Remove axes
    ax.axis("off")
    # Remove margins
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    ax.plot(audio_plot, color=color, linewidth=0.5)

    # Save
    plt.savefig(output_path, format="png", transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
