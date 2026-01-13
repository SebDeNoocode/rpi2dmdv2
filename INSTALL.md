# 🚀 Installation rapide RPI2DMDv2

Guide d'installation simplifié en 5 minutes.

---

## ⚡ Installation automatique (recommandé)

```bash
# 1. Cloner le projet
cd ~
git clone https://github.com/SebDeNoocode/rpi2dmdv2.git
cd rpi2dmdv2

# 2. Lancer le script d'installation
sudo ./install.sh

# 3. Configurer
nano config.yaml

# 4. Démarrer
sudo python3 controller.py
```

**C'est tout !** Le script installe automatiquement toutes les dépendances.

---

## 🔧 Prérequis matériels

- ✅ Raspberry Pi 4 (ou 3B+)
- ✅ Carte SD 8GB minimum
- ✅ Panneaux LED HUB75
- ✅ HAT RGB Matrix
- ✅ Alimentation 5V pour les LEDs

---

## 📋 Installation manuelle (détaillée)

### 1. Préparer le Raspberry Pi

```bash
# Mettre à jour
sudo apt-get update && sudo apt-get upgrade -y

# Installer les outils
sudo apt-get install -y git python3 python3-pip python3-dev build-essential
```

### 2. Installer rpi-rgb-led-matrix

```bash
cd ~
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
cd rpi-rgb-led-matrix
make -C lib
cd bindings/python
sudo pip3 install -e .
```

### 3. Installer RPI2DMDv2

```bash
cd ~
git clone https://github.com/SebDeNoocode/rpi2dmdv2.git
cd rpi2dmdv2
sudo pip3 install -r requirements.txt
```

### 4. Configurer

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Paramètres minimaux à vérifier :
- `matrix.rows` : nombre de lignes par panneau
- `matrix.cols` : nombre de colonnes par panneau
- `matrix.chain_length` : nombre de panneaux
- `location.timezone` : votre fuseau horaire

### 5. Tester

```bash
sudo python3 controller.py
```

Ouvrir dans un navigateur : `http://IP_RASPBERRY:5000/dashboard`

---

## 🔄 Démarrage automatique

```bash
# Créer le service
sudo nano /etc/systemd/system/rpi2dmdv2.service
```

Contenu :

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

[Install]
WantedBy=multi-user.target
```

Activer :

```bash
sudo systemctl enable rpi2dmdv2.service
sudo systemctl start rpi2dmdv2.service
```

---

## ✅ Vérification

### Test 1 : Dashboard
```
http://192.168.1.XXX:5000/dashboard
```

### Test 2 : Horloge
```bash
curl "http://192.168.1.XXX:5000/clock"
```

### Test 3 : Upload image
Via le dashboard : glisser-déposer une image

---

## 🆘 Problèmes courants

### "Permission denied"
→ Utiliser `sudo` pour lancer le script

### "rgbmatrix not found"
→ Vérifier l'installation de rpi-rgb-led-matrix :
```bash
cd ~/rpi-rgb-led-matrix/bindings/python
sudo pip3 install -e .
```

### "Config file not found"
→ Copier le fichier d'exemple :
```bash
cp config.example.yaml config.yaml
```

### Couleurs inversées
→ Changer `led_rgb_sequence` dans config.yaml :
```yaml
matrix:
  led_rgb_sequence: "BGR"  # Essayer BGR, GRB, etc.
```

### Panneaux scintillent
→ Augmenter `gpio_slowdown` dans config.yaml :
```yaml
matrix:
  gpio_slowdown: 4  # Essayer 5 ou 6
```

---

## 📚 Documentation complète

Voir **README.md** pour :
- Documentation complète de l'API
- Tous les endpoints disponibles
- Configuration avancée
- Exemples d'utilisation

---

## 💡 Premier test rapide

```bash
# 1. Afficher l'heure
curl "http://IP:5000/clock"

# 2. Texte défilant
curl "http://IP:5000/text?content=Hello+World"

# 3. Effacer
curl "http://IP:5000/clear"
```

---

## 🎯 Pour aller plus loin

1. **Configurer le WiFi** : `sudo python3 wifi_setup.py`
2. **Ajouter des médias** : via le dashboard ou dans `assets/`
3. **Mode diaporama** : `curl "http://IP:5000/random?interval=10"`
4. **Météo** : Ajouter clé API dans config.yaml

---

**Besoin d'aide ?** Consultez les [Issues GitHub](https://github.com/SebDeNoocode/rpi2dmdv2/issues)
