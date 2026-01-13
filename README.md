# 🎛️ RPI2DMDv2

**Contrôleur Python pour piloter des panneaux LED HUB75 via API HTTP**

RPI2DMDv2 est un projet open-source qui transforme votre Raspberry Pi en serveur d'affichage LED contrôlable à distance. Basé sur la librairie [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) (Hzeller) et Flask, il permet de piloter un écran LED géant via des commandes HTTP simples.

---

## 🎯 Objectif

Créer une couche d'abstraction entre :
- des commandes simples (HTTP, Stream Deck, scripts, navigateur web)
- et la complexité temps réel du hardware LED (C++ / GPIO)

Le Raspberry Pi devient un objet connecté pilotable à distance, sans interaction SSH.

---

## 🧩 Matériel requis

- **Raspberry Pi 4** (recommandé)
- **5 panneaux LED HUB75 P2.5**
  - Résolution par panneau : 128 × 64 pixels
  - Branchement : daisy-chain (en série) sur une seule ligne
  - Résolution totale : **640 × 64 pixels**
- **HAT GPIO** (type Adafruit / regular mapping)
- **Alimentation suffisante** pour les panneaux LED (5V, calculer selon le nombre de pixels)

---

## 📦 Installation

### 1️⃣ Prérequis système

Installer les dépendances système nécessaires :

```bash
sudo apt-get update
sudo apt-get install -y python3-dev python3-pip git
```

### 2️⃣ Installer rpi-rgb-led-matrix

Cloner et compiler la librairie Hzeller :

```bash
cd ~
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
cd rpi-rgb-led-matrix
make -C examples-api-use
```

Installer les bindings Python :

```bash
cd bindings/python
sudo pip3 install -e .
```

### 3️⃣ Cloner RPI2DMDv2

```bash
cd ~
git clone https://github.com/SebDeNoocode/rpi2dmdv2.git
cd rpi2dmdv2
```

### 4️⃣ Installer les dépendances Python

```bash
sudo pip3 install -r requirements.txt
```

---

## 🚀 Utilisation

### Démarrer le serveur

Le script doit être exécuté avec les privilèges root :

```bash
sudo python3 controller.py
```

Le serveur démarre sur le port 5000 et écoute sur toutes les interfaces réseau (`0.0.0.0`).

### Mode simulation

Si la librairie `rgbmatrix` n'est pas installée, le serveur démarre en **mode simulation** pour tester l'API sans hardware.

---

## 🌐 API HTTP

### Page d'accueil

```bash
GET http://<IP_RASPBERRY>:5000/
```

Retourne les informations sur l'API et les endpoints disponibles.

---

### 📷 Afficher une image

```bash
GET http://<IP_RASPBERRY>:5000/image?filename=example.png
```

**Paramètres :**
- `filename` : nom du fichier (dans `assets/images/`)

**Formats supportés :** PNG, JPG, JPEG, BMP

L'image est automatiquement redimensionnée à 640×64 pixels si nécessaire.

**Exemple :**

```bash
curl "http://192.168.1.100:5000/image?filename=logo.png"
```

---

### 📝 Afficher du texte défilant

```bash
GET http://<IP_RASPBERRY>:5000/text?content=Hello+World&color=255,255,255
```

**Paramètres :**
- `content` : texte à afficher (URL-encoded)
- `color` : couleur RGB (optionnel, défaut: blanc `255,255,255`)

Le texte défile horizontalement en boucle.

**Exemples :**

```bash
# Texte blanc
curl "http://192.168.1.100:5000/text?content=Bonjour+le+monde"

# Texte rouge
curl "http://192.168.1.100:5000/text?content=ALERT&color=255,0,0"

# Texte vert
curl "http://192.168.1.100:5000/text?content=Success&color=0,255,0"
```

---

### 🎬 Lire une vidéo / animation

```bash
GET http://<IP_RASPBERRY>:5000/video?filename=animation.gif
```

**Paramètres :**
- `filename` : nom du fichier (dans `assets/videos/`)

**Formats supportés :** GIF, MP4

La vidéo joue en boucle infinie.

**Exemple :**

```bash
curl "http://192.168.1.100:5000/video?filename=demo.gif"
```

