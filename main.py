import sys
import json
import logging
from video_processor import VideoProcessor
from ai_analyzer import AIAnalyzer
import time
import os
import shutil
import zipfile
from datetime import datetime
from github_publisher import publish_to_github

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_results_archive(results, output_dir, video_metadata=None):
    """Create archive with analysis results"""
    try:
        # Create archive directory
        archive_dir = os.path.join(output_dir, 'analysis_results')
        os.makedirs(archive_dir, exist_ok=True)

        # Save analysis results as JSON
        results_file = os.path.join(archive_dir, 'analysis.json')
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # Create README
        readme_content = f"""# Результаты анализа видео
Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Структура архива:
- all_frames/ - все кадры из видео
- analysis.json - полные результаты анализа с детальным описанием
- README.md - этот файл

## Информация о видео:
- Длительность: {video_metadata.get('duration', 'Не определена')} секунд
- Разрешение: {video_metadata.get('resolution', 'Не определено')}
- Формат: {video_metadata.get('format', 'Не определен')}

## Статистика анализа:
- Количество извлеченных кадров: {len(results.get('all_frames_info', []))}
- Количество ключевых кадров: {len(results.get('frames', []))}
- Наличие аудио: {"Да" if results.get('audio_analysis') else "Нет"}
- Обнаружена музыка: {"Да" if results.get('audio_analysis', {}).get('music_detection', {}).get('has_music') else "Нет"}

## Основное содержание:
{results.get('summary', 'Анализ не удался')}
"""

        readme_file = os.path.join(archive_dir, 'README.md')
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)

        # Create ZIP archive
        zip_path = os.path.join(output_dir, 'video_analysis.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add frames directory
            frames_dir = os.path.join(output_dir, 'all_frames')
            for root, _, files in os.walk(frames_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_path = os.path.join('all_frames', file)
                    zipf.write(file_path, arc_path)

            # Add analysis results and README
            zipf.write(results_file, 'analysis.json')
            zipf.write(readme_file, 'README.md')

        return zip_path

    except Exception as e:
        logger.error(f"Error creating archive: {str(e)}")
        raise

def analyze_video(url, publish=False):
    """Analyze video from URL and print results"""
    try:
        # Initialize processors
        video_processor = VideoProcessor(temp_dir='temp')
        ai_analyzer = AIAnalyzer()

        # Create output directory for frames
        output_dir = os.path.join('output', time.strftime('%Y%m%d_%H%M%S'))
        os.makedirs(output_dir, exist_ok=True)

        print("\nЗагрузка видео...")
        video_path = video_processor.download_video(url)
        print("✅ Видео успешно загружено")

        # Get video metadata
        video_metadata = video_processor.get_video_metadata(video_path)
        print("\n📋 Информация о видео:")
        print(f"Длительность: {video_metadata.get('duration', 'Не определена')} секунд")
        print(f"Разрешение: {video_metadata.get('resolution', 'Не определено')}")
        print(f"Формат: {video_metadata.get('format', 'Не определен')}")

        # Extract all frames first
        print("\nСохранение всех кадров...")
        all_frames = video_processor.extract_all_frames(video_path, output_dir, fps=1)
        print(f"✅ Сохранено {len(all_frames)} кадров в директорию: {os.path.join(output_dir, 'all_frames')}")

        print("\nИзвлечение ключевых кадров для анализа...")
        frames = video_processor.extract_frames(video_path)
        print(f"✅ Извлечено {len(frames)} ключевых кадров")

        print("\nАнализ содержания...")
        results = {
            'frames': [],
            'audio_analysis': None,
            'all_frames_info': []  # Добавляем информацию о всех кадрах
        }

        # Process all frames
        print("\n🔄 Анализ всех кадров для создания хронологии...")
        for frame_info in all_frames:
            frame_data = {
                'timestamp': frame_info['timestamp'],
                'filename': frame_info['filename'],
                'ocr_text': video_processor.perform_ocr(frame_info['path'])
            }
            results['all_frames_info'].append(frame_data)

        # Process key frames
        for i, frame in enumerate(frames, 1):
            print(f"\n🔄 Детальный анализ ключевого кадра {i}/{len(frames)}...")
            frame_analysis = {
                'timestamp': frame['timestamp'],
                'ocr_text': video_processor.perform_ocr(frame['path']),
                'vision_analysis': ai_analyzer.analyze_image(frame['path'])
            }
            results['frames'].append(frame_analysis)
            print(f"✅ Кадр {i} проанализирован")

        # Process audio
        print("\nАнализ аудио...")
        audio_path = video_processor.extract_audio(video_path)
        results['audio_analysis'] = {
            'transcription': ai_analyzer.transcribe_audio(audio_path),
            'music_detection': video_processor.detect_music(audio_path)
        }
        print("✅ Аудио проанализировано")

        # Generate summary
        print("\nСоздание детального описания...")
        results['summary'] = ai_analyzer.generate_summary(results)
        print("✅ Итоговое описание создано")

        # Print results in a readable format
        print("\n=== ДЕТАЛЬНЫЙ АНАЛИЗ ВИДЕО ===\n")

        # Print summary if available
        try:
            summary = json.loads(results['summary'])
            if 'error' not in summary:
                print("📝 ОБЩАЯ ИНФОРМАЦИЯ:")
                print(f"Название: {summary.get('title', 'Не указано')}")
                print(f"Длительность: {summary.get('duration', 'Не указана')}")
                print(f"Цель видео: {summary.get('purpose', 'Не указана')}")
                print("\n🎥 ТЕХНИЧЕСКИЕ АСПЕКТЫ:")
                tech = summary.get('technical_aspects', {})
                print(f"Качество видео: {tech.get('video_quality', 'Не указано')}")
                print(f"Освещение: {tech.get('lighting', 'Не указано')}")
                print(f"Работа камеры: {tech.get('camera_work', 'Не указано')}")
                print("\n👥 ОСНОВНЫЕ ЭЛЕМЕНТЫ:")
                main = summary.get('main_elements', {})
                print(f"Персонажи: {', '.join(main.get('characters', ['Не указаны']))}")
                print(f"Объекты: {', '.join(main.get('objects', ['Не указаны']))}")
                print(f"Локации: {', '.join(main.get('locations', ['Не указаны']))}")
                print(f"Действия: {', '.join(main.get('actions', ['Не указаны']))}")
                print("\n⏱️ ХРОНОЛОГИЯ СОБЫТИЙ:")
                for event in summary.get('chronological_events', []):
                    print(f"{event['timestamp']}: {event['description']}")
                print("\n🔊 АУДИО АНАЛИЗ:")
                audio = summary.get('audio_analysis', {})
                print(f"Речь: {audio.get('speech_content', 'Не обнаружена')}")
                print(f"Фоновые звуки: {audio.get('background_sounds', 'Не обнаружены')}")
                print(f"Музыка: {audio.get('music', 'Не обнаружена')}")
                print("\n📋 ДЕТАЛЬНОЕ ОПИСАНИЕ:")
                print(summary.get('detailed_summary', 'Не создано'))
            else:
                print("❌ Ошибка при создании итогового описания:")
                print(json.dumps(summary, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Ошибка при обработке итогового описания: {str(e)}")
            print("❌ Ошибка при обработке итогового описания")

        # Create archive with results
        print("\nСоздание архива с результатами анализа...")
        zip_path = create_results_archive(results, output_dir, video_metadata)
        print(f"✅ Архив создан: {zip_path}")

        # Cleanup
        video_processor.cleanup()
        print(f"\n✅ Анализ завершен! Все результаты доступны в архиве: {zip_path}")

        # Publish to GitHub if requested
        if publish:
            try:
                print("\nПубликация кода на GitHub...")
                repo_url = publish_to_github()
                print(f"✅ Код опубликован на GitHub: {repo_url}")
            except Exception as e:
                logger.error(f"Ошибка при публикации на GitHub: {str(e)}")
                print("❌ Ошибка при публикации на GitHub")

    except Exception as e:
        logger.error(f"Ошибка при анализе видео: {str(e)}")
        print(f"\n❌ Ошибка: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python main.py <video_url> [--publish]")
        sys.exit(1)

    publish = "--publish" in sys.argv
    video_url = sys.argv[1]
    analyze_video(video_url, publish)