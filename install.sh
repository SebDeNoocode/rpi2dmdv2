#!/bin/bash
################################################################################
# Script d'installation automatique RPI2DMDv2
# Installe toutes les dépendances et configure le système
################################################################################

set -e  # Arrêt en cas d'erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction d'affichage
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Bannière
echo "════════════════════════════════════════════════════════"
echo "       🎛️  Installation RPI2DMDv2"
echo "       LED Matrix Controller pour Raspberry Pi"
echo "════════════════════════════════════════════════════════"
echo ""

# Vérification : root
if [ "$EUID" -ne 0 ]; then
    log_error "Ce script doit être exécuté en tant que root"
    echo "Utilisez: sudo ./install.sh"
    exit 1
fi

# Vérification : Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    log_warning "Ce script est conçu pour Raspberry Pi"
    read -p "Continuer quand même ? (o/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Oo]$ ]]; then
        exit 1
    fi
fi

# Étape 1 : Mise à jour du système
log_info "Étape 1/6 : Mise à jour du système"
apt-get update
apt-get upgrade -y
log_success "Système mis à jour"

# Étape 2 : Installation des dépendances système
log_info "Étape 2/6 : Installation des dépendances système"
apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-dev \
    python3-pillow \
    build-essential \
    libgraphicsmagick++-dev \
    libwebp-dev \
    wget \
    curl

log_success "Dépendances système installées"

# Étape 3 : Installation de rpi-rgb-led-matrix
log_info "Étape 3/6 : Installation de rpi-rgb-led-matrix"

if [ ! -d "$HOME/rpi-rgb-led-matrix" ]; then
    cd "$HOME"
    git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
    cd rpi-rgb-led-matrix
    make -C lib
    make -C examples-api-use

    # Installer les bindings Python
    cd bindings/python
    pip3 install -e .

    log_success "rpi-rgb-led-matrix installé"
else
    log_warning "rpi-rgb-led-matrix déjà installé (ignoré)"
fi

# Étape 4 : Installation des dépendances Python RPI2DMDv2
log_info "Étape 4/6 : Installation des dépendances Python"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "requirements.txt" ]; then
    log_info "Installation des packages Python depuis requirements.txt..."
    if pip3 install -r requirements.txt; then
        log_success "Dépendances Python installées"

        # Vérification que les modules critiques sont bien installés
        python3 -c "import flask, pytz, yaml, PIL, imageio, requests" 2>/dev/null
        if [ $? -eq 0 ]; then
            log_success "Tous les modules Python sont fonctionnels"
        else
            log_warning "Certains modules Python ne semblent pas importables"
            log_info "Tentative de réinstallation..."
            pip3 install --upgrade --force-reinstall -r requirements.txt
        fi
    else
        log_error "Échec de l'installation des dépendances Python"
        exit 1
    fi
else
    log_error "Fichier requirements.txt non trouvé"
    exit 1
fi

# Étape 5 : Configuration
log_info "Étape 5/6 : Configuration initiale"

if [ ! -f "config.yaml" ]; then
    if [ -f "config.example.yaml" ]; then
        cp config.example.yaml config.yaml
        log_success "Fichier config.yaml créé depuis config.example.yaml"
        log_warning "⚠️  IMPORTANT : Éditez config.yaml pour personnaliser votre configuration"
        log_info "   nano config.yaml"
    else
        log_error "config.example.yaml non trouvé"
        exit 1
    fi
else
    log_warning "config.yaml existe déjà (non écrasé)"
fi

# Créer les dossiers assets s'ils n'existent pas
mkdir -p assets/images assets/videos assets/fonts
log_success "Dossiers assets créés"

# Étape 6 : Installation du service systemd
log_info "Étape 6/6 : Configuration du service systemd"

cat > /etc/systemd/system/rpi2dmdv2.service <<EOF
[Unit]
Description=RPI2DMDv2 LED Matrix Controller
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/controller.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
log_success "Service systemd créé"

# Résumé
echo ""
echo "════════════════════════════════════════════════════════"
log_success "Installation terminée !"
echo "════════════════════════════════════════════════════════"
echo ""
echo "📝 Prochaines étapes :"
echo ""
echo "1️⃣  Configurer vos paramètres :"
echo "   nano config.yaml"
echo ""
echo "2️⃣  Tester manuellement :"
echo "   sudo python3 controller.py"
echo ""
echo "3️⃣  Accéder au dashboard :"
echo "   http://$(hostname -I | awk '{print $1}'):5000/dashboard"
echo ""
echo "4️⃣  Activer le démarrage automatique :"
echo "   sudo systemctl enable rpi2dmdv2.service"
echo "   sudo systemctl start rpi2dmdv2.service"
echo ""
echo "5️⃣  Voir les logs :"
echo "   sudo journalctl -u rpi2dmdv2.service -f"
echo ""
echo "════════════════════════════════════════════════════════"
echo ""
log_info "Documentation complète : README.md"
echo ""
