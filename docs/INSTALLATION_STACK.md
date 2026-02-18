# Installation Complète – Stack de Développement
## Projet Streaming Automatique Escrime (Jetson Orin Nano)

---

## 1. Objectif

Mettre en place une stack de développement permettant :

- le développement complet sous Windows
- l'exécution du pipeline dans WSL
- le test sans Jetson
- l'utilisation de vidéos enregistrées
- une compatibilité totale DEV / PROD

Le Jetson est utilisé uniquement pour l’optimisation matérielle.

---

## 2. Architecture Générale

### Mode DEV

Fichier vidéo
↓
Pipeline Vision (CPU)
↓
Auto-framing
↓
Encodage software (x264)
↓
RTSP local
↓
OBS / VLC


### Mode PROD (Jetson)

Caméra
↓
Pipeline Vision (CUDA)
↓
Auto-framing
↓
NVENC H264
↓
RTSP


Le code applicatif reste identique.

---

## 3. Installation Windows

Installer :

- Windows Subsystem for Linux (WSL)
- VSCode
- OBS Studio
- VLC

Installation WSL :

```powershell
wsl --install
4. Installation WSL (Ubuntu)
sudo apt update
sudo apt install python3 python3-pip ffmpeg git -y
5. Installation Python
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
6. Création du Repository
Structure recommandée :

core/
sources/
vision/
stream/
web/
config/
scripts/
tests/
Principe :

Vision indépendante du matériel

Streaming abstrait

API indépendante

7. Lancement Mode DEV
Source vidéo :

VideoFileSource("match.mp4")
Lancement pipeline :

python main.py
Flux disponible :

rtsp://localhost:8554/live
Visualisation :

OBS

VLC

8. Installation Jetson Orin Nano
Sur le Jetson :

sudo apt install python3-pip ffmpeg
pip3 install -r requirements.txt
Installer PyTorch compatible Jetson.

Changer uniquement :

source caméra

encodeur NVENC

9. Bonnes Pratiques
Toujours développer en mode DEV

Utiliser des vidéos enregistrées

Tester frame par frame

Ne passer sur Jetson qu’après validation

Maintenir les interfaces abstraites


---

# ✅ 2️⃣ Générer le PDF (1 commande)

Installe pandoc :

```bash
sudo apt install pandoc
Puis :

pandoc docs/INSTALLATION_STACK.md -o Installation_Stack_Escrime.pdf
