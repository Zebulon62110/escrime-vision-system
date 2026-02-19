# Escrime - Système de Détection et Streaming d'Escrimes

Système complet de détection automatique, suivi et streaming des compétitions d'escrime utilisant l'IA et la vision par ordinateur.

## 🎯 Objectifs principaux

- ✅ Détection automatique de la piste d'escrime (14m x ~2m)
- ✅ **Identification des 2 fencers par position relative aux lignes de mise en garde** (NOUVEAU)
- ✅ Suivi en temps réel des fencers avec IDs persistants
- ✅ **Validation continue de la position des fencers sur les garde-lignes** (NOUVEAU)
- ✅ Recadrage automatique (auto-framing) pour garder les 2 fencers visibles
- ✅ Interface web de contrôle et de paramétrage temps réel
- ✅ Streaming RTSP vers PC de montage (OBS, etc.)

## ✨ Modifications récentes (Feb 2026)

### 🆕 Détection des fencers basée sur les lignes de mise en garde

Le système utilise maintenant les **lignes de mise en garde** comme référence primaire pour identifier les fencers :

**Identification simple :**
- **Fencer 1** : détecté à **GAUCHE** de la ligne gauche (5m)
- **Fencer 2** : détecté à **DROITE** de la ligne droite (9m)

**Workflow d'initialisation :**
```
PISTE DÉTECTÉE  →  CALCUL GARDE-LIGNES  →  FENCERS IDENTIFIÉS  →  SUIVI
```

### 🆕 Validation garde-lignes (API)

**Endpoint** : `GET /api/guard-validation`

```json
{
  "fencer_1_on_guard": true,
  "fencer_2_on_guard": true,
  "both_on_guard": true,
  "status": "✓ F1 | ✓ F2"
}
```

Affichage web : `⚔️ Guard Validation: ✓ F1 | ✓ F2`

### 🗑️ Code nettoyé

- ❌ Suppression de la méthode obsolète `_cluster_candidates_by_position()`
- ❌ Suppression des paramètres inutilisés (`initialization_frames`, `init_stabilization`)
- ✅ Code simplifié avec priorité stricte aux garde-lignes
- ✅ Documentation améliorée

## 🏗️ Architecture

### Trois modules découplés

```
┌──────────────────────────────────────┐
│        VIDÉO SOURCE                  │
│   (Caméra / Fichier vidéo)           │
└────────────────┬─────────────────────┘
                 │
┌────────────────▼─────────────────────┐
│      PIPELINE VISION                 │
│  • Détection piste (ROI)             │
│  • Détection personnes (YOLO)        │
│  • Identification fencers par        │
│    position garde-lignes             │
│  • Suivi fencers                     │
│  • Validation garde-lignes           │
│  • Auto-framing                      │
└────────────────┬─────────────────────┘
      ┌──────────┼──────────┐
      │          │          │
  ┌───▼────┐ ┌───▼───┐ ┌──▼──────┐
  │STREAMING│ │API WEB│ │STATS    │
  │ RTSP   │ │REST   │ │JSON     │
  │ NVENC  │ │WS     │ │         │
  └────────┘ └───────┘ └─────────┘
```

### Structure des fichiers

```
escrime-vision-system/
├── main.py                          # Point d'entrée
├── core/
│   ├── pipeline.py                  # Pipeline vision principal
│   ├── interfaces.py                # Interfaces abstraites
│   ├── state_manager.py             # Gestion estado (ROI, phase)
│   └── bout_manager.py              # Logique du bout
├── vision/
│   ├── person_detector.py           # Détection YOLO
│   ├── piste_detector.py            # Détection ROI
│   ├── guard_line_detector.py       # Garde-lignes ⭐ CLEF
│   ├── fencer_tracker.py            # Suivi 2 fencers ⭐ PRINCIPAL
│   └── framing.py                   # Calcul cadrage
├── sources/
│   ├── camera.py                    # Caméra
│   └── video_file.py                # Vidéo fichier
├── stream/
│   ├── encoder_nvenc.py             # Encodage NVIDIA
│   ├── encoder_software.py          # Encodage logiciel
│   └── rtsp_server.py               # Serveur RTSP
├── config/
│   ├── shared_roi.py                # Config ROI partagée
│   ├── shared_visibility.py         # Config visibilité
│   ├── shared_guard_lines.py        # Config garde-lignes
│   └── pipeline_stats.json          # Stats temps réel
├── web/
│   ├── server.py                    # API FastAPI
│   └── static/index.html            # Web UI
└── tests/
    ├── test_pipeline.py
    ├── test_framing.py
    └── test_tracker.py
```

## 🚀 Démarrage rapide

### Installation
```bash
pip install -r requirements.txt
```

### Lancer le système
```bash
python main.py
```

### Accéder à l'interface
```
http://localhost:8001
```

## 📱 Interface Web - Mode d'emploi

### Étape 1️⃣ : Sélection de la piste

1. Cliquez sur **"📐 Draw Piste"**
2. Dessinez le rectangle de la piste sur l'image vidéo
3. Cliquez sur **"✓ Validate & Start"**

### Étape 2️⃣ : Détection des fencers

L'interface affiche :
```
🔨 Execution Mode: DEV | FENCER_DETECTION
📡 Pipeline: 🟢 Running
👥 Fencers: 2
⚔️ Guard Validation: ✓ F1 | ✓ F2        ← Les fencers sont OK!
📍 ROI: x: 8-1269, y: 514-552
```

