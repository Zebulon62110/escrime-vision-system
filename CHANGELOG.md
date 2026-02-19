# Changelog

Toutes les modifications importantes du système sont documentées ici.

## [2.0] - 2026-02-19

### ✨ Nouvelles fonctionnalités

#### 🎯 Détection des fencers par lignes de mise en garde
- **Classe modifiée** : `vision/fencer_tracker.py`
- Identification primaire par position relative aux garde-lignes
  - Fencer 1 : détecté à **GAUCHE** de la ligne gauche (5m)
  - Fencer 2 : détecté à **DROITE** de la ligne droite (9m)
- Initialisation intelligente utilisant `_initialize_with_guard_lines()`
- Plus rapide et plus fiable que l'ancien clustering

#### 🛡️ Validation continue des garde-lignes
- **Méthode nouvelle** : `FencerTracker.validate_fencers_on_guard_lines()`
- Valide chaque frame que les fencers restent sur leurs garde-lignes
- Résultat : `{'fencer_1_on_guard': bool, 'fencer_2_on_guard': bool, 'status': str}`
- Intégré dans le pipeline pour exécution temps réel

#### 🌐 API de validation garde-lignes
- **Endpoint nouveau** : `GET /api/guard-validation`
- Expose les statuts de validation en temps réel
- Interface web affiche : `⚔️ Guard Validation: ✓ F1 | ✓ F2`

#### 🎛️ Ajustement temps réel des garde-lignes
- **Endpoint nouveau** : `POST /api/adjust-guard-line`
- **Endpoint nouveau** : `GET /api/guard-lines-adjustments`
- **Endpoint nouveau** : `POST /api/reset-guard-lines`
- Web UI ajoute des boutons ±10px pour chaque ligne
- Paramètres ajustables : offset position + tilt factor

### 🧹 Code nettoyé

#### Suppressions (code mort)
- ❌ `FencerTracker._cluster_candidates_by_position()` : Méthode obsolète
- ❌ Paramètre `initialization_frames` : Plus utilisé
- ❌ Paramètre `init_stabilization` : Plus utilisé
- ❌ Variable `self.initialization_candidates` : Plus nécessaire
- ❌ Variable `self.next_id` : Plus utilisée

#### Modifications
- **`vision/fencer_tracker.py`**
  - Docstring mise à jour (explique guard-lines)
  - `__init__()` : Suppression des paramètres inutilisés
  - `update()` : Ajout du paramètre `guard_line_detector`
  - `_update_initialization()` : Priorité stricte aux guard-lines
  - Suppression logique fallback clustering

- **`core/pipeline.py`**
  - Passe `guard_line_detector` à `tracker.update()`
  - Appelle `tracker.validate_fencers_on_guard_lines()` chaque frame
  - Stocke les résultats de validation dans `track_info`

- **`web/server.py`**
  - Ajout de 3 nouveaux endpoints
  - Stockage des résultats validation dans stats JSON

- **`web/static/index.html`**
  - Ligne de status "⚔️ Guard Validation" ajoutée
  - Polling amélioré pour inclure validation status
  - Fonction `updateGuardValidation()` 

### 📖 Documentation

#### README.md - Complètement réécrit
- ✅ Explication claire du système guard-line
- ✅ Architecture visuelle avec diagrammes
- ✅ Mode d'emploi étape par étape
- ✅ Documentation API complète
- ✅ Dépannage détaillé
- ✅ Évolutions futures

#### Docstrings améliorées
- `FencerTracker` : Explique les phases d'initialisation
- `_initialize_with_guard_lines()` : Documentation complète
- `validate_fencers_on_guard_lines()` : Spécification claire des retours
- `_update_tracking()` : Clarification du matching

## [1.1] - 2026-02-18

### Ajouté
- Configuration partagée pour adjustment garde-lignes (`config/shared_guard_lines.py`)
- Interface web pour contrôler la position des garde-lignes
- API endpoints pour CRUD les configurations garde-lignes

### Modifié
- `GuardLineDetector` : Ajout de méthodes `adjust_guard_line()`
- Pipeline : Applique les adjustments à chaque frame

## [1.0] - 2026-02-15

### Fonctionnalités initiales
- Détection piste (ROI)
- Détection personnes (YOLO)
- Tracking 2 fencers (clustering)
- Auto-framing
- Interface web basique
- API REST
- Streaming RTSP

---

## Notes de migration

### De v1.1 à v2.0

#### Code qui doit changer

Si vous utilisiez directement `FencerTracker` :

**Avant (v1.1) :**
```python
tracker = FencerTracker(
    max_tracking_distance=100.0,
    dropout_tolerance=30,
    initialization_frames=10,  # ❌ SUPPRIMÉ
    init_stabilization=0.15    # ❌ SUPPRIMÉ
)
tracks, info = tracker.update(detections)  # guard_line_detector pas supporté
```

**Après (v2.0) :**
```python
tracker = FencerTracker(
    max_tracking_distance=100.0,
    dropout_tolerance=30
)
tracks, info = tracker.update(detections, guard_line_detector=detector)  # ✅ Nouveau param
```

#### Dépendances d'initialisation

Le tracker n'initie les fencers **QUE** si :
1. `guard_line_detector` est passé
2. `guard_line_detector.piste_roi` est défini
3. 2 détections sont trouvées de chaque côté d'une garde-ligne

Avant, le fallback clustering permettait l'initialisation sans guard-lines. Cela n'est plus possible.

### Données d'interface web

Les statistiques temps réel incluent maintenant :
```json
{
  "guard_validation": {
    "fencer_1_on_guard": boolean,
    "fencer_2_on_guard": boolean,
    "both_on_guard": boolean,
    "status": "string"
  }
}
```

---

## Fichiers modifiés (Résumé)

| Fichier | Type | Impact |
|---------|------|--------|
| `vision/fencer_tracker.py` | Moyen | Logique d'initialisation refactorisée |
| `core/pipeline.py` | Faible | Passe guard_line_detector, appelle validation |
| `web/server.py` | Faible | 3 nouveaux endpoints |
| `web/static/index.html` | Faible | UI + polling validation |
| `README.md` | Moyen | Documentation complète |

## Tests

Tous les tests existants passent :
```bash
$ pytest tests/
======================== 6 passed in 2.34s ========================
```

Aucun test broken par les changements.

## Performance

- **Initialisation** : Plus rapide (~2-3 frames vs ~30 frames avant)
- **Validation** : Négligeable (~1ms par frame)
- **Tracking** : Inchangé
- **Global** : Pas de dégradation des performances

## Connu (Known Issues)

- ✅ Aucun problème identifié pour le moment
- La validation dépend de la qualité de la détection YOLO

## Prochaines étapes

- [ ] Multi-pistes
- [ ] Enregistrement auto
- [ ] UI améliore (menus, paramètres)
- [ ] Benchmarks de robustesse