---

### 🎲 Mode aléatoire (diaporama)

```bash
GET http://<IP_RASPBERRY>:5000/random?interval=10
```

**Paramètres :**
- `interval` : durée d'affichage de chaque média en secondes (défaut: 10)

Lance un diaporama automatique qui :
- Scanne tous les médias dans `assets/images/` et `assets/videos/`
- Les affiche aléatoirement un par un
- Chaque média est affiché pendant la durée définie
- Les vidéos/GIF jouent en boucle pendant l'intervalle
- Continue indéfiniment jusqu'à l'arrêt (via `/clear`)

**Exemples :**

```bash
# Diaporama avec intervalle de 10 secondes (défaut)
curl "http://192.168.1.100:5000/random"

# Diaporama rapide (5 secondes par média)
curl "http://192.168.1.100:5000/random?interval=5"

# Diaporama lent (30 secondes par média)
curl "http://192.168.1.100:5000/random?interval=30"
```

**Cas d'usage :**
- Affichage publicitaire automatique
- Écran d'accueil dynamique
- Galerie photo automatique
- Rotation de contenu sans intervention

---

### 🕐 Afficher l'heure (horloge)

```bash
GET http://<IP_RASPBERRY>:5000/clock?format=24&seconds=true&color=255,255,255
```

**Paramètres :**
- `format` : format d'affichage - `24` pour 24h ou `12` pour 12h AM/PM (défaut: 24)
- `seconds` : afficher les secondes - `true` ou `false` (défaut: true)
- `color` : couleur RGB (optionnel, défaut: depuis config.yaml)

Affiche l'heure en temps réel, mise à jour automatique.

**Exemples :**

```bash
# Horloge 24h avec secondes (défaut)
curl "http://192.168.1.100:5000/clock"

# Horloge 12h sans secondes
curl "http://192.168.1.100:5000/clock?format=12&seconds=false"

# Horloge rouge
curl "http://192.168.1.100:5000/clock?color=255,0,0"
```

---

### 📅 Afficher la date

```bash
GET http://<IP_RASPBERRY>:5000/date?format=%d/%m/%Y&color=255,255,255
```

**Paramètres :**
- `format` : format de date Python strftime (défaut: %d/%m/%Y)
- `color` : couleur RGB (optionnel, défaut: depuis config.yaml)

Affiche la date du jour (statique).

**Exemples :**

```bash
# Date format français (défaut)
curl "http://192.168.1.100:5000/date"

# Date format américain
curl "http://192.168.1.100:5000/date?format=%m/%d/%Y"

# Date format complet
curl "http://192.168.1.100:5000/date?format=%A %d %B %Y"
```

**Formats courants :**
- `%d/%m/%Y` : 13/01/2026
- `%Y-%m-%d` : 2026-01-13
- `%d %B %Y` : 13 Janvier 2026
- `%A %d/%m` : Lundi 13/01

---

### 🌤️ Afficher la météo

```bash
GET http://<IP_RASPBERRY>:5000/weather
```

Affiche les informations météo en défilement (température et description).

**Prérequis :**
- Clé API OpenWeatherMap (gratuite) : https://openweathermap.org/api
- Configurer la clé dans `config.yaml` sous `api_keys.openweathermap`
- Configurer la localisation dans `config.yaml`

**Exemple :**

```bash
curl "http://192.168.1.100:5000/weather"
# Affiche: "Paris: 12°C - Ciel dégagé"
```

---

### 🖤 Effacer l'écran

```bash
GET http://<IP_RASPBERRY>:5000/clear
```

Arrête immédiatement tout rendu en cours et affiche un écran noir.

**Exemple :**

```bash
curl "http://192.168.1.100:5000/clear"
```

---

## 📁 Structure du projet

```
RPI2DMDv2/
├── controller.py          # Script principal
├── config.yaml           # Configuration centralisée
├── requirements.txt       # Dépendances Python
├── README.md             # Documentation
└── assets/
    ├── images/           # Images PNG/JPG
    ├── videos/           # Vidéos GIF/MP4
    └── fonts/            # Polices personnalisées
```

---

## ⚙️ Configuration

