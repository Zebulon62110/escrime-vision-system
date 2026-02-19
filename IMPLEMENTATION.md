# Implémentation détaillée - Détection par Garde-lignes

Document technique expliquant l'implémentation de la détection intelligente des fencers basée sur les lignes de mise en garde.

## 🎯 Objectif de conception

Remplacer la méthode fragile de clustering par une approche géométrique utilisant les garde-lignes comme **référence primaire d'identification**.

## 📐 Géométrie de base

### Piste d'escrime (France)

```
┌─────────────────────────────────────────────┐
│ PISTE d'ESCRIME (14 mètres)                 │
│                                             │
│  0m  START                                  │
│  ├──────────────────────────────────────┐   │
│  │                                      │   │
│  5m  ⚔ LEFT GUARD LINE                 │   │
│      Fencer 1 doit être ICI (←)         │   │
│  │                                      │   │
│  7m  ─── CENTER                         │   │
│  │                                      │   │
│  9m  ⚔ RIGHT GUARD LINE                │   │
│      Fencer 2 doit être ICI (→)         │   │
│  │                                      │   │
│ 14m  END                                │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  Longueur piste : 14 mètres                │
│  Positions réglementaires à distance égale │
└─────────────────────────────────────────────┘
```

### Calculs de positions en pixels

**Données d'entrée :**
- ROI piste : `(x1, y1, x2, y2)` en pixels
- Longueur piste en mètres

**Algorithme (`GuardLineDetector.set_piste_roi()`) :**

```python
# 1. Calculer pixels par mètre
piste_length_pixels = x2 - x1  # Largeur du ROI
piste_length_meters = 14  # Dimensions réglementaires
pixels_per_meter = piste_length_pixels / piste_length_meters

# 2. Calculer position de la garde-ligne à 5m
left_line_x = x1 + (5.0 / piste_length_meters) * piste_length_pixels
# Exemple: si x1=100, x2=1400 (1300 px max)
#   left_line_x = 100 + (5/14) * 1300 = 100 + 464 = 564px

# 3. Calculer position de la garde-ligne à 9m  
right_line_x = x1 + (9.0 / piste_length_meters) * piste_length_pixels
# Exemple: right_line_x = 100 + (9/14) * 1300 = 100 + 837 = 937px

# 4. Position centre pour visualisation
center_x = x1 + (7.0 / piste_length_meters) * piste_length_pixels
# Exemple: center_x = 100 + (7/14) * 1300 = 100 + 650 = 750px
```

## 🔍 Détection des fencers

### Étape 1 : Détection YOLO

YOLO retourne une liste de détections :
```python
detections = [
    {'bbox': (x1, y1, x2, y2), 'conf': 0.95, ...},
    {'bbox': (x3, y3, x4, y4), 'conf': 0.89, ...},
    ...
]
```

### Étape 2 : Classification par position

**Nouveau code dans `FencerTracker._initialize_with_guard_lines()` :**

```python
def _initialize_with_guard_lines(self, detections, guard_line_detector):
    """
    Séparer les détections en 2 groupes :
    - Gauche de la garde-ligne 5m  → Fencer 1
    - Droite de la garde-ligne 9m  → Fencer 2
    """
    
    # Récupérer les positions des garde-lignes (en pixels)
    left_line_x = guard_line_detector.guard_line_left_x    # ~458px
    right_line_x = guard_line_detector.guard_line_right_x   # ~819px
    
    # Séparer par position
    left_side = []
    right_side = []
    
    for detection in detections:
        bbox = detection['bbox']
        # Calculer le centroïde X
        centroid_x = (bbox[0] + bbox[2]) / 2.0
        
        # Classification simple
        if centroid_x < left_line_x:
            left_side.append(detection)
        elif centroid_x > right_line_x:
            right_side.append(detection)
    
    # Vérifier qu'on a 1+ détection de chaque côté
    if not left_side or not right_side:
        return None  # Pas prêt, attendre...
    
    # Sélectionner la meilleure de chaque côté
    fencer1_detection = max(left_side, key=lambda d: d['conf'])
    fencer2_detection = max(right_side, key=lambda d: d['conf'])
    
    # Locker les fencers
    for fencer_id, detection in [(1, fencer1_detection), (2, fencer2_detection)]:
        self.fencers[fencer_id] = TrackedFencer(
            id=fencer_id,
            bbox=detection['bbox'],
            centroid=self._centroid_from_bbox(detection['bbox']),
            frames_alive=0,
            frames_since_detection=0
        )
    
    self.initialized = True
    return (tracks, frame_info)
```

