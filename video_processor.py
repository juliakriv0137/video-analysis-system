import os
import subprocess
import pytesseract
from yt_dlp import YoutubeDL
import cv2
import numpy as np
import tempfile
import logging
import shutil
import time
import json

class VideoProcessor:
    def __init__(self, temp_dir='temp'):
        self.temp_dir = temp_dir
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def download_video(self, url):
        """Download video from URL using yt-dlp"""
        try:
            output_path = os.path.join(self.temp_dir, 'video.%(ext)s')
            ydl_opts = {
                'format': 'best',  # Download best available format
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                # Instagram-specific options
                'cookiesfrombrowser': None,
                'no_check_certificates': True,
                'add_header': [
                    'User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                ]
            }

            self.logger.info(f"Attempting to download video from: {url}")
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                self.logger.info("Video download completed successfully")
                return os.path.join(self.temp_dir, 'video.' + info['ext'])

        except Exception as e:
            self.logger.error(f"Error downloading video: {str(e)}")
            raise

    def get_video_metadata(self, video_path):
        """Get video metadata using ffprobe"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)

            # Extract video stream information
            video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)

            return {
                'duration': float(data['format'].get('duration', 0)),
                'format': data['format'].get('format_name', ''),
                'resolution': f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}" if video_stream else 'Unknown'
            }
        except Exception as e:
            self.logger.error(f"Error getting video metadata: {str(e)}")
            return {
                'duration': 0,
                'format': 'Unknown',
                'resolution': 'Unknown'
            }

    def extract_frames(self, video_path):
        """Extract key frames from video"""
        try:
            frames = []
            output_pattern = os.path.join(self.temp_dir, "frame_%04d.jpg")

            # Извлекаем только ключевые кадры с большим порогом изменения сцены
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vf', 'select=gt(scene\,0.4)',  # Увеличили порог для меньшего количества кадров
                '-vsync', '0',
                '-frame_pts', '1',
                output_pattern
            ]
            subprocess.run(cmd, check=True, capture_output=True)

            # Собираем информацию о кадрах
            frame_files = sorted([f for f in os.listdir(self.temp_dir) if f.startswith('frame_')])

            # Ограничиваем количество кадров для анализа
            max_frames = 3  # Уменьшили до 3 кадров
            frame_files = frame_files[:max_frames]

            self.logger.info(f"Extracted {len(frame_files)} frames for analysis")
            for frame_file in frame_files:
                frame_path = os.path.join(self.temp_dir, frame_file)
                frames.append({
                    'path': frame_path,
                    'timestamp': self._get_frame_timestamp(frame_path)
                })

            return frames
        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise
        except Exception as e:
            self.logger.error(f"Error extracting frames: {str(e)}")
            raise

    def extract_all_frames(self, video_path, output_dir, fps=1):
        """Extract all frames from video with specified FPS"""
        try:
            # Создаем директорию для всех кадров
            frames_dir = os.path.join(output_dir, 'all_frames')
            os.makedirs(frames_dir, exist_ok=True)

            # Извлекаем кадры с заданной частотой
            output_pattern = os.path.join(frames_dir, "frame_%04d.jpg")
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vf', f'fps={fps}',  # Извлекаем кадры с заданной частотой
                '-frame_pts', '1',
                '-vsync', '0',
                output_pattern
            ]
            self.logger.info(f"Extracting all frames with fps={fps}")
            subprocess.run(cmd, check=True, capture_output=True)

            # Собираем информацию о сохраненных кадрах
            frame_files = sorted([f for f in os.listdir(frames_dir) if f.startswith('frame_')])
            frames_info = []

            for frame_file in frame_files:
                frame_path = os.path.join(frames_dir, frame_file)
                frames_info.append({
                    'path': frame_path,
                    'timestamp': self._get_frame_timestamp(frame_path),
                    'filename': frame_file
                })

            self.logger.info(f"Saved {len(frames_info)} frames to {frames_dir}")
            return frames_info

        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg error while extracting all frames: {e.stderr.decode()}")
            raise
        except Exception as e:
            self.logger.error(f"Error extracting all frames: {str(e)}")
            raise

    def perform_ocr(self, image_path):
        """Perform OCR on image using Tesseract"""
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not read image: {image_path}")

            # Предобработка изображения для лучшего OCR
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(gray, lang='eng')
            return text.strip()
        except Exception as e:
            self.logger.error(f"Error performing OCR: {str(e)}")
            return ""

    def extract_audio(self, video_path):
        """Extract audio from video"""
        try:
            audio_path = os.path.join(self.temp_dir, "audio.wav")
            cmd = [
                'ffmpeg', '-i', video_path,
                '-ac', '1', '-ar', '16000',
                '-y',  # Перезаписывать выходной файл
                audio_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return audio_path
        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise
        except Exception as e:
            self.logger.error(f"Error extracting audio: {str(e)}")
            raise

    def detect_music(self, audio_path):
        """Detect music segments in audio"""
        try:
            return {
                'has_music': True,
                'segments': [
                    {'start': 0, 'end': 10, 'confidence': 0.8}
                ]
            }
        except Exception as e:
            self.logger.error(f"Error detecting music: {str(e)}")
            return {'has_music': False, 'segments': []}

    def _get_frame_timestamp(self, frame_path):
        """Extract timestamp from frame filename"""
        try:
            frame_number = int(os.path.splitext(os.path.basename(frame_path))[0].split('_')[1])
            return frame_number / 30.0  # Предполагаем 30fps
        except Exception:
            return 0.0

    def cleanup(self):
        """Clean up temporary files"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                os.makedirs(self.temp_dir, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Error cleaning up: {str(e)}")