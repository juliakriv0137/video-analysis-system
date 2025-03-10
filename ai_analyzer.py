import os
import base64
from openai import OpenAI
import logging
import time
import json

class AIAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
        self.base_delay = 5  # Базовая задержка между запросами

    def analyze_image(self, image_path):
        """Analyze image using OpenAI Vision API with enhanced prompting"""
        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    delay = self.base_delay * (2 ** attempt)
                    self.logger.info(f"Waiting {delay} seconds before API call (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)

                    response = self.client.chat.completions.create(
                        model="gpt-4o",  # newest OpenAI model released May 13, 2024
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": """Проанализируйте этот кадр из видео и предоставьте результат в формате JSON со следующими полями:
                                        {
                                            "scene_description": "описание сцены",
                                            "main_objects": ["список основных объектов"],
                                            "actions": ["список действий"],
                                            "detected_text": "замеченный текст",
                                            "mood": "настроение сцены"
                                        }"""
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        }
                                    }
                                ]
                            }
                        ],
                        response_format={"type": "json_object"}
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    error_msg = str(e)
                    if "insufficient_quota" in error_msg:
                        return json.dumps({
                            "error": "API quota exceeded",
                            "message": "Недостаточно квоты API для анализа изображения",
                            "technical_details": error_msg
                        })
                    self.logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    if attempt == max_retries - 1:
                        raise
        except Exception as e:
            self.logger.error(f"Error analyzing image: {str(e)}")
            return json.dumps({
                "error": "Analysis failed",
                "message": "Не удалось проанализировать изображение",
                "technical_details": str(e)
            })

    def transcribe_audio(self, audio_path):
        """Transcribe audio using Whisper API"""
        try:
            time.sleep(self.base_delay)
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            return response
        except Exception as e:
            error_msg = str(e)
            if "insufficient_quota" in error_msg:
                return "Ошибка: превышен лимит API для транскрипции"
            self.logger.error(f"Error transcribing audio: {error_msg}")
            return "Ошибка при транскрипции аудио"

    def generate_summary(self, results):
        """Generate comprehensive analysis summary using GPT-4"""
        try:
            time.sleep(self.base_delay)
            prompt = self._create_summary_prompt(results)
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Создайте подробный анализ видео в формате JSON со следующей структурой:
                        {
                            "title": "краткое название или тема видео",
                            "duration": "примерная длительность видео",
                            "chronological_events": [
                                {
                                    "timestamp": "временная метка",
                                    "description": "описание события"
                                }
                            ],
                            "main_elements": {
                                "characters": ["люди или персонажи в видео"],
                                "objects": ["ключевые объекты"],
                                "locations": ["места действия"],
                                "actions": ["основные действия"]
                            },
                            "audio_analysis": {
                                "speech_content": "содержание речи",
                                "background_sounds": "фоновые звуки",
                                "music": "описание музыки, если есть"
                            },
                            "technical_aspects": {
                                "video_quality": "качество видео",
                                "lighting": "освещение",
                                "camera_work": "работа камеры"
                            },
                            "overall_mood": "общее настроение",
                            "purpose": "предполагаемая цель видео",
                            "detailed_summary": "подробное текстовое описание всего происходящего в видео"
                        }"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "insufficient_quota" in error_msg:
                return json.dumps({
                    "error": "API quota exceeded",
                    "message": "Недостаточно квоты API для создания итогового описания"
                })
            return json.dumps({
                "error": "Summary generation failed",
                "message": "Не удалось создать итоговое описание",
                "technical_details": error_msg
            })

    def _create_summary_prompt(self, results):
        """Create enhanced prompt for summary generation"""
        prompt = "Проанализируйте следующее содержание видео для создания JSON-анализа:\n\n"

        if results.get('frames'):
            prompt += "Ключевые кадры:\n"
            for frame in results['frames']:
                prompt += f"Момент {frame['timestamp']:.1f}с:\n"
                if isinstance(frame['vision_analysis'], str):
                    try:
                        analysis = json.loads(frame['vision_analysis'])
                        if 'error' not in analysis:
                            prompt += f"{json.dumps(analysis, ensure_ascii=False, indent=2)}\n"
                    except:
                        prompt += f"{frame['vision_analysis']}\n"
                if frame.get('ocr_text'):
                    prompt += f"Найденный текст: {frame['ocr_text']}\n"

        if results.get('audio_analysis'):
            prompt += f"\nАудио содержание:\n{results['audio_analysis'].get('transcription', '')}\n"
            if results['audio_analysis'].get('music_detection', {}).get('has_music'):
                prompt += "В видео обнаружена музыка.\n"

        return prompt