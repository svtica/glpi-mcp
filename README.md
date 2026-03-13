# GLPI MCP

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-green.svg)](LICENSE)

Serveur [MCP (Model Context Protocol)](https://modelcontextprotocol.io) permettant à un assistant IA — comme **Claude** — d'interagir directement avec votre instance GLPI via son API REST.

Compatible **GLPI 10** (endpoint `apirest.php`) et **GLPI 11** (endpoint `api.php/v1`).

Une fois configuré, Claude peut consulter, créer et mettre à jour des tickets, ajouter des suivis et des tâches, poster des solutions, gérer la base de connaissances, et produire des statistiques, le tout en langage naturel depuis votre conversation.

---

## Prérequis

### 1. GLPI

- GLPI **10.x** ou **11.x** (l'API REST est activée par défaut)
- L'API REST doit être activée : **Configuration → Générale → API → Activer l'API Rest → Oui**
- Un **App-Token** créé dans GLPI : **Configuration → Générale → API → Ajouter un client API**
- Un **User-Token** associé à votre compte : **Mon profil → API → Régénérer**

> ⚠️ Le compte associé au User-Token doit avoir les droits suffisants sur les tickets dans GLPI (lecture, écriture, suppression selon l'usage souhaité).

### 2. Python

- Python **3.12 ou supérieur**
- [uv](https://docs.astral.sh/uv/) (recommandé)

```bash
# Vérifier la version Python
python --version

# Installer uv si nécessaire
pip install uv
```

### 3. Claude Desktop

- [Claude Desktop](https://claude.ai/download) installé sur votre machine
- Un compte Claude avec accès aux **intégrations MCP** (plan Pro ou supérieur)

---

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/svtica/glpi-mcp.git
cd glpi-mcp
```

### 2. Installer les dépendances

```bash
uv sync
```

---

## Configuration (par utilisateur)

Le serveur lit ses credentials depuis un fichier **`config.json`** situé dans le même dossier que `server.py`. Ce fichier est **individuel à chaque utilisateur** et ne doit jamais être versionné (il est dans `.gitignore`).

### Créer votre config.json

Copiez le fichier exemple et renseignez vos valeurs :

```bash
cp config.example.json config.json
```

Les valeurs doivent être encodées en **base64** :

**PowerShell :**
```powershell
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("https://glpi.monentreprise.ca"))
```

**Linux / macOS :**
```bash
echo -n "https://glpi.monentreprise.ca" | base64
```

Renseignez ensuite les trois champs dans `config.json` :

| Champ             | Description                                        |
|-------------------|----------------------------------------------------|
| `GLPI_URL`        | URL de base de votre instance GLPI (sans `/` final) |
| `GLPI_APP_TOKEN`  | App-Token créé dans la configuration API GLPI      |
| `GLPI_USER_TOKEN` | User-Token de votre compte GLPI                    |
| `LANG`            | Langue des libellés : `fr` (défaut) ou `en` — non encodé en base64 |
| `GLPI_VERSION`    | Version GLPI : `10` (défaut) ou `11` — non encodé en base64 |

> Vous pouvez aussi utiliser des **variables d'environnement** (`GLPI_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`, `GLPI_LANG`, `GLPI_VERSION`) à la place du fichier `config.json`.

### Versions GLPI supportées

| Version | Endpoint API | Authentification |
|---------|-------------|------------------|
| **GLPI 10** | `apirest.php` | App-Token + User-Token → Session-Token |
| **GLPI 11** | `api.php/v1` | App-Token + User-Token → Session-Token (même mécanisme) |

Le champ `GLPI_VERSION` détermine quel préfixe d'endpoint est utilisé. Les deux versions utilisent la même authentification par session (`initSession`). Tous les outils sont compatibles avec les deux versions.

---

## Intégration avec Claude Desktop

### Méthode 1 — Claude Extensions (recommandée)

Copiez le contenu du projet dans votre dossier Claude Extensions :

```
%APPDATA%\Claude\Claude Extensions\ant.dir.svtica.glpi-mcp\
```

Créez-y votre `config.json` personnel avec vos credentials (voir section précédente).

Le dossier doit contenir un fichier `manifest.json` :

```json
{
  "manifest_version": "0.2",
  "name": "GLPI-MCP",
  "version": "0.1.0",
  "description": "Serveur MCP pour l'integration GLPI",
  "author": { "name": "Votre Nom", "url": "" },
  "server": {
    "type": "python",
    "entry_point": "server.py",
    "mcp_config": {
      "command": "uv",
      "args": ["--directory", "${__dirname}", "run", "python", "server.py"]
    }
  }
}
```

Redémarrez Claude Desktop. Chaque utilisateur de la machine copie ses propres fichiers dans son dossier `%APPDATA%` avec son propre `config.json`.

### Méthode 2 — claude_desktop_config.json (manuelle)

Ouvrez le fichier de configuration de Claude Desktop :

- **Windows** : `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS** : `~/Library/Application Support/Claude/claude_desktop_config.json`

Ajoutez la section `mcpServers` :

**Windows**
```json
{
  "mcpServers": {
    "glpi": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Chemin\\vers\\glpi-mcp",
        "run",
        "python",
        "server.py"
      ]
    }
  },
  "preferences": {
    "coworkScheduledTasksEnabled": false,
    "sidebarMode": "code"
  }
}
```

**macOS / Linux**
```json
{
  "mcpServers": {
    "glpi": {
      "command": "uv",
      "args": [
        "--directory",
        "/chemin/vers/glpi-mcp",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

> ⚠️ Assurez-vous que le JSON est valide — une accolade ou une virgule manquante suffit à empêcher Claude Desktop de charger la configuration. Utilisez un validateur JSON si nécessaire.

Redémarrez Claude Desktop. Si la configuration est correcte, une icône 🔌 apparaîtra dans la barre d'outils de Claude indiquant que le serveur MCP est connecté.

---

## Outils disponibles

### 🔐 Session

| Outil | Description |
|-------|-------------|
| `kill_session` | Ferme proprement la session GLPI active |

### 🎫 Tickets

| Outil | Description |
|-------|-------------|
| `list_tickets` | Liste les tickets avec pagination et filtres (statut, type) |
| `get_ticket` | Détail complet d'un ticket avec libellés lisibles |
| `search_tickets` | Recherche avancée par mots-clés, statut, type, catégorie, assigné |
| `create_ticket` | Crée un nouveau ticket |
| `update_ticket` | Modifie les champs d'un ticket existant |
| `delete_ticket` | Supprime un ticket |
| `link_tickets` | Lie deux tickets entre eux (lié, doublon, enfant, parent) |
| `list_ticket_links` | Liste tous les liens d'un ticket |
| `merge_tickets` | Fusionne des tickets source vers un ticket cible (copie suivis, lie comme doublon, ferme les sources) |

### 💬 Suivis

| Outil | Description |
|-------|-------------|
| `list_followups` | Liste tous les suivis d'un ticket |
| `get_followup` | Détail d'un suivi |
| `add_followup` | Ajoute un suivi (public ou privé) |

### ✅ Tâches

| Outil | Description |
|-------|-------------|
| `list_tasks` | Liste les tâches d'un ticket |
| `add_task` | Crée une tâche sur un ticket |
| `update_task` | Modifie une tâche (statut, durée, assigné) |
| `delete_task` | Supprime une tâche |

### 💡 Solutions

| Outil | Description |
|-------|-------------|
| `get_solution` | Lit la solution d'un ticket |
| `add_solution` | Poste une solution (clôture le ticket selon la config GLPI) |

### 📊 Statistiques

| Outil | Description |
|-------|-------------|
| `stats_by_status` | Nombre de tickets par statut |
| `stats_by_type` | Répartition Incidents / Demandes de service |
| `stats_by_priority` | Tickets ouverts par priorité |
| `stats_by_category` | Nombre de tickets par catégorie ITIL |
| `stats_by_assignee` | Tickets par technicien assigné |
| `stats_resolution_time` | Délai moyen de résolution des tickets |
| `stats_overdue` | Tickets en retard par rapport au SLA |

### 📚 Base de connaissances

| Outil | Description |
|-------|-------------|
| `list_kb_articles` | Liste les articles avec pagination |
| `get_kb_article` | Détail complet d'un article |
| `search_kb_articles` | Recherche par mots-clés (titre et contenu) |
| `create_kb_article` | Crée un nouvel article (titre, contenu HTML, catégorie, FAQ) |
| `update_kb_article` | Met à jour un article existant |
| `list_kb_categories` | Liste les catégories de la base de connaissances |
| `get_kb_article_visibility` | Lit les règles de visibilité d'un article (profils, groupes, utilisateurs, entités) |
| `add_kb_article_visibility_profile` | Ajoute un profil à la visibilité d'un article |
| `add_kb_article_visibility_group` | Ajoute un groupe à la visibilité d'un article |
| `update_kb_article_visibility_profile` | Modifie une règle de visibilité par profil existante |
| `update_kb_article_visibility_group` | Modifie une règle de visibilité par groupe existante |

> **Note :** La suppression de règles de visibilité n'est pas exposée volontairement afin de conserver un historique des procédures même obsolètes.

### 📋 Référentiels

| Outil | Description |
|-------|-------------|
| `list_itil_categories` | Liste les catégories ITIL disponibles |
| `get_users` | Liste les utilisateurs GLPI |
| `get_groups` | Liste les groupes GLPI |

---

## Exemples d'utilisation avec Claude

> *« Montre-moi tous les incidents ouverts en haute priorité »*

> *« Crée un ticket de demande de service pour l'installation d'Adobe Acrobat pour Marie Tremblay »*

> *« Ajoute un suivi sur le ticket #4521 pour informer l'utilisateur que le problème est en cours d'investigation »*

> *« Fusionne les tickets #4530 et #4531 vers le ticket #4521 »*
>
> *« Lie le ticket #4530 au ticket #4521 comme doublon »*
>
> *« Quelles sont les statistiques de tickets par statut ? »*
>
> *« Quel est le délai moyen de résolution des tickets ? »*
>
> *« Montre-moi les tickets en retard par rapport au SLA »*

> *« Cherche dans la base de connaissances une solution pour les problèmes VPN »*

> *« Qui peut voir l'article #120 de la base de connaissances ? »*

> *« Ajoute le groupe Techniciens à la visibilité de l'article #120 »*

> *« Clôture le ticket #4102 avec comme solution : redémarrage du service résolvant le problème »*

---

## Mappings de référence

### Statuts
| Code | Libellé |
|------|---------|
| 1 | Nouveau |
| 2 | En cours (attribué) |
| 3 | En cours (planifié) |
| 4 | En attente |
| 5 | Résolu |
| 6 | Clos |

### Types
| Code | Libellé |
|------|---------|
| 1 | Incident |
| 2 | Demande de service |

### Priorités / Urgences / Impacts
| Code | Libellé |
|------|---------|
| 1 | Très basse |
| 2 | Basse |
| 3 | Moyenne |
| 4 | Haute |
| 5 | Très haute |
| 6 | Majeure |

### Types de liens entre tickets
| Code | Libellé |
|------|---------|
| 1 | Lié à |
| 2 | Duplique |
| 3 | Enfant de |
| 4 | Parent de |

---

## Dépannage

### Le serveur n'apparaît pas dans Claude Desktop

- Vérifiez la syntaxe JSON du fichier de configuration (pas de virgule manquante ou en trop, pas d'accolade en trop)
- Vérifiez que le chemin vers le dossier est correct et absolu
- Redémarrez complètement Claude Desktop
- Assurez-vous que le dossier `%APPDATA%\Claude\connectors\` existe (créez-le si nécessaire)

### Erreur 401 à chaque appel

- Vérifiez que `GLPI_APP_TOKEN` et `GLPI_USER_TOKEN` sont corrects dans votre `config.json`
- Vérifiez que l'API REST est bien activée dans GLPI
- Vérifiez que le client API dans GLPI est actif et que l'IP est autorisée

### Erreur de connexion / timeout

- Vérifiez que `GLPI_URL` est accessible depuis la machine qui exécute le serveur
- Vérifiez qu'aucun pare-feu ne bloque la connexion

### Environnement corporatif — Proxy SSL intercepteur (Zscaler, Forcepoint, etc.)

En environnement d'entreprise, un proxy SSL peut intercepter les connexions HTTPS et remplacer les certificats par un certificat interne. Cela provoque l'erreur suivante lors de l'installation des dépendances par `uv` :

```
× Failed to download `python-dotenv==X.X.X`
╰─▶ invalid peer certificate: UnknownIssuer
```

**Solution :** Forcer `uv` à utiliser le magasin de certificats Windows avec la variable d'environnement `UV_NATIVE_TLS`.

Pour tester manuellement dans PowerShell :
```powershell
$env:UV_NATIVE_TLS=1
uv run python server.py
```

Pour que Claude Desktop passe automatiquement cette variable au démarrage du serveur, ajoutez une section `env` dans votre `claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "glpi": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Chemin\\vers\\glpi-mcp",
        "run",
        "python",
        "server.py"
      ],
      "env": {
        "UV_NATIVE_TLS": "1"
      }
    }
  }
}
```

### Environnement corporatif — Antivirus / EDR bloquant uv (Riskware)

Certains antivirus ou solutions EDR d'entreprise peuvent catégoriser `uv.exe` comme **Riskware** car il télécharge des exécutables et des packages depuis Internet. Si `uv` est bloqué par votre solution de sécurité :

- Contactez votre équipe TI pour qu'elle ajoute une exception pour `uv.exe` (situé dans `%USERPROFILE%\.local\bin\uv.exe`)
- Demandez également d'autoriser les domaines : `pypi.org`, `files.pythonhosted.org`, `astral.sh`

En alternative, demandez à un collègue ayant `uv` fonctionnel de vous transmettre le dossier `.venv` déjà généré, ce qui évite tout téléchargement.

### Alléger les dépendances

Le projet dépend de `mcp[cli]` qui inclut l'extra `[cli]` (typer, rich, click, shellingham, pygments, markdown-it-py…). Cet extra fournit les commandes de développement `mcp dev` et `mcp inspect`, utiles pour le débogage.

Si vous souhaitez réduire l'empreinte en production (environ 8 packages en moins), modifiez `pyproject.toml` :

```toml
# Avant (avec outillage CLI)
dependencies = ["mcp[cli]>=1.9.4", "httpx>=0.27"]

# Après (sans outillage CLI — production allégée)
dependencies = ["mcp>=1.9.4", "httpx>=0.27"]
```

Puis relancez `uv sync` pour mettre à jour l'environnement.
