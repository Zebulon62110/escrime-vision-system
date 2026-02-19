# Détection des Fencers - Escrime Vision System

## Fonctionnalité Complète ✅

**Une fois la piste sélectionnée manuellement**, le système détecte automatiquement les fencers (personnes en blanc sur la piste).

## Comment ça marche

### 1. Sélection de la Piste
- Utilisateur ouvre: `http://localhost:8001`
- Clique sur "📐 Draw Piste"
- Dessine un rectangle autour de la piste
- ROI est sauvegardée dans `config/shared_roi.py`

### 2. Détection des Fencers
Une fois la ROI sélectionnée:

```
[Vidéo] 
   ↓
[PersonDetector: YOLO détecte toutes les personnes]
   ↓
[FencerDetector: Filtre par]
   ├─ Couleur blanche (tenue de fencer)
   ├─ Position dans la ROI sélectionnée
   └─ Limite à 2 personnes (nombre de opponents)
   ↓
[Résultat: 0-2 fencers avec masque/sans masque]
```

## Architecture

### Nouveau: `vision/fencer_detector.py`

```python
class FencerDetector:
    """
    Détecte les fencers basé sur:
    1. Détection YOLO des personnes
    2. Filtre HSV pour clothing blanc (tenue escrime)
    3. Région ROI (piste sélectionnée)
    """
    
    def detect(frame):
        # 1. Récupère ROI desde shared_roi
        roi = get_manual_roi()
        if roi is None:
            return []  # Pas de piste sélectionnée
        
        # 2. Détecte personnes avec YOLO
        all_persons = person_detector.detect(frame)
        
        # 3. Filtre par couleur blanche + ROI
        fencers = [p for p in all_persons 
                   if is_in_roi(p) and has_white_color(p)]
        
        # 4. Garde max 2 fencers
        return fencers[:2]
```

### Filtre de Couleur Blanche

**HSV Thresholds (pour vêtements blancs):**
- **Saturation**: < 50 (très désaturé = gris/blanc)
- **Value**: > 150 (très clair = blanc)
- **Ratio minimum**: 25% du bbox should be white (pour filtrer les personnes habillées d'autres couleurs)

### Intégration Pipeline

**`main.py`**:
```python
person_detector = PersonDetector(...)
fencer_detector = FencerDetector(person_detector)

pipeline = VisionPipeline(
    person_detector=fencer_detector,  # ← Utilise FencerDetector
    ...
)
```

## Résultats Test

Sur le premier frame de `data/test.mp4` avec ROI (0, 300, 1280, 550):

```
✓ FencerDetector trouvé 2 fencers dans la ROI
  Fencer 1: bbox=(424, 379, 467, 535)  [Habillé de blanc]
  Fencer 2: bbox=(766, 350, 811, 500)  [Habillé de blanc]
```

## Prochaines Étapes

- [ ] Test avec vidéo réelle de match d'escrime
- [ ] Affiner le seuil de couleur blanche si besoin
- [ ] Implémenter le suivi multi-fencers (remplacer DummyTracker)
- [ ] Optimiser les performances (réduire le coût YOLO sur la ROI uniquement)

## Status Actuel

✅ Pipeline en cours d'exécution  
✅ Web UI prêt pour sélection de piste  
✅ FencerDetector avec filtre de couleur blanche  
✅ Détecte 2 fencers max par défaut  
✅ Masque et sans masque supportés  

**Accédez à**: http://localhost:8001