## ✅ Validation continue

### Workflow chaque frame

```
TRACKER.UPDATE(detections, guard_line_detector)
    ├─ Si non initialisé
    │  └─ _update_initialization()
    │      └─ _initialize_with_guard_lines()
    │          └─ Locker Fencer 1 & 2
    │
    ├─ Si initialisé
    │  └─ _update_tracking()
    │      └─ Matcher centroïdes, tracker positions
    │
    └─ PIPELINE.RUN()
       └─ validator = TRACKER.validate_fencers_on_guard_lines()
           └─ Vérifier que les fencers lockés sont "sur" une garde-ligne
              │
              ├─ Fencer 1 : doit être à côté LEFT line (avec tolérance)
              └─ Fencer 2 : doit être à côté RIGHT line (avec tolérance)
```

### Code de validation

**Nouvelle méthode `FencerTracker.validate_fencers_on_guard_lines()` :**

```python
def validate_fencers_on_guard_lines(self, guard_line_detector, current_detections):
    """
    Valider que les fencers lockés sont "sur" une garde-ligne.
    
    Processus :
    1. Appeler GuardLineDetector pour détecter quelles détections sont sur les lignes
    2. Comparer les fencers lockés avec les détections "sur-ligne"
    3. Retourner statut de chaque fencer
    """
    
    if not self.initialized or not current_detections:
        return {'fencer_1_on_guard': False, 'fencer_2_on_guard': False, ...}
    
    # 1. Détecter quelles détections sont "sur" une garde-ligne
    guard_result = guard_line_detector.detect_on_guard_line(current_detections)
    # Result: {'left': detection or None, 'right': detection or None}
    
    left_detection = guard_result.get('left')
    right_detection = guard_result.get('right')
    
    # 2. Obtenir les fencers lockés
    fencer_1 = self.fencers.get(1)
    fencer_2 = self.fencers.get(2)
    
    # 3. Vérifier Fencer 1 (doit être détecté sur LEFT line)
    fencer_1_on_guard = False
    if fencer_1 and left_detection:
        # Vérifier que c'est la MÊME détection (même bbox)
        if self._bboxes_overlap_significantly(
            fencer_1.bbox,
            left_detection['bbox'],
            threshold=0.5  # 50% IoU minimum
        ):
            fencer_1_on_guard = True
    
    # 4. Vérifier Fencer 2 (doit être détecté sur RIGHT line)
    fencer_2_on_guard = False
    if fencer_2 and right_detection:
        if self._bboxes_overlap_significantly(
            fencer_2.bbox,
            right_detection['bbox'],
            threshold=0.5
        ):
            fencer_2_on_guard = True
    
    # 5. Retourner résumé
    return {
        'fencer_1_on_guard': fencer_1_on_guard,
        'fencer_2_on_guard': fencer_2_on_guard,
        'both_on_guard': fencer_1_on_guard and fencer_2_on_guard,
        'status': f"{'✓' if fencer_1_on_guard else '✗'} F1 | {'✓' if fencer_2_on_guard else '✗'} F2"
    }
```

### Calcul d'intersection (IoU)

