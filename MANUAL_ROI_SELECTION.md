# Manuel Sélection de la Piste - Escrime Vision System

## Configuration Complète ✓

Vous avez choisi d'**abandonner la détection automatique des pistes** (qui était instable) et l'**interface web permet maintenant une sélection manuelle**.

## Comment ça marche

### Pour l'utilisateur (Web UI)

1. **Ouvrez** l'interface web: `http://localhost:8001`
2. **Cliquez** sur le bouton "📐 Draw Piste"
3. **Dessinez** un rectangle en cliquant et en glissant sur la vidéo pour délimiter la piste
4. **Relâchez** la souris - le ROI est automatiquement enregistré

Le rectangle vert superposé montre la région sélectionnée.

### Pour le développeur (API)

```bash
# Sélectionner manuellement une piste par API
curl -X POST http://localhost:8001/api/select-roi \
  -H "Content-Type: application/json" \
  -d '{
    "x1": 0,
    "y1": 300,
    "x2": 1280,
    "y2": 550
  }'
```

## Architecture

### Fichiers modifiés

1. **`web/static/index.html`** - Interface utilisateur avec dessin de rectangle
2. **`web/server.py`** - Endpoint `/api/select-roi` pour recevoir le ROI
3. **`vision/piste_detector.py`** - Détecteur utilisant maintenant le ROI manuel
4. **`config/shared_roi.py`** - Config partagée entre serveur web et pipeline

### Flux de données

```
[Web UI: Utilisateur dessine]
           ↓
[/api/select-roi endpoint]
           ↓
[config/shared_roi.py: sauvegarde ROI]
           ↓
[Pipeline: PisteDetector lit la ROI]
           ↓
[Filtre détections de tireurs par ROI]
```

## Utilisation dans le Pipeline

### Code du detecteur

```python
from config.shared_roi import get_manual_roi

# Dans la méthode detect()
shared_roi = get_manual_roi()
if shared_roi is not None:
    x1, y1, x2, y2 = shared_roi
    return [(x1, y1, x2, y2)]  # Utilise le ROI manuel
```

### Filtre des tireurs

Le pipeline filtre automatiquement les détections de personnes pour garder uniquement celles dans la ROI sélectionnée:

```python
# Dans core/pipeline.py
for d in detections:
    bbox = d.get('bbox')
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    for px1, py1, px2, py2 in piste_bboxes:
        if px1 <= cx <= px2 and py1 <= cy <= py2:
            filtered.append(d)  # Gardé si dans le ROI
```

## Prochaines étapes (À faire)

- [ ] Calibrer la détection des tireurs avec un ROI bien défini
- [ ] Implémenter le suivi multi-tireurs (replacement du DummyTracker)
- [ ] Optimiser les performances du tracker

## Status actuel

✅ Pipeline en cours d'exécution
✅ Web UI prêt
✅ Sélection manuelle des pistes fonctionnelle
✅ Filtrage des détections par ROI activé

Accédez à: **http://localhost:8001**
