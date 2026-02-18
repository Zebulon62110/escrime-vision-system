# Escrime - Système de Streaming Automatique (Jetson Orin Nano)

## Objectif
Mettre en place un système de captation automatique d'une compétition d'escrime permettant :
- la détection automatique des pistes,
- le suivi des tireurs sur une piste sélectionnée,
- le recadrage automatique (auto-framing),
- l'envoi d'un flux vidéo RTSP vers un PC de streaming,
- le pilotage à distance via une interface web.

## Matériel recommandé
- Jetson Orin Nano :
  - Acquisition vidéo
  - Détection IA (person detection)
  - Tracking multi-objets
  - Calcul du cadrage
  - Encodage matériel H.264
  - Serveur RTSP
- PC Windows :
  - Réception du flux RTSP
  - Streaming (OBS)
  - Overlay graphique (score, logos)
  - Supervision du système

## Architecture (principes)
Le système est découplé en trois blocs indépendants :

1) Vision
- Capture vidéo
- Détection des pistes
- Détection des personnes
- Tracking multi-objets
- Sélection des tireurs actifs
- Auto-framing

2) Streaming
- Encodage matériel NVENC
- Diffusion RTSP

3) Contrôle
- API REST
- Interface web
- Paramétrage temps réel

Cette séparation garantit robustesse et testabilité.

## Pipeline vidéo (flux principal)
VideoSource (Caméra ou fichier vidéo)
→ Détection des pistes (OpenCV)
→ Détection personnes (YOLO pré-entraîné)
→ Tracking multi-objets (ByteTrack)
→ Sélection des 2 tireurs actifs
→ Calcul zone de cadrage
→ Lissage du mouvement
→ Encodage H.264
→ Serveur RTSP

## Modes de fonctionnement
- LIVE : caméra réelle, streaming actif, paramétrage en temps réel.
- DEV : lecture de fichier, pause / frame par frame, overlays de debug.
- CALIBRATION : détection automatique des pistes, ajustement manuel, sauvegarde des paramètres.

## Front Web (Interface de contrôle)
Fonctions principales :
- Preview vidéo
- Affichage des pistes détectées
- Sélection de la piste active
- Réglage du zoom et du lissage
- Démarrage / arrêt de la source vidéo
- Statistiques temps réel (FPS, latence, GPU)

Le front communique via l'API REST et WebSocket pour les événements temps réel.

## Organisation logicielle recommandée
- `core/`
  - `pipeline.py`, `state_manager.py`
- `sources/`
  - `camera.py`, `video_file.py`
- `vision/`
  - `piste_detector.py`, `person_detector.py`, `tracker.py`, `framing.py`
- `stream/`
  - `rtsp_server.py`, `encoder_nvenc.py`, `encoder_software.py`
- `web/`
  - `api.py`, `websocket.py`
- `frontend/` (code UI)

## Principes techniques clés
- L'IA est utilisée uniquement pour détecter les personnes ; la logique métier sélectionne les tireurs.
- La géométrie des pistes réduit les faux positifs.
- Le système doit fonctionner en temps réel sur Jetson Orin Nano.
- Séparation Vision / Streaming / UI pour la stabilité et la maintenabilité.

## Évolutions possibles
- Multi-pistes simultanées
- Enregistrement automatique des matchs
- Ajout d'un module de reconnaissance/score automatique
- Statistiques et heatmaps de déplacement
- Détection des phases actives (engagements)

## Installation rapide (Jetson)
- Installer les dépendances système et Python (voir `requirements.txt`).
- Déployer les modèles IA (YOLO, ByteTrack) dans `vision/models/`.
- Lancer le pipeline en mode DEV :

```bash
python main.py --mode DEV
```

- En LIVE, lancer le service RTSP puis ouvrir le flux dans OBS sur le PC Windows.

## Usage
- Utiliser l'interface web pour sélectionner la piste et régler le framing.
- Pour forcer l'utilisation du Git/WSL depuis VSCode, ouvrir un terminal WSL intégré.

## Contribuer
- Fork + PR
- Respecter la séparation des responsabilités (vision / stream / web)
- Ajouter des tests unitaires pour la logique de sélection et le framing

## Licence
À préciser.
