import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration : config.json (base64) > variables d'environnement
# ---------------------------------------------------------------------------
def _load_config() -> Dict[str, str]:
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        decoded = {}
        for key in ("GLPI_URL", "GLPI_APP_TOKEN", "GLPI_USER_TOKEN"):
            if key in raw:
                decoded[key] = base64.b64decode(raw[key]).decode("utf-8")
        logger.info("Configuration chargÃ©e depuis config.json")
        return decoded
    logger.info("config.json absent, utilisation des variables d'environnement")
    return {}

_config = _load_config()
GLPI_URL        = _config.get("GLPI_URL",        os.environ.get("GLPI_URL", "")).rstrip("/")
GLPI_APP_TOKEN  = _config.get("GLPI_APP_TOKEN",  os.environ.get("GLPI_APP_TOKEN", ""))
GLPI_USER_TOKEN = _config.get("GLPI_USER_TOKEN", os.environ.get("GLPI_USER_TOKEN", ""))

# ---------------------------------------------------------------------------
# Mappings GLPI â†’ libellÃ©s lisibles
# ---------------------------------------------------------------------------
TICKET_STATUS = {
    1: "Nouveau",
    2: "En cours (attribuÃ©)",
    3: "En cours (planifiÃ©)",
    4: "En attente",
    5: "RÃ©solu",
    6: "Clos",
}

TICKET_TYPE = {
    1: "Incident",
    2: "Demande de service",
}

TICKET_PRIORITY = {
    1: "TrÃ¨s basse",
    2: "Basse",
    3: "Moyenne",
    4: "Haute",
    5: "TrÃ¨s haute",
    6: "Majeure",
}

TICKET_URGENCY = TICKET_PRIORITY  # mÃªme Ã©chelle
TICKET_IMPACT  = TICKET_PRIORITY  # mÃªme Ã©chelle

TASK_STATUS = {
    1: "Ã€ faire",
    2: "TerminÃ©e",
}

# ---------------------------------------------------------------------------
# Session GLPI (initialisÃ©e une fois au dÃ©marrage)
# ---------------------------------------------------------------------------
_session_token: Optional[str] = None


