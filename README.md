# GLPI MCP

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-green.svg)](LICENSE)

🇫🇷 **[Français](#français)** | 🇬🇧 **[English](#english)**

---

# Français

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

Renseignez ensuite les champs dans `config.json` :

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
| `list_kb_articles` | Liste les articles avec pagination. Si `range_start > 60` et `range_limit > 10`, `range_limit` est auto-clampé à 10 (les contenus HTML complets dans la réponse JSON dépassent souvent le `memory_limit` PHP-FPM côté GLPI au-delà). Quand le clamp s'applique, la réponse est un dict `{"_clamped_range_limit": 10, "_warning": "...", "items": [...]}` au lieu d'une liste. |
| `get_kb_article` | Détail complet d'un article |
| `search_kb_articles` | Recherche par mots-clés (titre par défaut ; passer `search_content=True` pour inclure le corps HTML — lent sans index FULLTEXT MySQL sur `knowbaseitems.answer`) |
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
- Toutes les requêtes HTTP ont un délai maximal de **30 secondes** (10 s pour la connexion). Au-delà, l'outil retourne un dict structuré avec les clés `error` et `detail` (libellés tirés de la table `LANG`) au lieu de pendre — par défaut en français : `{"error": "Timeout HTTP", "detail": "Requête > 30s — voir GLPI logs"}`. Si vous obtenez ce message de façon répétée, vérifiez les logs PHP-FPM/MySQL côté GLPI : la requête sous-jacente est probablement trop coûteuse (souvent une recherche full-text sans index).

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

---
---

# English

[MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that allows an AI assistant — such as **Claude** — to interact directly with your GLPI instance via its REST API.

Compatible with **GLPI 10** (endpoint `apirest.php`) and **GLPI 11** (endpoint `api.php/v1`).

Once configured, Claude can view, create and update tickets, add followups and tasks, post solutions, manage the knowledge base, and generate statistics, all in natural language from your conversation.

---

## Prerequisites

### 1. GLPI

- GLPI **10.x** or **11.x** (REST API is enabled by default)
- REST API must be enabled: **Setup → General → API → Enable Rest API → Yes**
- An **App-Token** created in GLPI: **Setup → General → API → Add an API client**
- A **User-Token** associated with your account: **My profile → API → Regenerate**

> ⚠️ The account associated with the User-Token must have sufficient permissions on tickets in GLPI (read, write, delete as needed).

### 2. Python

- Python **3.12 or higher**
- [uv](https://docs.astral.sh/uv/) (recommended)

```bash
# Check Python version
python --version

# Install uv if needed
pip install uv
```

### 3. Claude Desktop

- [Claude Desktop](https://claude.ai/download) installed on your machine
- A Claude account with access to **MCP integrations** (Pro plan or higher)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/svtica/glpi-mcp.git
cd glpi-mcp
```

### 2. Install dependencies

```bash
uv sync
```

---

## Configuration (per user)

The server reads its credentials from a **`config.json`** file located in the same folder as `server.py`. This file is **individual to each user** and must never be version-controlled (it is in `.gitignore`).

### Create your config.json

Copy the example file and fill in your values:

```bash
cp config.example.json config.json
```

Values must be encoded in **base64**:

**PowerShell:**
```powershell
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("https://glpi.mycompany.com"))
```

**Linux / macOS:**
```bash
echo -n "https://glpi.mycompany.com" | base64
```

Then fill in the fields in `config.json`:

| Field             | Description                                        |
|-------------------|----------------------------------------------------|
| `GLPI_URL`        | Base URL of your GLPI instance (without trailing `/`) |
| `GLPI_APP_TOKEN`  | App-Token created in GLPI API configuration        |
| `GLPI_USER_TOKEN` | User-Token from your GLPI account                  |
| `LANG`            | Label language: `fr` (default) or `en` — not base64-encoded |
| `GLPI_VERSION`    | GLPI version: `10` (default) or `11` — not base64-encoded |

> You can also use **environment variables** (`GLPI_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`, `GLPI_LANG`, `GLPI_VERSION`) instead of the `config.json` file.

### Supported GLPI versions

| Version | API Endpoint | Authentication |
|---------|-------------|----------------|
| **GLPI 10** | `apirest.php` | App-Token + User-Token → Session-Token |
| **GLPI 11** | `api.php/v1` | App-Token + User-Token → Session-Token (same mechanism) |

The `GLPI_VERSION` field determines which endpoint prefix is used. Both versions use the same session-based authentication (`initSession`). All tools are compatible with both versions.

---

## Integration with Claude Desktop

### Method 1 — Claude Extensions (recommended)

Copy the project contents to your Claude Extensions folder:

```
%APPDATA%\Claude\Claude Extensions\ant.dir.svtica.glpi-mcp\
```

Create your personal `config.json` with your credentials (see previous section).

The folder must contain a `manifest.json` file:

```json
{
  "manifest_version": "0.2",
  "name": "GLPI-MCP",
  "version": "0.1.0",
  "description": "MCP server for GLPI integration",
  "author": { "name": "Your Name", "url": "" },
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

Restart Claude Desktop. Each user on the machine copies their own files to their `%APPDATA%` folder with their own `config.json`.

### Method 2 — claude_desktop_config.json (manual)

Open the Claude Desktop configuration file:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add the `mcpServers` section:

**Windows**
```json
{
  "mcpServers": {
    "glpi": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Path\\to\\glpi-mcp",
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
        "/path/to/glpi-mcp",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

> ⚠️ Make sure the JSON is valid — a missing brace or comma is enough to prevent Claude Desktop from loading the configuration. Use a JSON validator if needed.

Restart Claude Desktop. If the configuration is correct, a 🔌 icon will appear in the Claude toolbar indicating the MCP server is connected.

---

## Available tools

### 🔐 Session

| Tool | Description |
|------|-------------|
| `kill_session` | Gracefully closes the active GLPI session |

### 🎫 Tickets

| Tool | Description |
|------|-------------|
| `list_tickets` | List tickets with pagination and filters (status, type) |
| `get_ticket` | Full ticket details with readable labels |
| `search_tickets` | Advanced search by keywords, status, type, category, assignee |
| `create_ticket` | Create a new ticket |
| `update_ticket` | Update fields of an existing ticket |
| `delete_ticket` | Delete a ticket |
| `link_tickets` | Link two tickets (linked, duplicate, child, parent) |
| `list_ticket_links` | List all links for a ticket |
| `merge_tickets` | Merge source tickets into a target (copies followups, links as duplicate, closes sources) |

### 💬 Followups

| Tool | Description |
|------|-------------|
| `list_followups` | List all followups for a ticket |
| `get_followup` | Followup details |
| `add_followup` | Add a followup (public or private) |

### ✅ Tasks

| Tool | Description |
|------|-------------|
| `list_tasks` | List tasks for a ticket |
| `add_task` | Create a task on a ticket |
| `update_task` | Update a task (status, duration, assignee) |
| `delete_task` | Delete a task |

### 💡 Solutions

| Tool | Description |
|------|-------------|
| `get_solution` | Read the solution for a ticket |
| `add_solution` | Post a solution (closes the ticket per GLPI config) |

### 📊 Statistics

| Tool | Description |
|------|-------------|
| `stats_by_status` | Ticket count by status |
| `stats_by_type` | Incidents vs Service Requests breakdown |
| `stats_by_priority` | Open tickets by priority |
| `stats_by_category` | Ticket count by ITIL category |
| `stats_by_assignee` | Tickets per assigned technician |
| `stats_resolution_time` | Average ticket resolution time |
| `stats_overdue` | Tickets overdue against SLA |

### 📚 Knowledge Base

| Tool | Description |
|------|-------------|
| `list_kb_articles` | List articles with pagination. If `range_start > 60` and `range_limit > 10`, `range_limit` is auto-clamped to 10 (full HTML article bodies in the JSON response often exceed the GLPI PHP-FPM `memory_limit` beyond that). When clamping kicks in, the response is a dict `{"_clamped_range_limit": 10, "_warning": "...", "items": [...]}` instead of a list. |
| `get_kb_article` | Full article details |
| `search_kb_articles` | Search by keywords (title only by default ; pass `search_content=True` to also match the HTML body — slow without a MySQL FULLTEXT index on `knowbaseitems.answer`) |
| `create_kb_article` | Create a new article (title, HTML content, category, FAQ) |
| `update_kb_article` | Update an existing article |
| `list_kb_categories` | List knowledge base categories |
| `get_kb_article_visibility` | Read visibility rules for an article (profiles, groups, users, entities) |
| `add_kb_article_visibility_profile` | Add a profile to an article's visibility |
| `add_kb_article_visibility_group` | Add a group to an article's visibility |
| `update_kb_article_visibility_profile` | Update an existing profile visibility rule |
| `update_kb_article_visibility_group` | Update an existing group visibility rule |

> **Note:** Deleting visibility rules is intentionally not exposed in order to preserve a history of procedures, even obsolete ones.

### 📋 Reference data

| Tool | Description |
|------|-------------|
| `list_itil_categories` | List available ITIL categories |
| `get_users` | List GLPI users |
| `get_groups` | List GLPI groups |

---

## Usage examples with Claude

> *"Show me all open high-priority incidents"*

> *"Create a service request ticket for installing Adobe Acrobat for Jane Smith"*

> *"Add a followup to ticket #4521 to inform the user that the issue is being investigated"*

> *"Merge tickets #4530 and #4531 into ticket #4521"*
>
> *"Link ticket #4530 to ticket #4521 as a duplicate"*
>
> *"What are the ticket statistics by status?"*
>
> *"What is the average ticket resolution time?"*
>
> *"Show me tickets that are overdue against the SLA"*

> *"Search the knowledge base for VPN troubleshooting solutions"*

> *"Who can see knowledge base article #120?"*

> *"Add the Technicians group to the visibility of article #120"*

> *"Close ticket #4102 with the solution: service restart resolved the issue"*

---

## Reference mappings

### Statuses
| Code | Label (fr) | Label (en) |
|------|------------|------------|
| 1 | Nouveau | New |
| 2 | En cours (attribué) | In progress (assigned) |
| 3 | En cours (planifié) | In progress (planned) |
| 4 | En attente | Pending |
| 5 | Résolu | Solved |
| 6 | Clos | Closed |

### Types
| Code | Label (fr) | Label (en) |
|------|------------|------------|
| 1 | Incident | Incident |
| 2 | Demande de service | Service request |

### Priorities / Urgencies / Impacts
| Code | Label (fr) | Label (en) |
|------|------------|------------|
| 1 | Très basse | Very low |
| 2 | Basse | Low |
| 3 | Moyenne | Medium |
| 4 | Haute | High |
| 5 | Très haute | Very high |
| 6 | Majeure | Major |

### Ticket link types
| Code | Label (fr) | Label (en) |
|------|------------|------------|
| 1 | Lié à | Linked to |
| 2 | Duplique | Duplicates |
| 3 | Enfant de | Child of |
| 4 | Parent de | Parent of |

---

## Troubleshooting

### Server does not appear in Claude Desktop

- Check the JSON syntax of the configuration file (no missing or extra commas/braces)
- Verify the folder path is correct and absolute
- Fully restart Claude Desktop
- Make sure the `%APPDATA%\Claude\connectors\` folder exists (create it if needed)

### 401 error on every call

- Verify that `GLPI_APP_TOKEN` and `GLPI_USER_TOKEN` are correct in your `config.json`
- Check that the REST API is enabled in GLPI
- Verify that the API client in GLPI is active and the IP is authorized

### Connection error / timeout

- Verify that `GLPI_URL` is reachable from the machine running the server
- Check that no firewall is blocking the connection
- All HTTP requests have a hard ceiling of **30 seconds** (10 s for connect). Beyond that, the tool returns a structured dict with `error` and `detail` (labels taken from the `LANG` table) instead of hanging — in English: `{"error": "HTTP timeout", "detail": "Request > 30s — see GLPI logs"}`. If you hit this repeatedly, inspect the PHP-FPM/MySQL logs on the GLPI side: the underlying query is likely too expensive (typically a full-text search without an index).

### Corporate environment — SSL-intercepting proxy (Zscaler, Forcepoint, etc.)

In corporate environments, an SSL proxy may intercept HTTPS connections and replace certificates with an internal certificate. This causes the following error when installing dependencies with `uv`:

```
× Failed to download `python-dotenv==X.X.X`
╰─▶ invalid peer certificate: UnknownIssuer
```

**Solution:** Force `uv` to use the Windows certificate store with the `UV_NATIVE_TLS` environment variable.

To test manually in PowerShell:
```powershell
$env:UV_NATIVE_TLS=1
uv run python server.py
```

To have Claude Desktop automatically pass this variable when starting the server, add an `env` section to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "glpi": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Path\\to\\glpi-mcp",
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

### Corporate environment — Antivirus / EDR blocking uv (Riskware)

Some corporate antivirus or EDR solutions may categorize `uv.exe` as **Riskware** because it downloads executables and packages from the Internet. If `uv` is blocked by your security solution:

- Contact your IT team to add an exception for `uv.exe` (located at `%USERPROFILE%\.local\bin\uv.exe`)
- Also request authorization for the domains: `pypi.org`, `files.pythonhosted.org`, `astral.sh`

As an alternative, ask a colleague with a working `uv` to share the `.venv` folder, which avoids any downloads.

### Reducing dependencies

The project depends on `mcp[cli]` which includes the `[cli]` extra (typer, rich, click, shellingham, pygments, markdown-it-py…). This extra provides the development commands `mcp dev` and `mcp inspect`, useful for debugging.

If you want to reduce the footprint in production (about 8 fewer packages), modify `pyproject.toml`:

```toml
# Before (with CLI tooling)
dependencies = ["mcp[cli]>=1.9.4", "httpx>=0.27"]

# After (without CLI tooling — lightweight production)
dependencies = ["mcp>=1.9.4", "httpx>=0.27"]
```

Then run `uv sync` again to update the environment.