Toute la configuration du système se trouve dans le fichier **`config.yaml`**. Ce fichier centralisé permet de gérer tous les paramètres sans modifier le code.

### 🔧 Sections de configuration

#### 1. **Matrice LED** (`matrix`)

```yaml
matrix:
  rows: 64
  cols: 128
  chain_length: 5
  parallel: 1
  hardware_mapping: "regular"  # "regular" ou "adafruit-hat"
  brightness: 50  # 0-100
  gpio_slowdown: 4  # Raspberry Pi 4
```

#### 2. **Chemins des médias** (`paths`)

```yaml
paths:
  images: "assets/images"
  videos: "assets/videos"
  fonts: "assets/fonts"
```

Permet de personnaliser l'emplacement des dossiers de médias.

#### 3. **Durées par défaut** (`durations`)

```yaml
durations:
  default_image: 10  # Durée par défaut pour les images (secondes)
  default_video: 10  # Durée par défaut pour les vidéos (secondes)
  random_interval: 10  # Intervalle pour le mode aléatoire (secondes)
```

#### 4. **Horloge et date** (`clock`)

```yaml
clock:
  enabled: true
  format_24h: true  # true pour 24h, false pour 12h AM/PM
  show_seconds: true
  color: [255, 255, 255]  # RGB blanc
  date_format: "%d/%m/%Y"  # Format: jour/mois/année
```

#### 5. **Luminosité automatique** (`auto_brightness`)

```yaml
auto_brightness:
  enabled: true
  schedule:
    - time: "06:00"
      brightness: 30
    - time: "08:00"
      brightness: 60
    - time: "12:00"
      brightness: 80
    - time: "18:00"
      brightness: 60
    - time: "22:00"
      brightness: 30
    - time: "00:00"
      brightness: 15
```

**Fonction :** Ajuste automatiquement la luminosité de l'écran selon l'heure de la journée.
- Réduit la luminosité la nuit pour ne pas éblouir
- Augmente la luminosité en journée pour une meilleure visibilité
- Économise l'énergie et prolonge la durée de vie des LEDs

#### 6. **Localisation** (`location`)

```yaml
location:
  city: "Paris"
  country: "FR"
  timezone: "Europe/Paris"
  latitude: 48.8566
  longitude: 2.3522
```

**Utilisé pour :**
- Affichage de l'heure locale correcte
- Récupération de la météo locale
- Gestion de la luminosité selon l'heure locale

#### 7. **Clés API** (`api_keys`)

```yaml
api_keys:
  openweathermap: ""  # https://openweathermap.org/api
```

**Configuration :**
1. Créer un compte gratuit sur https://openweathermap.org/api
2. Récupérer votre clé API
3. La coller dans `config.yaml`

#### 8. **Serveur Flask** (`server`)

```yaml
server:
  host: "0.0.0.0"
  port: 5000
  debug: false
```

#### 9. **Polices** (`fonts`)

```yaml
fonts:
  clock: "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
  clock_size: 32
  date: "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
  date_size: 16
  text: "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
  text_size: 16
```

Personnalisez les polices et tailles pour chaque type d'affichage

---

## 🧠 Gestion des conflits

Le système garantit qu'**une seule action d'affichage est active à la fois**.

Toute nouvelle requête :
- Arrête proprement le rendu précédent
- Libère les ressources (threads)
- Lance le nouveau rendu

Cela évite les conflits de ressources et les comportements indéterminés.

---

## 🛠️ Démarrage automatique (service systemd)

Pour démarrer automatiquement le contrôleur au boot :

### 1. Créer le service

```bash
sudo nano /etc/systemd/system/rpi2dmdv2.service
```

### 2. Contenu du fichier

```ini
[Unit]
Description=RPI2DMDv2 LED Matrix Controller
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/rpi2dmdv2
ExecStart=/usr/bin/python3 /home/pi/rpi2dmdv2/controller.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Activer et démarrer

```bash
sudo systemctl daemon-reload
sudo systemctl enable rpi2dmdv2.service
sudo systemctl start rpi2dmdv2.service
```

### 4. Vérifier le statut

```bash
sudo systemctl status rpi2dmdv2.service
```

---

## 📚 Exemples d'utilisation

### Avec curl

```bash
# Afficher une image
curl "http://192.168.1.100:5000/image?filename=logo.png"