```python
@staticmethod
def _bboxes_overlap_significantly(bbox1, bbox2, threshold=0.5):
    """
    Calculer le pourcentage de recouvrement entre 2 bboxes.
    
    IoU = Intersection / Union
    
    Utilité : vérifier si 2 détections correspondent à la même personne.
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2
    
    # Intersection
    xi1 = max(x1_1, x1_2)
    yi1 = max(y1_1, y1_2)
    xi2 = min(x2_1, x2_2)
    yi2 = min(y2_1, y2_2)
    
    if xi1 >= xi2 or yi1 >= yi2:
        return False  # Pas d'intersection
    
    intersection = (xi2 - xi1) * (yi2 - yi1)
    union = (x2_1 - x1_1) * (y2_1 - y1_1) + (x2_2 - x1_2) * (y2_2 - y1_2) - intersection
    
    iou = intersection / union if union > 0 else 0
    return iou >= threshold
```

## 🔌 Intégration pipeline

### Modifications `core/pipeline.py`

```python
def run(self):
    while True:
        # ...
        
        # 1. Détecter personnes
        detections = self.person_detector.detect(frame, ...)
        
        # 2. MODIFICATION: Passer guard_line_detector à tracker
        tracks, track_info = self.tracker.update(
            detections,
            guard_line_detector=self.bout_manager.guard_line_detector  # ✅ NOUVEAU
        )
        
        # 3. MODIFICATION: Valider les fencers sur garde-lignes
        guard_validation = self.tracker.validate_fencers_on_guard_lines(
            self.bout_manager.guard_line_detector,
            current_detections=detections
        )
        track_info['guard_validation'] = guard_validation  # ✅ NOUVEAU
        
        # 4. Transition d'état
        current_phase = self.bout_manager.transition(track_info)
        
        # 5. Sauvegarder stats (avec validation)
        self.guard_validation = guard_validation
        self._save_stats()
        
        # ...visualisation, streaming, etc...
```

### Modifications `web/server.py`

```python
@app.get("/api/guard-validation")
def guard_validation_status():
    """Retourner le statut de validation des fencers."""
    try:
        with open("config/pipeline_stats.json", 'r') as f:
            stats = json.load(f)
            # stats contient 'guard_validation' que le pipeline a sauvegardé
            validation = stats.get("guard_validation", {})
            return {
                "fencer_1_on_guard": validation.get("fencer_1_on_guard", False),
                "fencer_2_on_guard": validation.get("fencer_2_on_guard", False),
                "both_on_guard": validation.get("both_on_guard", False),
                "status": validation.get("status", "—")
            }
    except Exception as e:
        return {"error": str(e)}
```

## 📊 Data flow (complet)

```
VIDEO FRAME
    ↓
YOLO DETECTION
    ├─ Detection 1: (x1, y1, x2, y2)
    ├─ Detection 2: (x3, y3, x4, y4)
    ├─ Detection 3: ...
    └─ Detection N: ...
    ↓
TRACKER.UPDATE(detections, guard_line_detector)
    ├─ [SI NON INITIALIZED]
    │  └─ FOR each detection:
    │      ├─ Calculate centroid_x
    │      ├─ IF centroid_x < left_line_x → left_side[]
    │      ├─ IF centroid_x > right_line_x → right_side[]
    │  └─ IF left_side.count >= 1 AND right_side.count >= 1
    │      ├─ SELECT best from left_side → Fencer 1
    │      ├─ SELECT best from right_side → Fencer 2
    │      ├─ LOCK both fencers (self.initialized = True)
    │      └─ RETURN tracks with IDs 1, 2
    │
    ├─ [SI INITIALIZED]
    │  └─ MATCH detections to existing tracks (centroid distance)
    │  └─ UPDATE locked fencers position
    │  └─ RETURN updated tracks
    │
    └─ RETURN (tracks, track_info)
    ↓
TRACKER.VALIDATE_FENCERS_ON_GUARD_LINES()
    ├─ guard_result = guard_line_detector.detect_on_guard_line(detections)
    │  └─ Returns: {'left': detection_or_none, 'right': detection_or_none}
    ├─ FOR Fencer 1:
    │  ├─ IF exists AND in guard_result['left']
    │  └─ AND bbox overlap > 50%
    │      └─ fencer_1_on_guard = TRUE
    ├─ FOR Fencer 2: [similarly]
    └─ RETURN {fencer_1_on_guard, fencer_2_on_guard, status}
    ↓
SAVE STATS
    └─ Write to JSON:
       {
         "guard_validation": {
           "fencer_1_on_guard": true/false,
           "fencer_2_on_guard": true/false,
           "both_on_guard": true/false,
           "status": "✓ F1 | ✓ F2"
         }
       }
    ↓
DRAW FRAME
    ├─ Draw piste ROI
    ├─ Draw guard lines (left, center, right)
    ├─ Draw detected persons (rectangles)
    ├─ Draw locked fencers (highlighted)
    └─ Color code:
       ✓ GREEN if on guard line
       ✗ RED if not on guard line
    ↓
WEB UI POLLING
    └─ Every 500ms:
       GET /api/guard-validation
       UPDATE Display: "⚔️ Guard Validation: ✓ F1 | ✓ F2"
```

