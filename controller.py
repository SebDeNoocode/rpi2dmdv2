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
from typing import Optional, List
from pathlib import Path

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

# Configuration de la matrice LED
MATRIX_CONFIG = {
    'rows': 64,
    'cols': 128,
    'chain_length': 5,
    'parallel': 1,
    'hardware_mapping': 'regular',
    'brightness': 50,
    'gpio_slowdown': 4,  # Raspberry Pi 4
}

# Dimensions totales de l'affichage
DISPLAY_WIDTH = MATRIX_CONFIG['cols'] * MATRIX_CONFIG['chain_length']  # 640
DISPLAY_HEIGHT = MATRIX_CONFIG['rows']  # 64

# Chemins des assets
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / 'assets'
IMAGES_DIR = ASSETS_DIR / 'images'
VIDEOS_DIR = ASSETS_DIR / 'videos'
FONTS_DIR = ASSETS_DIR / 'fonts'


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
            '/clear': 'GET - Effacer l\'écran',
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

    # Démarrer le serveur Flask
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
