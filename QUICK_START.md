# Guide de démarrage rapide

Version courte et simple pour commencer tout de suite.

## ✅ Prérequis installés

- Python 3.8+
- Dépendances : `pip install -r requirements.txt`
- Caméra connectée (USB ou MIPI CSI)

## 🚀 Démarrage (3 étapes)

### 1. Lancer le système

```bash
cd /home/seb/escrime-vision-system
python main.py
```

Attendre que les logs affichent :
```
Starting pipeline in DEV mode
GStreamer RTSP server failed...
MJPEG preview available at http://localhost:8080/preview
```

### 2. Ouvrir l'interface web

```
http://localhost:8001
```

### 3. Suivre l'assistant

```
┌─────────────────────────────────────────┐
│ 1. DRAW PISTE                           │
│    Cliquez "📐 Draw Piste"              │
│    Dessinez le rectangle de la piste    │
│    Cliquez "✓ Validate & Start"         │
│                                         │
│ 2. WATCH FENCERS                        │
│    Attendez que les fencers arrivent    │
│    Panel: ⚔️ Guard Validation: ✓ F1 | ✓ F2  │
│                                         │
│ 3. ADJUST (si besoin)                   │
│    Boutons ±10px pour aide-lignes       │
│    API: POST /api/adjust-guard-line     │
│                                         │
│ 4. STREAM                               │
│    Ouvrir flux RTSP pour OBS            │
│    rtsp://[IP]:554/live                 │
└─────────────────────────────────────────┘
```

## 📱 Web UI - Vue rapide

### Status Panel (top)
```
🔧 Execution Mode: DEV
📡 Pipeline: 🟢 Running
👥 Fencers: 2
⚔️ Guard Validation: ✓ F1 | ✓ F2    ← C'est ce qu'il faut!
📍 ROI: x: 8-1269, y: 514-552
```

### Guard Lines Panel (pendant FENCER_DETECTION)
```
⚔️ Adjust Guard Lines

Left Line (5m)           Right Line (9m)
[←] [-10px] [+10px] [→] [←] [-10px] [+10px] [→]
[ Reset ]                [ Reset ]
```

## 🆘 Problèmes courants

### "Piste not configured"
→ Cliquer "📐 Draw Piste" et valider

### "🔍 Waiting for fencers..."
→ Attendre que les 2 fencers prennent position (gauche & droite)

### "⚔️ Guard Validation: ✗ F1 | ✗ F2"
→ Les fencers ne sont pas sur les garde-lignes. Options:
1. Attendre qu'ils se repositionnent
2. Ajuster les garde-lignes (bouton ±10px)

## 🔧 API rapide

### Status validation
```bash
curl http://localhost:8001/api/guard-validation
```

### Ajuster garde-ligne
```bash
curl -X POST http://localhost:8001/api/adjust-guard-line \
  -H "Content-Type: application/json" \
  -d '{"line": "left", "offset_x": 10, "tilt": 1.0}'
```

### Réinitialiser
```bash
curl -X POST http://localhost:8001/api/reset-guard-lines
```

## 📊 Logs à surveiller

### ✅ Succès
```
[FencerTracker] ✓ LOCKED 2 fencers using guard lines!
  → Fencer 1 (LEFT): x=446 (left of 458px)
  → Fencer 2 (RIGHT): x=927 (right of 819px)
  → Separation: 481px
```

### ⚠️ En attente
```
[FencerTracker] 🔍 Waiting for fencers on guard lines...
```

### ❌ Problème
```
[FencerTracker] ⚠️ Fencers too close!
```

## 🎯 What's new?

Le système identifie maintenant les fencers par leur **position relative aux garde-lignes** :

- **Fencer 1** = Détecté à GAUCHE ← de la ligne 5m
- **Fencer 2** = Détecté à DROITE → de la ligne 9m

Plus besoin d'attendre 30 frames de clustering! Initialisation en 2-3 frames.

## 📚 Docs complètes

- `README.md` : Documentation complète
- `IMPLEMENTATION.md` : Détails techniques
- `CHANGELOG.md` : Modifications v1.1 → v2.0

## 🎬 Exemple d'utilisation typique

```bash
# Terminal 1 : Lancer le système
$ python main.py
[Pipeline] Starting...
[GuardLineDetector] Initial guard lines: 5m=458px, 7m=638px, 9m=819px

# Terminal 2 ou Browser : Interface web
$ open http://localhost:8001

# Actions utilisateur:
1. Draw piste
2. Validate
3. Wait for fencers to position
4. See ✓ F1 | ✓ F2 appear
5. Adjust if needed (buttons ±10px)
6. Start streaming
```

---

**Version 2.0 - Février 2026**