Les fencers doivent être à leur position de garde (gauche pour F1, droite pour F2).

### Étape 3️⃣ : Ajuster les garde-lignes (si besoin)

Un panneau apparaît pendant FENCER_DETECTION :

```
⚔️ Adjust Guard Lines

Left Line (5m)           Right Line (9m)
[←] [-10px] [+10px] [→] [←] [-10px] [+10px] [→]
[  Reset  ]              [  Reset  ]
```

Utilisez les boutons pour ajuster les positions.

### Étape 4️⃣ : Suivi continu

Une fois les fencers lockés, le système entre en mode **BOUT_ACTIVE** :
- Suivi en temps réel
- Validation garde-lignes continues
- Auto-framing des 2 fencers
- Streaming RTSP actif

## 🔧 API REST (Ajustement temps réel)

### Ajuster une garde-ligne
```bash
curl -X POST http://localhost:8001/api/adjust-guard-line \
  -H "Content-Type: application/json" \
  -d '{
    "line": "left",
    "offset_x": 10,
    "tilt": 1.0
  }'
```

Paramètres :
- `line` : `"left"` | `"right"` | `"center"`
- `offset_x` : pixels (positif = droite, négatif = gauche)
- `tilt` : 1.0 = normal, <1.0 = converge, >1.0 = diverge

### Récupérer l'état
```bash
curl http://localhost:8001/api/guard-lines-adjustments
```

Response :
```json
{
  "left_offset": 10,
  "left_tilt": 1.0,
  "right_offset": -5,
  "right_tilt": 1.0,
  "center_offset": 0
}
```

### Réinitialiser
```bash
curl -X POST http://localhost:8001/api/reset-guard-lines
```

### Obtenir le statut de validation
```bash
curl http://localhost:8001/api/guard-validation
```

## 📊 Phases du bout

```
PISTE_SELECTION
    ↓ [Utilisateur définit le ROI]
FENCER_DETECTION
    ↓ [Détection des 2 fencers sur garde-lignes]
INITIALIZING
    ↓ [Fencers lockés, préparation match]
BOUT_ACTIVE
    ↓ [Suivi en temps réel]
```

## 🔍 Détails techniques

### FencerTracker (`vision/fencer_tracker.py`)

**Responsabilités principales :**
1. Initialiser via `_initialize_with_guard_lines()` 
2. Identifier Fencer 1 (gauche) et Fencer 2 (droite)
3. Tracker avec IDs persistants (1, 2)
4. Valider position sur garde-lignes chaque frame
5. Calculer cadrage optimal

**Méthodes clés :**
- `update(detections, guard_line_detector)` 
- `_initialize_with_guard_lines(detections, guard_line_detector)`
- `validate_fencers_on_guard_lines(guard_line_detector, current_detections)`
- `_calculate_frame_box()` pour l'auto-framing

### GuardLineDetector (`vision/guard_line_detector.py`)

**Responsabilités :**
1. Calculer les positions de garde-lignes automatiquement
2. Ajuster position/tilt temps réel
3. Détecter si une détection est "sur" une ligne
4. Valider proche-lignes

**Positions (France) :**
```
0m ────────────────── start
5m ──⚔── LEFT guard line  (Fencer 1 doit être GAUCHE)
7m ────────────────── CENTER
9m ──⚔── RIGHT guard line (Fencer 2 doit être DROITE)
14m ──────────────── fin
```

## 🆘 Dépannage

### Les fencers ne sont pas détectés

**Vérifier :**
1. ❓ YOLO détecte-t-il les 2 personnes ? (voir logs)
2. ❓ Les personnes sont-elles aux positions de garde ?
3. ❓ ROI est-il correct ? (réessayer "Draw Piste")

### Garde-lignes mal positionnées

**Solutions :**
1. Utiliser boutons ±10px dans Web UI
2. API `/api/adjust-guard-line` avec `offset_x`
3. `/api/reset-guard-lines` pour recommencer

### Fencers "sautent" pendant le suivi

**Paramètres à ajuster :**
```python
# vision/fencer_tracker.py
max_tracking_distance = 100.0  # px (augmenter si trop restrictif)
dropout_tolerance = 30  # frames (augmenter pour plus de tolérance)
```

## 📈 Exemple de logs réussis

```
[GuardLineDetector] Initial guard lines: 5m=458px, 7m=638px, 9m=819px
[FencerTracker] ✓ LOCKED 2 fencers using guard lines!
  → Fencer 1 (LEFT): x=446 (left of 458px)
  → Fencer 2 (RIGHT): x=927 (right of 819px)
  → Separation: 481px
[BoutManager] 🤺 Phase → BOUT_ACTIVE (fencers locked)
```

## 🧪 Tests

```bash
pytest tests/
```

## 🔮 Évolutions futures

- [ ] Multi-pistes simultanées
- [ ] Enregistrement automatique des matchs
- [ ] Heatmaps de déplacements
- [ ] Détection automatique des engagements
- [ ] Scoring assisté par IA

## 📄 Licence

Propriétaire

---

**Version** : 2.0 (Feb 2026)
**Dernière mise à jour** : Code nettoyé, garde-lignes intégrées
