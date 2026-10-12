# Gestion Projet BAN - Suivi de Vélocité

Calcul et suivi automatisé de la vélocité des sprints BAN basé sur le Project v2 GitHub.

## 🎯 Objectif

- Mesurer la vélocité (points Fibonacci complétés) à la fin de chaque sprint
- Maintenir un historique pour suivre les tendances
- Calculer la moyenne mobile sur 3 sprints
- Générer automatiquement un rapport d'équipe

## 🚀 Utilisation

### Lancer le calcul de vélocité

1. Allez dans **Actions** du dépôt
2. Sélectionnez **Calculate Sprint Velocity**
3. Cliquez sur **Run workflow**
4. Remplissez les paramètres :
   - **sprint_name** (optionnel) : ex. `Sprint Ban 80`
     - Si vide, prend le sprint le plus récent
   - **create_issue** (coché par défaut) : crée une issue de rapport

### Résultat

Le workflow :
- ✅ Récupère le champ **Sprint Ban** du Project v2
- ✅ Compte toutes les issues **fermées** de ce sprint
- ✅ Somme les points Fibonacci (labels `point-1`, `point-2`, etc.)
- ✅ Met à jour l'historique `data/sprint_history.json`
- ✅ Calcule la moyenne mobile sur 3 sprints
- ✅ Crée une issue de rapport avec les statistiques
- ✅ Commit automatiquement les changements

## 📋 Prérequis

Vos issues doivent respecter :

### 1. Champ Sprint Ban
- Remplir le champ **Sprint Ban** (type itération) dans le Project v2
- Exemple : `Sprint Ban 80`

### 2. Labels de points
- Ajouter un label de points selon Fibonacci :
  - `point-1`, `point-2`, `point-3`, `point-5`, `point-8`, `point-13`, `point-21`, `point-34`, `point-55`
  - Une issue peut avoir plusieurs labels de points (ils s'additionnent)

### 3. État de l'issue
- L'issue doit être **fermée** (state: closed) pour être comptabilisée
- Les Pull Requests sont ignorées

## 📊 Structure des données

### Historique JSON

Fichier : `data/sprint_history.json`

```json
[
  {
    "sprint": "Sprint Ban 80",
    "date": "2026-10-12T10:30:00Z",
    "points_completed": 34,
    "tickets_completed": 7,
    "moving_average_3": 33.67
  },
  {
    "sprint": "Sprint Ban 81",
    "date": "2026-11-12T10:30:00Z",
    "points_completed": 42,
    "tickets_completed": 9,
    "moving_average_3": 37.33
  }
]
```

### Champs

- **sprint** : nom du sprint (ex. "Sprint Ban 80")
- **date** : timestamp UTC du calcul
- **points_completed** : somme des points Fibonacci
- **tickets_completed** : nombre de tickets fermés avec points
- **moving_average_3** : moyenne mobile sur 3 derniers sprints

## 📈 Interprétation

### Vélocité
- Somme des points complétés dans le sprint
- Métrique clé pour la prévisibilité

### Moyenne mobile (3 sprints)
- Moyenne des 3 derniers sprints
- Lisse les variations court terme
- Utilisez pour prévoir la capacité future

### Tendance
- Stable : vélocité entre 90-110% de la moyenne
- Hausse : +10% de la moyenne
- Baisse : -10% de la moyenne

## 🔍 Exemple d'utilisation

**Fin du Sprint Ban 80 :**

1. Vérifiez que les issues sont :
   - Assignées à `Sprint Ban 80` (champ Sprint Ban)
   - Fermées
   - Tagged avec un label de points

2. Lancez le workflow :
   - `sprint_name` : `Sprint Ban 80`
   - `create_issue` : coché

3. Le workflow :
   - Récupère 34 points + 8 points = 42 points
   - Crée une issue : "📊 Rapport vélocité - Sprint Ban 80"
   - Met à jour l'historique
   - Calcule la moyenne mobile
   - Commit le fichier `data/sprint_history.json`

## 🔗 Fichiers

- `.github/workflows/sprint-velocity.yml` - Workflow GitHub Actions
- `scripts/calculate_velocity.py` - Script Python de calcul
- `data/sprint_history.json` - Historique versionné

## 📝 Notes

- L'historique est versionné dans Git pour la traçabilité
- Un rapport issue est créé à chaque calcul (peut être désactivé)
- Le script est idempotent : relancer sur le même sprint met à jour le record
- La moyenne mobile se recalcule à chaque exécution

## 🚨 Troubleshooting

### "No Sprint Ban iterations found"
- Vérifiez que le Project v2 a un champ nommé exactement **"Sprint Ban"**
- Le champ doit être de type **Iteration**

### "No iteration found matching"
- Vérifiez l'orthographe du nom du sprint
- Les sprints doivent exister dans le champ Sprint Ban du Project

### Points non comptabilisés
- Vérifiez que les labels sont nommés exactement `point-1`, `point-2`, etc.
- L'issue doit être **fermée**
- L'issue doit avoir le champ Sprint Ban rempli
