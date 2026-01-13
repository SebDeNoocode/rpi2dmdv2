#!/usr/bin/env python3
"""
RPI2DMDv2 - LED Matrix Controller
Contrôleur Python pour piloter des panneaux LED HUB75 via API Flask
"""

import os
import sys
import time
import threading
import logging
import random
import yaml
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

import pytz
import requests
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import imageio

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
except ImportError:
    print("ATTENTION: rgbmatrix non installé. Mode simulation activé.")
    RGBMatrix = None
    RGBMatrixOptions = None

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RPI2DMDv2')

# Chemins de base
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / 'config.yaml'


def load_config() -> Dict[str, Any]:
    """Charge la configuration depuis le fichier config.yaml"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info("Configuration chargée depuis config.yaml")
        return config
    except FileNotFoundError:
        logger.error(f"Fichier de configuration non trouvé: {CONFIG_FILE}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Erreur lors de la lecture de la configuration: {e}")
        sys.exit(1)


# Charger la configuration
CONFIG = load_config()

# Configuration de la matrice LED (depuis config)
MATRIX_CONFIG = CONFIG['matrix']

# Dimensions totales de l'affichage
DISPLAY_WIDTH = MATRIX_CONFIG['cols'] * MATRIX_CONFIG['chain_length']
DISPLAY_HEIGHT = MATRIX_CONFIG['rows']

# Chemins des assets (depuis config)
IMAGES_DIR = BASE_DIR / CONFIG['paths']['images']
VIDEOS_DIR = BASE_DIR / CONFIG['paths']['videos']
FONTS_DIR = BASE_DIR / CONFIG['paths']['fonts']


class DisplayRenderer:
    """
    Gère le rendu sur la matrice LED avec gestion des conflits.
    Un seul rendu actif à la fois.
    """

    def __init__(self, matrix: Optional[RGBMatrix] = None):
        self.matrix = matrix
        self.current_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.simulation_mode = matrix is None

        if self.simulation_mode:
            logger.warning("Mode simulation: pas de matrice LED détectée")

    def stop_current_render(self):
        """Arrête le rendu en cours de manière propre"""
        with self.lock:
            if self.current_thread and self.current_thread.is_alive():
                logger.info("Arrêt du rendu précédent...")
                self.stop_event.set()
                self.current_thread.join(timeout=2.0)
                self.stop_event.clear()
                logger.info("Rendu précédent arrêté")

    def start_render(self, target_func, *args, **kwargs):
        """Démarre un nouveau rendu en arrêtant le précédent"""
        self.stop_current_render()

        with self.lock:
            self.current_thread = threading.Thread(
                target=target_func,
                args=args,
                kwargs=kwargs,
                daemon=True
            )
            self.current_thread.start()
            logger.info(f"Nouveau rendu démarré: {target_func.__name__}")

    def clear_display(self):
        """Efface l'écran"""
        self.stop_current_render()
        if not self.simulation_mode:
            self.matrix.Clear()
        logger.info("Écran effacé")

    def render_image(self, image_path: Path):
        """Affiche une image sur la matrice"""
        try:
            img = Image.open(image_path)

            # Redimensionner l'image si nécessaire
            if img.size != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
                logger.info(f"Redimensionnement de {img.size} vers {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
                img = img.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)

            # Convertir en RGB si nécessaire
            if img.mode != 'RGB':
                img = img.convert('RGB')

            if self.simulation_mode:
                logger.info(f"[SIMULATION] Affichage image: {image_path.name}")
                return

            # Afficher sur la matrice
            self.matrix.SetImage(img)
            logger.info(f"Image affichée: {image_path.name}")

        except Exception as e:
            logger.error(f"Erreur lors du rendu de l'image: {e}")

    def render_text_scroll(self, text: str, color: tuple = (255, 255, 255)):
        """Fait défiler du texte horizontalement"""
        try:
            # Créer une image pour le texte
            font_size = 16
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()

            # Calculer la taille du texte
            temp_img = Image.new('RGB', (1, 1))
            draw = ImageDraw.Draw(temp_img)
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # Créer l'image du texte
            text_img = Image.new('RGB', (text_width + DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
            draw = ImageDraw.Draw(text_img)

            # Centrer verticalement
            y_pos = (DISPLAY_HEIGHT - text_height) // 2
            draw.text((DISPLAY_WIDTH, y_pos), text, font=font, fill=color)

            # Faire défiler
            x_offset = 0
            while not self.stop_event.is_set():
                # Extraire la partie visible
                visible = text_img.crop((
                    x_offset,
                    0,
                    x_offset + DISPLAY_WIDTH,
                    DISPLAY_HEIGHT
                ))

                if self.simulation_mode:
                    if x_offset % 50 == 0:
                        logger.debug(f"[SIMULATION] Scroll position: {x_offset}")
                else:
                    self.matrix.SetImage(visible)

                x_offset += 2

                # Recommencer au début
                if x_offset > text_width:
                    x_offset = 0

                time.sleep(0.03)  # ~30 FPS

            logger.info("Défilement de texte terminé")

        except Exception as e:
            logger.error(f"Erreur lors du défilement de texte: {e}")

    def render_video(self, video_path: Path):
        """Lit une vidéo ou un GIF en boucle"""
        try:
            # Lire le fichier avec imageio
            reader = imageio.get_reader(video_path)
            fps = reader.get_meta_data().get('fps', 30)
            frame_delay = 1.0 / fps

            logger.info(f"Lecture vidéo: {video_path.name} à {fps} FPS")

            while not self.stop_event.is_set():
                for frame in reader:
                    if self.stop_event.is_set():
                        break

                    # Convertir le frame en Image PIL
                    img = Image.fromarray(frame)

                    # Redimensionner si nécessaire
                    if img.size != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
                        img = img.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)

                    # Convertir en RGB
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    if self.simulation_mode:
                        pass  # Pas de log pour chaque frame
                    else:
                        self.matrix.SetImage(img)

                    time.sleep(frame_delay)

                # Recommencer la vidéo (boucle)
                reader.set_image_index(0)

            reader.close()
            logger.info("Lecture vidéo terminée")

        except Exception as e:
            logger.error(f"Erreur lors de la lecture vidéo: {e}")

    def render_image_timed(self, image_path: Path, duration: float):
        """Affiche une image pendant une durée définie"""
        try:
            img = Image.open(image_path)

            # Redimensionner l'image si nécessaire
            if img.size != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
                img = img.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)

            # Convertir en RGB si nécessaire
            if img.mode != 'RGB':
                img = img.convert('RGB')

            if self.simulation_mode:
                logger.info(f"[SIMULATION] Affichage image: {image_path.name} pendant {duration}s")
            else:
                self.matrix.SetImage(img)
                logger.info(f"Image affichée: {image_path.name} pendant {duration}s")

            # Attendre la durée spécifiée
            start_time = time.time()
            while not self.stop_event.is_set() and (time.time() - start_time) < duration:
                time.sleep(0.1)

        except Exception as e:
            logger.error(f"Erreur lors du rendu de l'image: {e}")

    def render_video_timed(self, video_path: Path, duration: float):
        """Lit une vidéo ou un GIF pendant une durée définie"""
        try:
            # Lire le fichier avec imageio
            reader = imageio.get_reader(video_path)
            fps = reader.get_meta_data().get('fps', 30)
            frame_delay = 1.0 / fps

            logger.info(f"Lecture vidéo: {video_path.name} pendant {duration}s à {fps} FPS")

            start_time = time.time()
            while not self.stop_event.is_set() and (time.time() - start_time) < duration:
                for frame in reader:
                    if self.stop_event.is_set() or (time.time() - start_time) >= duration:
                        break

                    # Convertir le frame en Image PIL
                    img = Image.fromarray(frame)

                    # Redimensionner si nécessaire
                    if img.size != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
                        img = img.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)

                    # Convertir en RGB
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    if not self.simulation_mode:
                        self.matrix.SetImage(img)

                    time.sleep(frame_delay)

                # Recommencer la vidéo si on n'a pas atteint la durée
                if (time.time() - start_time) < duration:
                    reader.set_image_index(0)

            reader.close()
            logger.info(f"Lecture vidéo terminée: {video_path.name}")

        except Exception as e:
            logger.error(f"Erreur lors de la lecture vidéo: {e}")

    def get_all_media_files(self) -> List[Path]:
        """Récupère tous les fichiers médias disponibles"""
        media_files = []

        # Extensions supportées
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}
        video_extensions = {'.gif', '.mp4', '.avi', '.mov'}

        # Scanner le dossier images
        if IMAGES_DIR.exists():
            for file in IMAGES_DIR.iterdir():
                if file.is_file() and file.suffix.lower() in image_extensions:
                    media_files.append(('image', file))

        # Scanner le dossier videos
        if VIDEOS_DIR.exists():
            for file in VIDEOS_DIR.iterdir():
                if file.is_file() and file.suffix.lower() in video_extensions:
                    media_files.append(('video', file))

        return media_files

    def render_random_media(self, interval: float = 10.0, shuffle: bool = True):
        """
        Affiche aléatoirement des médias avec un intervalle défini

        Args:
            interval: durée d'affichage de chaque média en secondes (défaut: 10s)
            shuffle: si True, mélange aléatoirement l'ordre (défaut: True)
        """
        try:
            logger.info(f"Démarrage du mode aléatoire avec intervalle de {interval}s")

            while not self.stop_event.is_set():
                # Récupérer tous les médias disponibles
                media_files = self.get_all_media_files()

                if not media_files:
                    logger.warning("Aucun média trouvé dans assets/images ou assets/videos")
                    time.sleep(5)
                    continue

                logger.info(f"{len(media_files)} médias trouvés")

                # Mélanger l'ordre si demandé
                if shuffle:
                    random.shuffle(media_files)

                # Afficher chaque média
                for media_type, media_path in media_files:
                    if self.stop_event.is_set():
                        break

                    logger.info(f"Affichage de {media_type}: {media_path.name}")

                    if media_type == 'image':
                        self.render_image_timed(media_path, interval)
                    elif media_type == 'video':
                        self.render_video_timed(media_path, interval)

            logger.info("Mode aléatoire terminé")

        except Exception as e:
            logger.error(f"Erreur dans le mode aléatoire: {e}")

    def render_clock(self, format_24h: bool = True, show_seconds: bool = True, color: tuple = (255, 255, 255)):
        """Affiche l'heure en temps réel"""
        try:
            # Récupérer la timezone depuis la config
            tz = pytz.timezone(CONFIG['location']['timezone'])

            # Charger la police
            font_path = CONFIG['fonts']['clock']
            font_size = CONFIG['fonts']['clock_size']
            try:
                font = ImageFont.truetype(font_path, font_size)
            except:
                font = ImageFont.load_default()
                logger.warning("Police horloge non trouvée, utilisation de la police par défaut")

            logger.info(f"Démarrage de l'horloge (timezone: {CONFIG['location']['timezone']})")

            while not self.stop_event.is_set():
                # Obtenir l'heure actuelle dans la timezone configurée
                now = datetime.now(tz)

                # Formater l'heure
                if format_24h:
                    if show_seconds:
                        time_str = now.strftime("%H:%M:%S")
                    else:
                        time_str = now.strftime("%H:%M")
                else:
                    if show_seconds:
                        time_str = now.strftime("%I:%M:%S %p")
                    else:
                        time_str = now.strftime("%I:%M %p")

                # Créer l'image
                img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
                draw = ImageDraw.Draw(img)

                # Calculer la position centrée
                text_bbox = draw.textbbox((0, 0), time_str, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                x_pos = (DISPLAY_WIDTH - text_width) // 2
                y_pos = (DISPLAY_HEIGHT - text_height) // 2

                # Dessiner l'heure
                draw.text((x_pos, y_pos), time_str, font=font, fill=color)

                # Afficher
                if not self.simulation_mode:
                    self.matrix.SetImage(img)
                elif self.stop_event.is_set():
                    break

                # Attendre 1 seconde (ou 10 secondes si pas de secondes)
                time.sleep(1 if show_seconds else 10)

            logger.info("Horloge arrêtée")

        except Exception as e:
            logger.error(f"Erreur lors de l'affichage de l'horloge: {e}")

    def render_date(self, date_format: str = "%d/%m/%Y", color: tuple = (255, 255, 255)):
        """Affiche la date statique"""
        try:
            # Récupérer la timezone depuis la config
            tz = pytz.timezone(CONFIG['location']['timezone'])
            now = datetime.now(tz)
            date_str = now.strftime(date_format)

            # Charger la police
            font_path = CONFIG['fonts']['date']
            font_size = CONFIG['fonts']['date_size']
            try:
                font = ImageFont.truetype(font_path, font_size)
            except:
                font = ImageFont.load_default()
                logger.warning("Police date non trouvée, utilisation de la police par défaut")

            # Créer l'image
            img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Calculer la position centrée
            text_bbox = draw.textbbox((0, 0), date_str, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x_pos = (DISPLAY_WIDTH - text_width) // 2
            y_pos = (DISPLAY_HEIGHT - text_height) // 2

            # Dessiner la date
            draw.text((x_pos, y_pos), date_str, font=font, fill=color)

            # Afficher
            if self.simulation_mode:
                logger.info(f"[SIMULATION] Affichage date: {date_str}")
            else:
                self.matrix.SetImage(img)
                logger.info(f"Date affichée: {date_str}")

        except Exception as e:
            logger.error(f"Erreur lors de l'affichage de la date: {e}")

    def render_weather(self, api_key: str):
        """Affiche les informations météo (nécessite une clé API OpenWeatherMap)"""
        try:
            if not api_key:
                logger.error("Clé API OpenWeatherMap manquante dans config.yaml")
                return

            # Récupérer les données météo
            lat = CONFIG['location']['latitude']
            lon = CONFIG['location']['longitude']
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=fr"

            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extraire les informations
            temp = round(data['main']['temp'])
            description = data['weather'][0]['description'].capitalize()
            city = data['name']

            weather_text = f"{city}: {temp}°C - {description}"

            logger.info(f"Météo récupérée: {weather_text}")

            # Afficher avec scrolling text
            self.render_text_scroll(weather_text, color=(100, 200, 255))

        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération de la météo: {e}")
        except KeyError as e:
            logger.error(f"Erreur lors du parsing des données météo: {e}")
        except Exception as e:
            logger.error(f"Erreur inattendue lors de l'affichage météo: {e}")


class BrightnessController:
    """Contrôle automatique de la luminosité selon l'horaire"""

    def __init__(self, matrix: Optional[RGBMatrix], config: Dict[str, Any]):
        self.matrix = matrix
        self.config = config
        self.enabled = config['auto_brightness']['enabled']
        self.schedule = config['auto_brightness']['schedule']
        self.current_brightness = config['matrix']['brightness']
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.simulation_mode = matrix is None

        if self.enabled and not self.simulation_mode:
            self.start()

    def start(self):
        """Démarre le contrôleur de luminosité"""
        if not self.enabled:
            logger.info("Contrôle automatique de luminosité désactivé")
            return

        self.thread = threading.Thread(target=self._brightness_loop, daemon=True)
        self.thread.start()
        logger.info("Contrôle automatique de luminosité démarré")

    def stop(self):
        """Arrête le contrôleur de luminosité"""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("Contrôle automatique de luminosité arrêté")

    def _brightness_loop(self):
        """Boucle principale de contrôle de la luminosité"""
        while not self.stop_event.is_set():
            try:
                # Obtenir l'heure actuelle
                tz = pytz.timezone(CONFIG['location']['timezone'])
                now = datetime.now(tz)
                current_time = now.strftime("%H:%M")

                # Trouver la luminosité appropriée pour l'heure actuelle
                target_brightness = self._get_brightness_for_time(current_time)

                # Changer la luminosité si nécessaire
                if target_brightness != self.current_brightness:
                    self._set_brightness(target_brightness)

                # Vérifier toutes les minutes
                time.sleep(60)

            except Exception as e:
                logger.error(f"Erreur dans la boucle de contrôle de luminosité: {e}")
                time.sleep(60)

    def _get_brightness_for_time(self, current_time: str) -> int:
        """Détermine la luminosité appropriée pour une heure donnée"""
        # Convertir l'heure actuelle en minutes depuis minuit
        current_minutes = self._time_to_minutes(current_time)

        # Trier les horaires
        sorted_schedule = sorted(self.schedule, key=lambda x: self._time_to_minutes(x['time']))

        # Trouver la plage horaire correspondante
        for i, entry in enumerate(sorted_schedule):
            entry_minutes = self._time_to_minutes(entry['time'])

            if i == len(sorted_schedule) - 1:
                # Dernier élément, comparé avec le premier
                next_entry = sorted_schedule[0]
                next_minutes = self._time_to_minutes(next_entry['time']) + 24 * 60

                if entry_minutes <= current_minutes < next_minutes:
                    return entry['brightness']
            else:
                # Comparer avec l'élément suivant
                next_entry = sorted_schedule[i + 1]
                next_minutes = self._time_to_minutes(next_entry['time'])

                if entry_minutes <= current_minutes < next_minutes:
                    return entry['brightness']

        # Par défaut, retourner la première valeur
        return sorted_schedule[0]['brightness']

    def _time_to_minutes(self, time_str: str) -> int:
        """Convertit une heure HH:MM en minutes depuis minuit"""
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes

    def _set_brightness(self, brightness: int):
        """Change la luminosité de la matrice"""
        if self.simulation_mode:
            logger.info(f"[SIMULATION] Changement de luminosité: {brightness}%")
        else:
            self.matrix.brightness = brightness
            logger.info(f"Luminosité ajustée à {brightness}%")

        self.current_brightness = brightness


def initialize_matrix() -> Optional[RGBMatrix]:
    """Initialise la matrice LED avec les paramètres configurés"""
    if RGBMatrix is None:
        logger.warning("Matrice LED non disponible - mode simulation")
        return None

    try:
        options = RGBMatrixOptions()
        options.rows = MATRIX_CONFIG['rows']
        options.cols = MATRIX_CONFIG['cols']
        options.chain_length = MATRIX_CONFIG['chain_length']
        options.parallel = MATRIX_CONFIG['parallel']
        options.hardware_mapping = MATRIX_CONFIG['hardware_mapping']
        options.brightness = MATRIX_CONFIG['brightness']
        options.gpio_slowdown = MATRIX_CONFIG['gpio_slowdown']

        # Configuration de l'ordre des couleurs LED
        if 'led_rgb_sequence' in MATRIX_CONFIG:
            options.led_rgb_sequence = MATRIX_CONFIG['led_rgb_sequence']
            logger.info(f"Séquence LED configurée: {MATRIX_CONFIG['led_rgb_sequence']}")

        # Options additionnelles pour améliorer la qualité
        options.disable_hardware_pulsing = True
        options.drop_privileges = False  # Nécessaire pour root

        matrix = RGBMatrix(options=options)
        logger.info(f"Matrice LED initialisée: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT} pixels")
        return matrix

    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la matrice: {e}")
        return None


# Initialisation de Flask et de la matrice
app = Flask(__name__)
matrix = initialize_matrix()
renderer = DisplayRenderer(matrix)
brightness_controller = BrightnessController(matrix, CONFIG)


@app.route('/')
def index():
    """Page d'accueil de l'API"""
    return jsonify({
        'name': 'RPI2DMDv2 Controller',
        'version': '1.0.0',
        'display': {
            'width': DISPLAY_WIDTH,
            'height': DISPLAY_HEIGHT,
            'panels': MATRIX_CONFIG['chain_length'],
        },
        'endpoints': {
            '/image': 'GET ?filename=example.png - Afficher une image',
            '/text': 'GET ?content=Hello+World&color=255,255,255 - Défiler du texte',
            '/video': 'GET ?filename=animation.gif - Lire une vidéo',
            '/random': 'GET ?interval=10 - Afficher aléatoirement images/vidéos avec intervalle',
            '/clock': 'GET ?format=24&seconds=true&color=255,255,255 - Afficher l\'heure',
            '/date': 'GET ?format=%d/%m/%Y&color=255,255,255 - Afficher la date',
            '/weather': 'GET - Afficher la météo (nécessite clé API)',
            '/clear': 'GET - Effacer l\'écran',
        },
        'config': {
            'location': CONFIG['location']['city'],
            'timezone': CONFIG['location']['timezone'],
            'auto_brightness': CONFIG['auto_brightness']['enabled']
        }
    })


@app.route('/image')
def display_image():
    """Affiche une image sur la matrice"""
    filename = request.args.get('filename')

    if not filename:
        return jsonify({'error': 'Paramètre filename manquant'}), 400

    image_path = IMAGES_DIR / filename

    if not image_path.exists():
        return jsonify({'error': f'Image non trouvée: {filename}'}), 404

    renderer.start_render(renderer.render_image, image_path)

    return jsonify({
        'status': 'success',
        'action': 'image_display',
        'filename': filename
    })


@app.route('/text')
def display_text():
    """Fait défiler du texte sur la matrice"""
    content = request.args.get('content')
    color_str = request.args.get('color', '255,255,255')

    if not content:
        return jsonify({'error': 'Paramètre content manquant'}), 400

    try:
        color = tuple(map(int, color_str.split(',')))
        if len(color) != 3:
            raise ValueError
    except:
        return jsonify({'error': 'Couleur invalide (format: R,G,B)'}), 400

    renderer.start_render(renderer.render_text_scroll, content, color)

    return jsonify({
        'status': 'success',
        'action': 'text_scroll',
        'content': content,
        'color': color
    })


@app.route('/video')
def display_video():
    """Lit une vidéo ou un GIF sur la matrice"""
    filename = request.args.get('filename')

    if not filename:
        return jsonify({'error': 'Paramètre filename manquant'}), 400

    video_path = VIDEOS_DIR / filename

    if not video_path.exists():
        return jsonify({'error': f'Vidéo non trouvée: {filename}'}), 404

    renderer.start_render(renderer.render_video, video_path)

    return jsonify({
        'status': 'success',
        'action': 'video_playback',
        'filename': filename
    })


@app.route('/random')
def display_random():
    """Affiche aléatoirement des images et vidéos avec un intervalle défini"""
    interval_str = request.args.get('interval', '10')

    try:
        interval = float(interval_str)
        if interval < 1:
            return jsonify({'error': 'L\'intervalle doit être >= 1 seconde'}), 400
    except ValueError:
        return jsonify({'error': 'Intervalle invalide (doit être un nombre)'}), 400

    # Vérifier qu'il y a des médias disponibles
    media_files = renderer.get_all_media_files()
    if not media_files:
        return jsonify({
            'error': 'Aucun média trouvé',
            'help': 'Placez des images dans assets/images/ ou des vidéos dans assets/videos/'
        }), 404

    renderer.start_render(renderer.render_random_media, interval)

    return jsonify({
        'status': 'success',
        'action': 'random_media',
        'interval': interval,
        'media_count': len(media_files)
    })


@app.route('/clock')
def display_clock():
    """Affiche l'heure en temps réel"""
    # Paramètres depuis la requête ou config
    format_str = request.args.get('format', '24')
    seconds_str = request.args.get('seconds', 'true')
    color_str = request.args.get('color', None)

    # Format 24h ou 12h
    format_24h = format_str == '24'

    # Afficher les secondes
    show_seconds = seconds_str.lower() in ['true', '1', 'yes']

    # Couleur
    if color_str:
        try:
            color = tuple(map(int, color_str.split(',')))
            if len(color) != 3:
                raise ValueError
        except:
            return jsonify({'error': 'Couleur invalide (format: R,G,B)'}), 400
    else:
        color = tuple(CONFIG['clock']['color'])

    renderer.start_render(renderer.render_clock, format_24h, show_seconds, color)

    return jsonify({
        'status': 'success',
        'action': 'clock',
        'format': '24h' if format_24h else '12h',
        'seconds': show_seconds,
        'color': color
    })


@app.route('/date')
def display_date():
    """Affiche la date"""
    # Paramètres depuis la requête ou config
    date_format = request.args.get('format', CONFIG['clock']['date_format'])
    color_str = request.args.get('color', None)

    # Couleur
    if color_str:
        try:
            color = tuple(map(int, color_str.split(',')))
            if len(color) != 3:
                raise ValueError
        except:
            return jsonify({'error': 'Couleur invalide (format: R,G,B)'}), 400
    else:
        color = tuple(CONFIG['clock']['color'])

    renderer.start_render(renderer.render_date, date_format, color)

    # Obtenir la date pour la réponse
    tz = pytz.timezone(CONFIG['location']['timezone'])
    now = datetime.now(tz)
    date_str = now.strftime(date_format)

    return jsonify({
        'status': 'success',
        'action': 'date',
        'date': date_str,
        'format': date_format,
        'color': color
    })


@app.route('/weather')
def display_weather():
    """Affiche la météo"""
    api_key = CONFIG['api_keys'].get('openweathermap', '')

    if not api_key:
        return jsonify({
            'error': 'Clé API OpenWeatherMap manquante',
            'help': 'Configurez la clé API dans config.yaml sous api_keys.openweathermap'
        }), 400

    renderer.start_render(renderer.render_weather, api_key)

    return jsonify({
        'status': 'success',
        'action': 'weather',
        'location': CONFIG['location']['city']
    })


@app.route('/clear')
def clear_display():
    """Efface l'écran"""
    renderer.clear_display()

    return jsonify({
        'status': 'success',
        'action': 'clear'
    })


if __name__ == '__main__':
    # Vérifier que le script est exécuté en root
    if os.geteuid() != 0 and not renderer.simulation_mode:
        logger.error("Ce script doit être exécuté en root (sudo)")
        sys.exit(1)

    logger.info("Démarrage du serveur RPI2DMDv2...")
    logger.info(f"Affichage: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT} pixels")
    logger.info(f"Localisation: {CONFIG['location']['city']} ({CONFIG['location']['timezone']})")
    logger.info(f"Luminosité auto: {'Activée' if CONFIG['auto_brightness']['enabled'] else 'Désactivée'}")

    # Démarrer le serveur Flask
    server_config = CONFIG['server']
    app.run(
        host=server_config['host'],
        port=server_config['port'],
        debug=server_config['debug'],
        threaded=True
    )