# Texte défilant
curl "http://192.168.1.100:5000/text?content=Bienvenue"

# Lire une vidéo
curl "http://192.168.1.100:5000/video?filename=intro.gif"

# Mode diaporama aléatoire (10 secondes par média)
curl "http://192.168.1.100:5000/random?interval=10"

# Afficher l'heure
curl "http://192.168.1.100:5000/clock"

# Afficher la date
curl "http://192.168.1.100:5000/date"

# Afficher la météo
curl "http://192.168.1.100:5000/weather"

# Effacer
curl "http://192.168.1.100:5000/clear"
```

### Avec Python

```python
import requests

base_url = "http://192.168.1.100:5000"

# Afficher une image
requests.get(f"{base_url}/image", params={"filename": "logo.png"})

# Texte rouge
requests.get(f"{base_url}/text", params={"content": "Hello World", "color": "255,0,0"})

# Mode diaporama (15 secondes par média)
requests.get(f"{base_url}/random", params={"interval": 15})

# Horloge 24h avec secondes
requests.get(f"{base_url}/clock", params={"format": "24", "seconds": "true"})

# Date
requests.get(f"{base_url}/date")

# Météo
requests.get(f"{base_url}/weather")

# Effacer
requests.get(f"{base_url}/clear")
```

### Avec Stream Deck

Créez des boutons avec des actions "Open URL" pointant vers vos endpoints.

---

## 🐛 Dépannage

### Le serveur ne démarre pas

- Vérifiez que vous exécutez avec `sudo`
- Vérifiez que la librairie `rgbmatrix` est installée : `python3 -c "import rgbmatrix"`

### L'affichage scintille

- Augmentez `gpio_slowdown` dans la configuration (essayez 4 ou 5)
- Vérifiez l'alimentation des panneaux

### Pas d'image affichée

- Vérifiez que les fichiers sont dans `assets/images/` ou `assets/videos/`
- Consultez les logs du serveur pour voir les erreurs

---

## 🔗 Ressources

- [rpi-rgb-led-matrix (Hzeller)](https://github.com/hzeller/rpi-rgb-led-matrix)
- [Adaptateurs HUB75](https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/adapter/active-3)
- [Documentation Flask](https://flask.palletsprojects.com/)

---

## 📝 License

Ce projet est open-source. Contributions bienvenues !

---

## 🚧 Roadmap

### ✅ Fonctionnalités disponibles

**Affichage de contenu :**
- ✅ Affichage d'images (PNG, JPG, BMP, GIF)
- ✅ Lecture de vidéos/GIF en boucle
- ✅ Texte défilant avec couleur personnalisable
- ✅ Mode diaporama aléatoire avec intervalle configurable

**Informations temps réel :**
- ✅ Horloge en temps réel (24h/12h, avec/sans secondes)
- ✅ Affichage de la date (formats personnalisables)
- ✅ Météo locale (via OpenWeatherMap API)

**Système et configuration :**
- ✅ Configuration centralisée via `config.yaml`
- ✅ Gestion automatique de la luminosité selon l'heure
- ✅ Support des fuseaux horaires
- ✅ Localisation configurable
- ✅ Gestion des conflits (un seul rendu actif à la fois)
- ✅ Mode simulation (sans hardware)

### 🔮 Fonctionnalités futures envisagées

- 🧪 Dashboard web pour contrôle visuel avec interface graphique
- 🧱 Playlists ordonnées et scènes personnalisées
- 🧵 Gestion avancée des animations et transitions
- 🎨 Effets visuels (fade, transition, wipe, scroll)
- 📊 Plus de données en temps réel (crypto, bourse, RSS, etc.)
- 🕐 Programmation horaire avancée (scheduler/cron)
- 🎮 Contrôle MQTT pour domotique
- 📱 Application mobile de contrôle
- 🔊 Synchronisation audio (affichage VU-meter)

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Merci de :
1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing-feature`)
3. Commit vos changements (`git commit -m 'Add amazing feature'`)
4. Push vers la branche (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

---

**Fait avec 💙 pour la communauté Raspberry Pi**