## 🧪 Exemple d'exécution

### Scénario : Deux fencers prennent position

```
FRAME 1 : Yolo détecte 1 person
    Logs: 🔍 Waiting for fencers on guard lines... (left: 0, right: 0)

FRAME 2-3: Yolo détecte 1 person, puis 2
    Logs: 🔍 Waiting for fencers on guard lines... (left: 0, right: 1)

FRAME 4 : Yolo détecte 2 persons
    - Detection 1: centroid_x = 446  → centroid_x < 458 → left_side
    - Detection 2: centroid_x = 927  → centroid_x > 819 → right_side
    
    Logs: ✓ LOCKED 2 fencers using guard lines!
          → Fencer 1 (LEFT): x=446
          → Fencer 2 (RIGHT): x=927

FRAME 5+ : Suivi continu
    - UPDATE TRACKING (matcher détections,tracker mouvements)
    - VALIDATE (Fencer 1 sur LEFT line? Fencer 2 sur RIGHT line?)
    - Logs: ⚔️ Guard Validation: ✓ F1 | ✓ F2
    
    JSON stats: {
      "guard_validation": {
        "fencer_1_on_guard": true,
        "fencer_2_on_guard": true,
        "both_on_guard": true,
        "status": "✓ F1 | ✓ F2"
      }
    }
    
    Web UI: Display "✓ F1 | ✓ F2" (both green)
```

## 🔧 Dépannage

### Les fencers ne peuvent pas s'initialiser

**Causes possibles :**

1. **Guard-line detector pas initialisé**
   - Vérifier que ROI est défini
   - Vérifier que `guard_line_detector.piste_roi != None`

2. **Détections YOLO insuffisantes**
   - Vérifier que YOLO détecte 2+ personnes
   - Vérifier les confiances

3. **Fencers mal positionnés**
   - Fencer 1 doit être GAUCHE de ligne gauche (5m)
   - Fencer 2 doit être DROITE de ligne droite (9m)
   - Vérifier positions réglementaires sur piste

### Validation fonctionne mais résultats erratiques

1. **YOLO rédetecte différent fencer à chaque frame**
   - Augmenter `max_tracking_distance` dans FencerTracker
   - Augmenter `dropout_tolerance` pour plus de patience

2. **Fencers détectés mais pas reconnus "sur" une ligne**
   - Ajuster position garde-lignes via Web UI (±10px)
   - Augmenter tolérance dans `detect_on_guard_line()` si besoin

---

## Résumé technique

| Aspect | Avant (v1.1) | Après (v2.0) |
|--------|------------|-------------|
| **Initialisation** | Clustering 30 frames | Guard-lines 2-3 frames |
| **Robustesse** | Moyenne (clustering instable) | Haute (position géométrique) |
| **Validation** | Aucune | Chaque frame |
| **Performance** | Comparable | Meilleure |
| **Code maintenance** | Complexe | Simple |
| **Temps d'ajustement** | Manuel | Web UI interactive |

