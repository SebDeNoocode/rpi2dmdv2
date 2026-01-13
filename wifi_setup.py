#!/usr/bin/env python3
"""
Script utilitaire pour configurer le WiFi sur Raspberry Pi
À partir de la configuration définie dans config.yaml
"""

import os
import sys
import yaml
import subprocess
from pathlib import Path

# Chemins
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / 'config.yaml'
WPA_SUPPLICANT_PATH = '/etc/wpa_supplicant/wpa_supplicant.conf'


def load_config():
    """Charge la configuration depuis config.yaml"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de config.yaml: {e}")
        sys.exit(1)


def generate_wpa_supplicant(ssid, password, country):
    """Génère le contenu du fichier wpa_supplicant.conf"""
    return f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country={country}

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""


def configure_wifi(config):
    """Configure le WiFi à partir de la config"""
    if not config.get('wifi', {}).get('enabled', False):
        print("ℹ️  Configuration WiFi désactivée dans config.yaml")
        return

    wifi_config = config['wifi']
    ssid = wifi_config.get('ssid', '')
    password = wifi_config.get('password', '')
    country = wifi_config.get('country', 'FR')

    if not ssid or not password:
        print("⚠️  SSID ou mot de passe WiFi manquant dans config.yaml")
        return

    if ssid == "VotreSSID" or password == "VotreMotDePasse":
        print("⚠️  Veuillez configurer votre SSID et mot de passe WiFi dans config.yaml")
        return

    # Vérifier les permissions root
    if os.geteuid() != 0:
        print("❌ Ce script doit être exécuté avec sudo")
        sys.exit(1)

    print(f"📡 Configuration WiFi...")
    print(f"   SSID: {ssid}")
    print(f"   Pays: {country}")

    # Générer le contenu wpa_supplicant
    wpa_content = generate_wpa_supplicant(ssid, password, country)

    try:
        # Sauvegarder le fichier wpa_supplicant
        with open(WPA_SUPPLICANT_PATH, 'w') as f:
            f.write(wpa_content)
        print(f"✅ Fichier {WPA_SUPPLICANT_PATH} créé")

        # Redémarrer le service wpa_supplicant
        print("🔄 Redémarrage du service WiFi...")
        subprocess.run(['wpa_cli', '-i', 'wlan0', 'reconfigure'], check=False)

        print("✅ Configuration WiFi appliquée !")
        print("ℹ️  Le Raspberry Pi devrait se connecter au WiFi dans quelques secondes")

        # Afficher l'état de la connexion après quelques secondes
        print("\n📊 Vérification de la connexion...")
        subprocess.run(['sleep', '5'], check=False)
        subprocess.run(['iwconfig', 'wlan0'], check=False)

    except PermissionError:
        print(f"❌ Permission refusée pour écrire {WPA_SUPPLICANT_PATH}")
        print("   Exécutez ce script avec sudo")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur lors de la configuration WiFi: {e}")
        sys.exit(1)


def show_current_wifi():
    """Affiche l'état actuel du WiFi"""
    print("\n📡 État actuel du WiFi:")
    print("=" * 50)

    # Afficher l'adresse IP
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        if result.stdout.strip():
            print(f"🌐 Adresse IP: {result.stdout.strip()}")
        else:
            print("⚠️  Pas d'adresse IP (non connecté)")
    except:
        pass

    # Afficher iwconfig
    try:
        subprocess.run(['iwconfig', 'wlan0'], check=False)
    except:
        print("❌ Impossible d'obtenir les informations WiFi")

    print("=" * 50)


if __name__ == '__main__':
    print("=" * 50)
    print("🔧 Configuration WiFi pour RPI2DMDv2")
    print("=" * 50)

    # Charger la configuration
    config = load_config()

    # Afficher l'état actuel
    show_current_wifi()

    # Demander confirmation
    print("\n⚠️  Cette opération va modifier la configuration WiFi du système.")
    response = input("Continuer ? (o/N): ").strip().lower()

    if response in ['o', 'oui', 'y', 'yes']:
        configure_wifi(config)
        print("\n✅ Configuration terminée !")
    else:
        print("❌ Configuration annulée")
