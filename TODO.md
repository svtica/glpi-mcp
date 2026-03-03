# GLPI MCP — TODO & Suivi d'avancement

## Légende
- [ ] À faire
- [x] Terminé
- [~] En cours / partiel

---

## 🔐 Authentification & Configuration

- [x] Outil `init_session` fonctionnel
- [x] Charger les credentials depuis variables d'environnement (`GLPI_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`)
- [x] Initialiser la session automatiquement au démarrage du serveur
- [x] Ajouter un outil `kill_session` pour fermer proprement la session
- [x] Gérer le renouvellement de session en cas d'expiration (retry automatique sur 401)

---

## 🎫 Tickets — CRUD de base

- [x] `list_tickets` — Lister tous les tickets
- [x] `get_ticket` — Détail d'un ticket
- [x] `create_ticket` — Créer un ticket
- [x] `update_ticket` — Modifier un ticket
- [x] `delete_ticket` — Supprimer un ticket
- [x] Ajouter la pagination sur `list_tickets` (paramètres `range`)
- [x] Ajouter le filtrage par statut, catégorie, type, assigné, date

---

## 🔍 Recherche & Navigation

- [x] `search_tickets` — Recherche avancée via l'API GLPI (`/search/Ticket`) avec critères multiples
- [x] Mapper les statuts numériques → libellés (`1=Nouveau`, `2=En cours (attribué)`, `3=En cours (planifié)`, `4=En attente`, `5=Résolu`, `6=Clos`)
- [x] Mapper les types → libellés (`1=Incident`, `2=Demande`)
- [x] Mapper les priorités → libellés (`1=Très basse` … `6=Majeure`)
- [x] `list_itil_categories` — Lister les catégories ITIL (Incident, Demande de service, Changement, Problème)

---

## 💬 Suivis (ITILFollowup)

- [x] `list_followups` — Lister les suivis d'un ticket
- [x] `add_followup` — Ajouter un suivi à un ticket
- [x] `get_followup` — Détail d'un suivi

---

## ✅ Tâches (ITILTask)

- [x] `list_tasks` — Lister les tâches d'un ticket
- [x] `add_task` — Créer une tâche sur un ticket
- [x] `update_task` — Modifier une tâche (statut, durée, assigné)
- [x] `delete_task` — Supprimer une tâche

---

## ✔️ Solutions (ITILSolution)

- [x] `get_solution` — Lire la solution d'un ticket
- [x] `add_solution` — Poster une solution / clôturer un ticket

---

## 📊 Statistiques

- [x] `stats_by_status` — Nombre de tickets par statut
- [x] `stats_by_type` — Nombre de tickets par type (Incident / Demande)
- [x] `stats_by_priority` — Tickets ouverts par priorité
- [x] `stats_by_category` — Nombre de tickets par catégorie ITIL
- [x] `stats_by_assignee` — Tickets par technicien assigné
- [x] `stats_resolution_time` — Délai moyen de résolution
- [x] `stats_overdue` — Tickets en retard par rapport au SLA

---

## 🔗 Liaison & Fusion de tickets

- [x] `link_tickets` — Lier deux tickets entre eux (lié, doublon, parent/enfant)
- [x] `list_ticket_links` — Lister les liens d'un ticket
- [x] `merge_tickets` — Fusionner des tickets source vers un ticket cible (copie suivis, lie comme doublon, ferme les sources)

---

## 🧹 Qualité & Robustesse

- [x] Supprimer les paramètres `base_url` / `app_token` / `session_token` de chaque outil (gérés globalement)
- [x] Gestion d'erreurs structurée (codes HTTP GLPI, messages explicites)
- [x] Supprimer `add_computer` (hors scope)
- [x] Ajouter `httpx` dans `pyproject.toml` comme dépendance officielle
- [x] Rédiger le README (installation, config, liste des outils, exemples Claude)

---

## 📅 Historique

| Date | Action |
|------|--------|
| 2026-02-23 | Analyse initiale du projet, définition du scope tickets |
| 2026-02-23 | Refactoring server.py : session globale, variables d'env, mappings lisibles, followups, tâches, solutions, recherche avancée, stats de base |
| 2026-03-03 | Gestion d'erreurs structurée dans _request(), fusion de tickets (merge_tickets, link_tickets, list_ticket_links), stats complètes (stats_by_category, stats_by_assignee, stats_resolution_time, stats_overdue) |