async def _init_session() -> str:
    """Initialise la session GLPI et retourne le session_token."""
    global _session_token
    url = f"{GLPI_URL}/apirest.php/initSession"
    headers = {
        "App-Token": GLPI_APP_TOKEN,
        "Authorization": f"user_token {GLPI_USER_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        _session_token = resp.json()["session_token"]
        logger.info("Session GLPI initialisÃ©e.")
        return _session_token


async def _get_session() -> str:
    """Retourne le session_token existant ou en crÃ©e un nouveau."""
    if not _session_token:
        return await _init_session()
    return _session_token


# ---------------------------------------------------------------------------
# Client GLPI
# ---------------------------------------------------------------------------
class GLPIClient:
    """Client async pour l'API REST GLPI."""

    def __init__(self) -> None:
        pass

    async def _headers(self) -> Dict[str, str]:
        return {
            "App-Token": GLPI_APP_TOKEN,
            "Session-Token": await _get_session(),
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """ExÃ©cute une requÃªte HTTP avec renouvellement automatique de session sur 401."""
        url = f"{GLPI_URL}{path}"
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.request(method, url, headers=await self._headers(), **kwargs)
            if resp.status_code == 401:
                logger.warning("Session expirÃ©e, renouvellement automatique...")
                await _init_session()
                resp = await client.request(method, url, headers=await self._headers(), **kwargs)
            resp.raise_for_status()
            return resp.json()

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, data: Dict[str, Any]) -> Any:
        return await self._request("POST", path, json=data)

    async def put(self, path: str, data: Dict[str, Any]) -> Any:
        return await self._request("PUT", path, json=data)

    async def delete(self, path: str) -> Any:
        return await self._request("DELETE", path)


def _enrich_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Ajoute des libellÃ©s lisibles aux champs numÃ©riques d'un ticket."""
    ticket["_status_label"]   = TICKET_STATUS.get(ticket.get("status"), "Inconnu")
    ticket["_type_label"]     = TICKET_TYPE.get(ticket.get("type"), "Inconnu")
    ticket["_priority_label"] = TICKET_PRIORITY.get(ticket.get("priority"), "Inconnue")
    ticket["_urgency_label"]  = TICKET_URGENCY.get(ticket.get("urgency"), "Inconnue")
    ticket["_impact_label"]   = TICKET_IMPACT.get(ticket.get("impact"), "Inconnu")
    return ticket


# ---------------------------------------------------------------------------
# Serveur MCP
# ---------------------------------------------------------------------------
mcp = FastMCP("GLPI MCP")
glpi = GLPIClient()


# â”€â”€ Session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@mcp.tool()
async def kill_session() -> Dict[str, str]:
    """Ferme proprement la session GLPI active."""
    global _session_token
    if not _session_token:
        return {"message": "Aucune session active."}
    await glpi.get("/apirest.php/killSession")
    _session_token = None
    return {"message": "Session fermÃ©e."}


# â”€â”€ Tickets â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@mcp.tool()
async def list_tickets(
    status: Optional[int] = None,
    ticket_type: Optional[int] = None,
    range_start: int = 0,
    range_limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Liste les tickets avec pagination optionnelle.
    - status : 1=Nouveau 2=En cours(attribuÃ©) 3=En cours(planifiÃ©) 4=En attente 5=RÃ©solu 6=Clos
    - ticket_type : 1=Incident 2=Demande de service
    - range_start / range_limit : pagination
    """
    params: Dict[str, Any] = {
        "range": f"{range_start}-{range_start + range_limit - 1}",
    }
    if status is not None:
        params["searchText[status]"] = status
    if ticket_type is not None:
        params["searchText[type]"] = ticket_type

    result = await glpi.get("/apirest.php/Ticket", params=params)
    if isinstance(result, list):
        return [_enrich_ticket(t) for t in result]
    return result


@mcp.tool()
async def get_ticket(ticket_id: int) -> Dict[str, Any]:
    """Retourne le dÃ©tail complet d'un ticket, avec libellÃ©s lisibles."""
    ticket = await glpi.get(f"/apirest.php/Ticket/{ticket_id}")
    return _enrich_ticket(ticket)


@mcp.tool()
async def search_tickets(
    keywords: Optional[str] = None,
    status: Optional[int] = None,
    ticket_type: Optional[int] = None,
    category_id: Optional[int] = None,
    assigned_user_id: Optional[int] = None,
    range_start: int = 0,
    range_limit: int = 50,
) -> Any:
    """
    Recherche avancÃ©e de tickets via l'API GLPI /search/Ticket.
    Tous les paramÃ¨tres sont optionnels et combinables.
    """
    criteria = []
    idx = 0

    if keywords:
        criteria += [
            {f"criteria[{idx}][field]": "1",        # Titre
             f"criteria[{idx}][searchtype]": "contains",
             f"criteria[{idx}][value]": keywords},
        ]
        idx += 1

    if status is not None:
        criteria.append({
            f"criteria[{idx}][field]": "12",
            f"criteria[{idx}][searchtype]": "equals",
            f"criteria[{idx}][value]": str(status),
        })
        idx += 1

    if ticket_type is not None:
        criteria.append({
            f"criteria[{idx}][field]": "14",
            f"criteria[{idx}][searchtype]": "equals",
            f"criteria[{idx}][value]": str(ticket_type),
        })
        idx += 1

    if category_id is not None:
        criteria.append({
            f"criteria[{idx}][field]": "7",
            f"criteria[{idx}][searchtype]": "equals",
            f"criteria[{idx}][value]": str(category_id),
        })
        idx += 1

    if assigned_user_id is not None:
        criteria.append({
            f"criteria[{idx}][field]": "5",
            f"criteria[{idx}][searchtype]": "equals",
            f"criteria[{idx}][value]": str(assigned_user_id),
        })
        idx += 1

    # Aplatir la liste de dicts en un seul dict de params
    params: Dict[str, Any] = {
        "range": f"{range_start}-{range_start + range_limit - 1}",
    }
    for c in criteria:
        params.update(c)

    return await glpi.get("/apirest.php/search/Ticket", params=params)


@mcp.tool()
async def create_ticket(
    name: str,
    content: str,
    ticket_type: int = 1,
    category_id: Optional[int] = None,
    priority: int = 3,
    assigned_user_id: Optional[int] = None,
    assigned_group_id: Optional[int] = None,
) -> Any:
    """
    CrÃ©e un nouveau ticket.
    - ticket_type : 1=Incident 2=Demande de service
    - priority : 1 (trÃ¨s basse) â†’ 6 (majeure)
    """
    input_data: Dict[str, Any] = {
        "name": name,
        "content": content,
        "type": ticket_type,
        "priority": priority,
    }
    if category_id:
        input_data["itilcategories_id"] = category_id
    if assigned_user_id:
        input_data["_users_id_assign"] = assigned_user_id
    if assigned_group_id:
        input_data["_groups_id_assign"] = assigned_group_id

    return await glpi.post("/apirest.php/Ticket", {"input": input_data})


@mcp.tool()
async def update_ticket(ticket_id: int, update_fields: Dict[str, Any]) -> Any:
    """
    Met Ã  jour un ticket. Passer uniquement les champs Ã  modifier.
    Exemples de champs : status, priority, name, content, itilcategories_id
    """
    return await glpi.put(f"/apirest.php/Ticket/{ticket_id}", {"input": update_fields})


@mcp.tool()
async def delete_ticket(ticket_id: int) -> Any:
    """Supprime un ticket par son ID."""
    return await glpi.delete(f"/apirest.php/Ticket/{ticket_id}")


# â”€â”€ CatÃ©gories â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@mcp.tool()
async def list_itil_categories() -> Any:
    """Liste toutes les catÃ©gories ITIL disponibles (Incident, Demande, Changement, ProblÃ¨me)."""
    return await glpi.get("/apirest.php/ITILCategory")


# â”€â”€ Suivis (ITILFollowup) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@mcp.tool()
async def list_followups(ticket_id: int) -> Any:
    """Liste tous les suivis d'un ticket."""
    return await glpi.get(f"/apirest.php/Ticket/{ticket_id}/ITILFollowup")


@mcp.tool()
async def add_followup(ticket_id: int, content: str, is_private: bool = False) -> Any:
    """
    Ajoute un suivi Ã  un ticket.
    - is_private : True pour un suivi visible uniquement par les techniciens
    """
    data = {
        "input": {
            "items_id": ticket_id,
            "itemtype": "Ticket",
            "content": content,
            "is_private": int(is_private),
        }
    }
    return await glpi.post("/apirest.php/ITILFollowup", data)


@mcp.tool()
async def get_followup(followup_id: int) -> Any:
    """Retourne le dÃ©tail d'un suivi spÃ©cifique."""
    return await glpi.get(f"/apirest.php/ITILFollowup/{followup_id}")


# â”€â”€ TÃ¢ches (ITILTask) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@mcp.tool()
async def list_tasks(ticket_id: int) -> Any:
    """Liste toutes les tÃ¢ches d'un ticket."""
    return await glpi.get(f"/apirest.php/Ticket/{ticket_id}/TicketTask")


@mcp.tool()
async def add_task(
    ticket_id: int,
    content: str,
    assigned_user_id: Optional[int] = None,
    duration_seconds: Optional[int] = None,
    is_private: bool = False,
    status: int = 1,
) -> Any:
    """
    CrÃ©e une tÃ¢che sur un ticket.
    - status : 1=Ã€ faire 2=TerminÃ©e
    - duration_seconds : durÃ©e en secondes (ex. 3600 = 1h)
    """
    input_data: Dict[str, Any] = {
        "tickets_id": ticket_id,
        "content": content,
        "is_private": int(is_private),
        "state": status,
    }
    if assigned_user_id:
        input_data["users_id_tech"] = assigned_user_id
    if duration_seconds is not None:
        input_data["actiontime"] = duration_seconds

    return await glpi.post("/apirest.php/TicketTask", {"input": input_data})


@mcp.tool()
async def update_task(task_id: int, update_fields: Dict[str, Any]) -> Any:
    """
    Met Ã  jour une tÃ¢che. Exemples : state (1/2), content, actiontime, users_id_tech
    """
    return await glpi.put(f"/apirest.php/TicketTask/{task_id}", {"input": update_fields})


@mcp.tool()
async def delete_task(task_id: int) -> Any:
    """Supprime une tÃ¢che."""
    return await glpi.delete(f"/apirest.php/TicketTask/{task_id}")


# â”€â”€ Solutions (ITILSolution) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@mcp.tool()
async def get_solution(ticket_id: int) -> Any:
    """Retourne la solution d'un ticket."""
    return await glpi.get(f"/apirest.php/Ticket/{ticket_id}/ITILSolution")


@mcp.tool()
async def add_solution(ticket_id: int, content: str, solution_type_id: Optional[int] = None) -> Any:
    """
    Poste une solution sur un ticket (le clÃ´ture automatiquement selon la config GLPI).
    - solution_type_id : ID du type de solution si applicable
    """
    input_data: Dict[str, Any] = {
        "items_id": ticket_id,
        "itemtype": "Ticket",
        "content": content,
    }
    if solution_type_id:
        input_data["solutiontypes_id"] = solution_type_id

    return await glpi.post("/apirest.php/ITILSolution", {"input": input_data})


# â”€â”€ Statistiques â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@mcp.tool()
async def stats_by_status() -> Dict[str, Any]:
    """Retourne le nombre de tickets ouverts par statut."""
    tickets = await glpi.get("/apirest.php/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de rÃ©cupÃ©rer les tickets", "raw": tickets}

    counts: Dict[str, int] = {label: 0 for label in TICKET_STATUS.values()}
    for t in tickets:
        label = TICKET_STATUS.get(t.get("status"), "Inconnu")
        counts[label] = counts.get(label, 0) + 1

    return {"total": len(tickets), "by_status": counts}


@mcp.tool()
async def stats_by_type() -> Dict[str, Any]:
    """Retourne le nombre de tickets par type (Incident / Demande de service)."""
    tickets = await glpi.get("/apirest.php/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de rÃ©cupÃ©rer les tickets", "raw": tickets}

    counts: Dict[str, int] = {label: 0 for label in TICKET_TYPE.values()}
    for t in tickets:
        label = TICKET_TYPE.get(t.get("type"), "Inconnu")
        counts[label] = counts.get(label, 0) + 1

    return {"total": len(tickets), "by_type": counts}


@mcp.tool()
async def stats_by_priority() -> Dict[str, Any]:
    """Retourne le nombre de tickets ouverts par prioritÃ©."""
    tickets = await glpi.get("/apirest.php/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de rÃ©cupÃ©rer les tickets", "raw": tickets}

    # Uniquement tickets non-clos
    open_tickets = [t for t in tickets if t.get("status") not in (5, 6)]
    counts: Dict[str, int] = {label: 0 for label in TICKET_PRIORITY.values()}
    for t in open_tickets:
        label = TICKET_PRIORITY.get(t.get("priority"), "Inconnue")
        counts[label] = counts.get(label, 0) + 1

    return {"total_open": len(open_tickets), "by_priority": counts}


# â”€â”€ Utilisateurs & Groupes (lecture seule) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@mcp.tool()
async def get_users() -> Any:
    """Liste les utilisateurs GLPI."""
    return await glpi.get("/apirest.php/User")


@mcp.tool()
async def get_groups() -> Any:
    """Liste les groupes GLPI."""
    return await glpi.get("/apirest.php/Group")


# ---------------------------------------------------------------------------
# Point d'entrÃ©e
# ---------------------------------------------------------------------------


# === Base de connaissances (KnowbaseItem) =====================================
# Le nom de classe GLPI est KnowbaseItem (sans 'ledge'), confirmé par
# front/knowbaseitem.form.php

@mcp.tool()
async def list_kb_articles(
    range_start: int = 0,
    range_limit: int = 50,
) -> Any:
    """Liste les articles de la base de connaissances GLPI."""
    params: Dict[str, Any] = {
        "range": f"{range_start}-{range_start + range_limit - 1}",
    }
    return await glpi.get("/apirest.php/KnowbaseItem", params=params)


@mcp.tool()
async def get_kb_article(article_id: int) -> Any:
    """Retourne le detail complet d'un article de la base de connaissances."""
    return await glpi.get(f"/apirest.php/KnowbaseItem/{article_id}")


@mcp.tool()
async def search_kb_articles(
    keywords: str,
    range_start: int = 0,
    range_limit: int = 50,
) -> Any:
    """Recherche des articles dans la base de connaissances par mots-cles."""
    # Champ 6 = nom/titre, champ 7 = contenu/reponse dans KnowbaseItem
    params: Dict[str, Any] = {
        "range": f"{range_start}-{range_start + range_limit - 1}",
        "criteria[0][link]": "AND",
        "criteria[0][field]": "6",
        "criteria[0][searchtype]": "contains",
        "criteria[0][value]": keywords,
        "criteria[1][link]": "OR",
        "criteria[1][field]": "7",
        "criteria[1][searchtype]": "contains",
        "criteria[1][value]": keywords,
    }
    return await glpi.get("/apirest.php/search/KnowbaseItem", params=params)


@mcp.tool()
async def create_kb_article(
    name: str,
    answer: str,
    category_id: Optional[int] = None,
    is_faq: bool = False,
) -> Any:
    """
    Cree un nouvel article dans la base de connaissances.
    - name : titre de l'article
    - answer : contenu / solution (HTML accepte)
    - category_id : ID de la categorie KB (optionnel)
    - is_faq : True pour publier dans la FAQ publique
    """
    input_data: Dict[str, Any] = {
        "name": name,
        "answer": answer,
        "is_faq": int(is_faq),
    }
    if category_id:
        input_data["knowbaseitemcategories_id"] = category_id
    return await glpi.post("/apirest.php/KnowbaseItem", {"input": input_data})


@mcp.tool()
async def update_kb_article(article_id: int, update_fields: Dict[str, Any]) -> Any:
    """
    Met a jour un article de la base de connaissances.
    Exemples de champs : name, answer, is_faq, knowbaseitemcategories_id
    """
    return await glpi.put(f"/apirest.php/KnowbaseItem/{article_id}", {"input": update_fields})


@mcp.tool()
async def list_kb_categories() -> Any:
    """Liste toutes les categories de la base de connaissances."""
    return await glpi.get("/apirest.php/KnowbaseItemCategory")


@mcp.tool()
async def get_kb_article_visibility(article_id: int) -> Dict[str, Any]:
    """
    Retourne les regles de visibilite d'un article KB :
    profils, groupes, utilisateurs et entites ayant acces.
    """
    profiles = await glpi.get(f"/apirest.php/KnowbaseItem/{article_id}/KnowbaseItem_Profile")
    groups   = await glpi.get(f"/apirest.php/KnowbaseItem/{article_id}/KnowbaseItem_Group")
    users    = await glpi.get(f"/apirest.php/KnowbaseItem/{article_id}/KnowbaseItem_User")
    entities = await glpi.get(f"/apirest.php/KnowbaseItem/{article_id}/Entity_KnowbaseItem")
    return {
        "profiles": profiles,
        "groups": groups,
        "users": users,
        "entities": entities,
    }


@mcp.tool()
async def add_kb_article_visibility_profile(
    article_id: int,
    profiles_id: int,
    entities_id: int = 0,
    is_recursive: bool = False,
) -> Any:
    """
    Ajoute un profil dans la visibilite d'un article KB.
    - profiles_id : ID du profil GLPI
    - entities_id : 0 = entite racine
    - is_recursive : appliquer aux sous-entites
    """
    return await glpi.post("/apirest.php/KnowbaseItem_Profile", {"input": {
        "knowbaseitems_id": article_id,
        "profiles_id": profiles_id,
        "entities_id": entities_id,
        "is_recursive": int(is_recursive),
    }})


@mcp.tool()
async def add_kb_article_visibility_group(
    article_id: int,
    groups_id: int,
    entities_id: int = 0,
    is_recursive: bool = False,
) -> Any:
    """
    Ajoute un groupe dans la visibilite d'un article KB.
    - groups_id : ID du groupe GLPI
    """
    return await glpi.post("/apirest.php/KnowbaseItem_Group", {"input": {
        "knowbaseitems_id": article_id,
        "groups_id": groups_id,
        "entities_id": entities_id,
        "is_recursive": int(is_recursive),
    }})


@mcp.tool()
async def update_kb_article_visibility_profile(
    visibility_id: int,
    update_fields: Dict[str, Any],
) -> Any:
    """
    Met a jour une regle de visibilite par profil d'un article KB.
    - visibility_id : ID de l'entree KnowbaseItem_Profile (obtenu via get_kb_article_visibility)
    - update_fields : champs a modifier, ex: {"entities_id": 1, "is_recursive": 1}
    """
    return await glpi.put(f"/apirest.php/KnowbaseItem_Profile/{visibility_id}", {"input": update_fields})


@mcp.tool()
async def update_kb_article_visibility_group(
    visibility_id: int,
    update_fields: Dict[str, Any],
) -> Any:
    """
    Met a jour une regle de visibilite par groupe d'un article KB.
    - visibility_id : ID de l'entree KnowbaseItem_Group (obtenu via get_kb_article_visibility)
    - update_fields : champs a modifier, ex: {"entities_id": 1, "is_recursive": 1}
    """
    return await glpi.put(f"/apirest.php/KnowbaseItem_Group/{visibility_id}", {"input": update_fields})
if __name__ == "__main__":
    mcp.run(transport="stdio")


