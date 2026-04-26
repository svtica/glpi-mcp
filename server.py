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
        # LANG et GLPI_VERSION ne sont pas encodés en base64
        if "LANG" in raw:
            decoded["LANG"] = raw["LANG"]
        if "GLPI_VERSION" in raw:
            decoded["GLPI_VERSION"] = raw["GLPI_VERSION"]
        logger.info("Configuration chargée depuis config.json")
        return decoded
    logger.info("config.json absent, utilisation des variables d'environnement")
    return {}

_config = _load_config()
GLPI_URL        = _config.get("GLPI_URL",        os.environ.get("GLPI_URL", "")).rstrip("/")
GLPI_APP_TOKEN  = _config.get("GLPI_APP_TOKEN",  os.environ.get("GLPI_APP_TOKEN", ""))
GLPI_USER_TOKEN = _config.get("GLPI_USER_TOKEN", os.environ.get("GLPI_USER_TOKEN", ""))
LANG            = _config.get("LANG",            os.environ.get("GLPI_LANG", "fr")).lower()
GLPI_VERSION    = _config.get("GLPI_VERSION",    os.environ.get("GLPI_VERSION", "10"))

# ---------------------------------------------------------------------------
# Mappings GLPI — libellés lisibles (fr / en)
# ---------------------------------------------------------------------------
_MAPPINGS = {
    "fr": {
        "TICKET_STATUS": {
            1: "Nouveau",
            2: "En cours (attribué)",
            3: "En cours (planifié)",
            4: "En attente",
            5: "Résolu",
            6: "Clos",
        },
        "TICKET_TYPE": {
            1: "Incident",
            2: "Demande de service",
        },
        "TICKET_PRIORITY": {
            1: "Très basse",
            2: "Basse",
            3: "Moyenne",
            4: "Haute",
            5: "Très haute",
            6: "Majeure",
        },
        "TASK_STATUS": {
            1: "À faire",
            2: "Terminée",
        },
        "TICKET_LINK_TYPE": {
            1: "Lié à",
            2: "Duplique",
            3: "Enfant de",
            4: "Parent de",
        },
        "UNKNOWN":          "Inconnu",
        "UNKNOWN_F":        "Inconnue",
        "UNASSIGNED":       "Non assigné",
        "UNCATEGORIZED":    "Sans catégorie",
        "HTTP_TIMEOUT_ERROR":  "Timeout HTTP",
        "HTTP_TIMEOUT_DETAIL": "Requête > 30s — voir GLPI logs",
        "KB_CLAMP_WARNING": (
            "range_limit ramené à 10 car range_start > 60 "
            "(évite les erreurs PHP memory_limit côté GLPI sur de gros payloads KB)."
        ),
    },
    "en": {
        "TICKET_STATUS": {
            1: "New",
            2: "In progress (assigned)",
            3: "In progress (planned)",
            4: "Pending",
            5: "Solved",
            6: "Closed",
        },
        "TICKET_TYPE": {
            1: "Incident",
            2: "Service request",
        },
        "TICKET_PRIORITY": {
            1: "Very low",
            2: "Low",
            3: "Medium",
            4: "High",
            5: "Very high",
            6: "Major",
        },
        "TASK_STATUS": {
            1: "To do",
            2: "Done",
        },
        "TICKET_LINK_TYPE": {
            1: "Linked to",
            2: "Duplicates",
            3: "Child of",
            4: "Parent of",
        },
        "UNKNOWN":          "Unknown",
        "UNKNOWN_F":        "Unknown",
        "UNASSIGNED":       "Unassigned",
        "UNCATEGORIZED":    "Uncategorized",
        "HTTP_TIMEOUT_ERROR":  "HTTP timeout",
        "HTTP_TIMEOUT_DETAIL": "Request > 30s — see GLPI logs",
        "KB_CLAMP_WARNING": (
            "range_limit clamped to 10 because range_start > 60 "
            "(prevents PHP memory_limit errors on large KB payloads from GLPI)."
        ),
    },
}

_lang_data      = _MAPPINGS.get(LANG, _MAPPINGS["fr"])
TICKET_STATUS   = _lang_data["TICKET_STATUS"]
TICKET_TYPE     = _lang_data["TICKET_TYPE"]
TICKET_PRIORITY = _lang_data["TICKET_PRIORITY"]
TICKET_URGENCY  = TICKET_PRIORITY  # même échelle
TICKET_IMPACT   = TICKET_PRIORITY  # même échelle
TASK_STATUS     = _lang_data["TASK_STATUS"]
TICKET_LINK_TYPE = _lang_data["TICKET_LINK_TYPE"]
LABEL_UNKNOWN   = _lang_data["UNKNOWN"]
LABEL_UNKNOWN_F = _lang_data["UNKNOWN_F"]
LABEL_UNASSIGNED = _lang_data["UNASSIGNED"]
LABEL_UNCATEGORIZED = _lang_data["UNCATEGORIZED"]
LABEL_HTTP_TIMEOUT_ERROR  = _lang_data["HTTP_TIMEOUT_ERROR"]
LABEL_HTTP_TIMEOUT_DETAIL = _lang_data["HTTP_TIMEOUT_DETAIL"]
LABEL_KB_CLAMP_WARNING    = _lang_data["KB_CLAMP_WARNING"]

logger.info("Langue des libellés : %s", LANG)

# ---------------------------------------------------------------------------
# Préfixe API selon la version GLPI
# ---------------------------------------------------------------------------
if GLPI_VERSION == "11":
    _API_PREFIX = "/api.php/v1"
else:
    _API_PREFIX = "/apirest.php"

logger.info("Version GLPI : %s (préfixe API : %s)", GLPI_VERSION, _API_PREFIX)

# ---------------------------------------------------------------------------
# Session GLPI (initialisée une fois au démarrage)
# ---------------------------------------------------------------------------
_session_token: Optional[str] = None


# HTTP timeout applied to every httpx.AsyncClient created in this module.
# 30s read covers slow GLPI search queries; 10s connect catches firewall drops fast.
_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def _init_session() -> str:
    """Initialise la session GLPI et retourne le session_token."""
    global _session_token
    url = f"{GLPI_URL}{_API_PREFIX}/initSession"
    headers = {
        "App-Token": GLPI_APP_TOKEN,
        "Authorization": f"user_token {GLPI_USER_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(verify=False, timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        _session_token = resp.json()["session_token"]
        logger.info("Session GLPI initialisée.")
        return _session_token


async def _get_session() -> str:
    """Retourne le session_token existant ou en crée un nouveau."""
    if not _session_token:
        return await _init_session()
    return _session_token


# ---------------------------------------------------------------------------
# Client GLPI
# ---------------------------------------------------------------------------
class GLPIClient:
    """Client async pour l'API REST GLPI (compatible V10 et V11)."""

    def __init__(self) -> None:
        self.prefix = _API_PREFIX

    def _path(self, endpoint: str) -> str:
        """Construit le chemin complet avec le préfixe API."""
        return f"{self.prefix}{endpoint}"

    async def _headers(self) -> Dict[str, str]:
        return {
            "App-Token": GLPI_APP_TOKEN,
            "Session-Token": await _get_session(),
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Exécute une requête HTTP avec renouvellement automatique de session sur 401.

        Returns a structured error dict on httpx timeouts so callers do
        not have to handle raw exceptions. The 30s ceiling is enforced by
        the AsyncClient timeout configured at module level.
        """
        url = f"{GLPI_URL}{path}"
        try:
            async with httpx.AsyncClient(verify=False, timeout=_HTTP_TIMEOUT) as client:
                resp = await client.request(method, url, headers=await self._headers(), **kwargs)
                if resp.status_code == 401:
                    logger.warning("Session expirée, renouvellement automatique...")
                    await _init_session()
                    resp = await client.request(method, url, headers=await self._headers(), **kwargs)

                # --- Gestion d'erreurs structurée ---
                try:
                    body = resp.json()
                except Exception:
                    if resp.is_success:
                        return {"message": "Opération réussie (réponse vide)."}
                    return {
                        "error": f"Erreur HTTP {resp.status_code}",
                        "detail": resp.text[:500] if resp.text else "Réponse vide",
                    }

                # GLPI retourne parfois des erreurs sous forme ["ERROR_*", "message"]
                if isinstance(body, list) and len(body) == 2 and isinstance(body[0], str) and body[0].startswith("ERROR"):
                    error_code, error_msg = body[0], body[1]
                    if error_code in ("ERROR_SESSION_TOKEN_INVALID", "ERROR_SESSION_TOKEN_MISSING"):
                        logger.warning("Token de session invalide (%s), renouvellement...", error_code)
                        await _init_session()
                        resp = await client.request(method, url, headers=await self._headers(), **kwargs)
                        try:
                            body = resp.json()
                        except Exception:
                            if resp.is_success:
                                return {"message": "Opération réussie (réponse vide)."}
                            return {"error": f"Erreur HTTP {resp.status_code}", "detail": resp.text[:500]}
                        if isinstance(body, list) and len(body) == 2 and isinstance(body[0], str) and body[0].startswith("ERROR"):
                            return {"error": body[0], "message": body[1]}
                    else:
                        return {"error": error_code, "message": error_msg}

                # Erreurs HTTP classiques (4xx/5xx) avec body JSON
                if not resp.is_success:
                    return {"error": f"Erreur HTTP {resp.status_code}", "detail": body}

                return body
        except httpx.TimeoutException:
            logger.error("HTTP timeout (>30s) on %s %s", method, url)
            return {
                "error": LABEL_HTTP_TIMEOUT_ERROR,
                "detail": LABEL_HTTP_TIMEOUT_DETAIL,
            }

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return await self._request("GET", self._path(endpoint), params=params)

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Any:
        return await self._request("POST", self._path(endpoint), json=data)

    async def put(self, endpoint: str, data: Dict[str, Any]) -> Any:
        return await self._request("PUT", self._path(endpoint), json=data)

    async def delete(self, endpoint: str) -> Any:
        return await self._request("DELETE", self._path(endpoint))


def _enrich_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Ajoute des libellés lisibles aux champs numériques d'un ticket."""
    ticket["_status_label"]   = TICKET_STATUS.get(ticket.get("status"), LABEL_UNKNOWN)
    ticket["_type_label"]     = TICKET_TYPE.get(ticket.get("type"), LABEL_UNKNOWN)
    ticket["_priority_label"] = TICKET_PRIORITY.get(ticket.get("priority"), LABEL_UNKNOWN_F)
    ticket["_urgency_label"]  = TICKET_URGENCY.get(ticket.get("urgency"), LABEL_UNKNOWN_F)
    ticket["_impact_label"]   = TICKET_IMPACT.get(ticket.get("impact"), LABEL_UNKNOWN)
    return ticket


# ---------------------------------------------------------------------------
# Serveur MCP
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "GLPI MCP",
    instructions=(
        "IMPORTANT: All text content fields sent to GLPI (such as 'content', 'answer', "
        "'name', etc.) MUST be formatted in GLPI-compatible HTML. Never use Markdown syntax. "
        "Use HTML tags instead: <p> for paragraphs, <strong> for bold, <em> for italic, "
        "<ul>/<li> for bullet lists, <ol>/<li> for numbered lists, <h1>-<h3> for headings, "
        "<code> for inline code, <pre> for code blocks, <br> for line breaks. "
        "Do NOT use #, **, *, ``` or any other Markdown syntax in content fields."
    ),
)
glpi = GLPIClient()


# ---------------------------------------------------------------------------
# Search-option discovery (per itemtype)
# ---------------------------------------------------------------------------
# GLPI search criteria use numeric field IDs whose meaning depends on the
# itemtype AND the GLPI version. KnowbaseItem field 6 is the title in
# GLPI 10 but the same numeric ID can resolve to a different column on
# GLPI 11, which surfaces as
#     ["ERROR", "Identifiant de champ incorrect dans le critère de recherche"].
# To stay version-agnostic we discover the IDs at runtime via
# listSearchOptions/{itemtype} and look them up by their stable column name
# (the meta["field"] attribute, which is locale-independent unlike
# meta["name"]). The result is cached for the lifetime of the process.
_search_options_cache: Dict[str, Dict[str, str]] = {}


async def _discover_search_options(itemtype: str) -> Dict[str, str]:
    """Return a dict mapping column name -> numeric search-option ID.

    Falls back to an empty dict on any error (network, schema mismatch,
    endpoint absent). Callers must always pass an explicit default to
    `_resolve_search_field_id` so the legacy GLPI 10 numbering keeps
    working when discovery is unavailable.
    """
    if itemtype in _search_options_cache:
        return _search_options_cache[itemtype]

    try:
        result = await glpi.get(f"/listSearchOptions/{itemtype}")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("listSearchOptions/%s a échoué : %s", itemtype, exc)
        _search_options_cache[itemtype] = {}
        return {}

    if not isinstance(result, dict):
        logger.warning(
            "listSearchOptions/%s n'a pas retourné un dict (%s) ; fallback aux IDs par défaut.",
            itemtype,
            type(result).__name__,
        )
        _search_options_cache[itemtype] = {}
        return {}

    # GLPI returns an error payload as {"error": ..., "detail": ...} when
    # the endpoint is not reachable on the active API prefix; treat that
    # as "discovery failed" and fall back silently.
    if "error" in result and "detail" in result:
        logger.info(
            "Discovery search options indisponible pour %s (%s); fallback aux IDs par défaut.",
            itemtype,
            result.get("error"),
        )
        _search_options_cache[itemtype] = {}
        return {}

    mapping: Dict[str, str] = {}
    for field_id, meta in result.items():
        if not str(field_id).isdigit():
            continue
        if not isinstance(meta, dict):
            continue
        column = (meta.get("field") or "").strip().lower()
        if column:
            mapping.setdefault(column, str(field_id))
    _search_options_cache[itemtype] = mapping
    logger.info("Découverte de %d options de recherche pour %s.", len(mapping), itemtype)
    return mapping


async def _resolve_search_field_id(itemtype: str, column: str, default: str) -> str:
    """Resolve a numeric search-option ID by column name, with a fallback.

    The default is the legacy GLPI 10 ID; it keeps the tool working when
    listSearchOptions is unavailable (older instance, restricted profile,
    different API prefix).
    """
    mapping = await _discover_search_options(itemtype)
    return mapping.get(column.lower(), default)


# ── Session ────────────────────────────────────────────────────────────────

@mcp.tool()
async def kill_session() -> Dict[str, str]:
    """Ferme proprement la session GLPI active."""
    global _session_token
    if not _session_token:
        return {"message": "Aucune session active."}
    await glpi.get("/killSession")
    _session_token = None
    return {"message": "Session fermée."}


# ── Tickets ────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_tickets(
    status: Optional[int] = None,
    ticket_type: Optional[int] = None,
    range_start: int = 0,
    range_limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Liste les tickets avec pagination optionnelle.
    - status : 1=Nouveau 2=En cours(attribué) 3=En cours(planifié) 4=En attente 5=Résolu 6=Clos
    - type : 1=Incident 2=Demande de service
    - range_start / range_limit : pagination
    """
    params: Dict[str, Any] = {
        "range": f"{range_start}-{range_start + range_limit - 1}",
    }
    if status is not None:
        params["searchText[status]"] = status
    if ticket_type is not None:
        params["searchText[type]"] = ticket_type

    result = await glpi.get("/Ticket", params=params)
    if isinstance(result, list):
        return [_enrich_ticket(t) for t in result]
    return result


@mcp.tool()
async def get_ticket(ticket_id: int) -> Dict[str, Any]:
    """Retourne le détail complet d'un ticket, avec libellés lisibles."""
    ticket = await glpi.get(f"/Ticket/{ticket_id}")
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
    Recherche avancée de tickets via l'API GLPI /search/Ticket.
    Tous les paramètres sont optionnels et combinables.
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

    return await glpi.get("/search/Ticket", params=params)


@mcp.tool()
async def create_ticket(
    name: str,
    content: str,
    type: int = 1,
    category_id: Optional[int] = None,
    priority: int = 3,
    assigned_user_id: Optional[int] = None,
    assigned_group_id: Optional[int] = None,
) -> Any:
    """
    Crée un nouveau ticket.
    - type : 1=Incident 2=Demande de service
    - priority : 1 (très basse) → 6 (majeure)
    """
    input_data: Dict[str, Any] = {
        "name": name,
        "content": content,
        "type": type,
        "priority": priority,
    }
    if category_id:
        input_data["itilcategories_id"] = category_id
    if assigned_user_id:
        input_data["_users_id_assign"] = assigned_user_id
    if assigned_group_id:
        input_data["_groups_id_assign"] = assigned_group_id

    return await glpi.post("/Ticket", {"input": input_data})


@mcp.tool()
async def update_ticket(ticket_id: int, update_fields: Dict[str, Any]) -> Any:
    """
    Met à jour un ticket. Passer uniquement les champs à modifier.
    Exemples de champs : status, priority, name, content, itilcategories_id
    """
    return await glpi.put(f"/Ticket/{ticket_id}", {"input": update_fields})


@mcp.tool()
async def delete_ticket(ticket_id: int) -> Any:
    """Supprime un ticket par son ID."""
    return await glpi.delete(f"/Ticket/{ticket_id}")


# ── Liaison de tickets ─────────────────────────────────────────────────────

@mcp.tool()
async def link_tickets(
    ticket_id_1: int,
    ticket_id_2: int,
    link_type: int = 1,
) -> Any:
    """
    Crée un lien entre deux tickets.
    - link_type : 1=Lié à, 2=Duplique, 3=Enfant de, 4=Parent de
    """
    return await glpi.post("/Ticket_Ticket", {"input": {
        "tickets_id_1": ticket_id_1,
        "tickets_id_2": ticket_id_2,
        "link": link_type,
    }})


@mcp.tool()
async def list_ticket_links(ticket_id: int) -> Any:
    """Liste tous les liens d'un ticket avec d'autres tickets."""
    result = await glpi.get(f"/Ticket/{ticket_id}/Ticket_Ticket")
    if isinstance(result, list):
        for link in result:
            link["_link_label"] = TICKET_LINK_TYPE.get(link.get("link"), LABEL_UNKNOWN)
    return result


@mcp.tool()
async def merge_tickets(
    target_ticket_id: int,
    source_ticket_ids: List[int],
    add_followups: bool = True,
    close_source: bool = True,
) -> Dict[str, Any]:
    """
    Fusionne un ou plusieurs tickets source vers un ticket cible.
    - Lie chaque ticket source au ticket cible comme doublon (link_type=2)
    - Copie les suivis des tickets source vers le ticket cible (si add_followups=True)
    - Ferme les tickets source avec un suivi explicatif (si close_source=True)

    Paramètres :
    - target_ticket_id : ID du ticket cible (celui qui reste ouvert)
    - source_ticket_ids : liste des IDs de tickets à fusionner dans le cible
    - add_followups : copier les suivis des tickets source vers le cible
    - close_source : fermer les tickets source après la fusion
    """
    results: Dict[str, Any] = {
        "target_ticket_id": target_ticket_id,
        "merged": [],
        "errors": [],
    }

    for src_id in source_ticket_ids:
        merge_result: Dict[str, Any] = {"source_ticket_id": src_id}
        try:
            # 1. Lier comme doublon
            link_resp = await glpi.post("/Ticket_Ticket", {"input": {
                "tickets_id_1": src_id,
                "tickets_id_2": target_ticket_id,
                "link": 2,  # Duplique
            }})
            merge_result["link"] = link_resp

            # 2. Copier les suivis vers le ticket cible
            if add_followups:
                followups = await glpi.get(f"/Ticket/{src_id}/ITILFollowup")
                copied = 0
                if isinstance(followups, list):
                    for fu in followups:
                        fu_content = fu.get("content", "")
                        fu_private = fu.get("is_private", 0)
                        prefix = f"[Fusionné depuis ticket #{src_id}] "
                        await glpi.post("/ITILFollowup", {"input": {
                            "items_id": target_ticket_id,
                            "itemtype": "Ticket",
                            "content": prefix + fu_content,
                            "is_private": fu_private,
                        }})
                        copied += 1
                merge_result["followups_copied"] = copied

            # 3. Fermer le ticket source
            if close_source:
                close_msg = f"Ticket fusionné vers le ticket #{target_ticket_id}."
                await glpi.post("/ITILFollowup", {"input": {
                    "items_id": src_id,
                    "itemtype": "Ticket",
                    "content": close_msg,
                    "is_private": 0,
                }})
                await glpi.put(f"/Ticket/{src_id}", {"input": {
                    "status": 6,  # Clos
                }})
                merge_result["closed"] = True

            results["merged"].append(merge_result)
        except Exception as e:
            merge_result["error"] = str(e)
            results["errors"].append(merge_result)

    return results


# ── Catégories ─────────────────────────────────────────────────────────────

@mcp.tool()
async def list_itil_categories() -> Any:
    """Liste toutes les catégories ITIL disponibles (Incident, Demande, Changement, Problème)."""
    return await glpi.get("/ITILCategory")


# ── Suivis (ITILFollowup) ──────────────────────────────────────────────────

@mcp.tool()
async def list_followups(ticket_id: int) -> Any:
    """Liste tous les suivis d'un ticket."""
    return await glpi.get(f"/Ticket/{ticket_id}/ITILFollowup")


@mcp.tool()
async def add_followup(ticket_id: int, content: str, is_private: bool = False) -> Any:
    """
    Ajoute un suivi à un ticket.
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
    return await glpi.post("/ITILFollowup", data)


@mcp.tool()
async def get_followup(followup_id: int) -> Any:
    """Retourne le détail d'un suivi spécifique."""
    return await glpi.get(f"/ITILFollowup/{followup_id}")


# ── Tâches (ITILTask) ──────────────────────────────────────────────────────

@mcp.tool()
async def list_tasks(ticket_id: int) -> Any:
    """Liste toutes les tâches d'un ticket."""
    return await glpi.get(f"/Ticket/{ticket_id}/TicketTask")


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
    Crée une tâche sur un ticket.
    - status : 1=À faire 2=Terminée
    - duration_seconds : durée en secondes (ex. 3600 = 1h)
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

    return await glpi.post("/TicketTask", {"input": input_data})


@mcp.tool()
async def update_task(task_id: int, update_fields: Dict[str, Any]) -> Any:
    """
    Met à jour une tâche. Exemples : state (1/2), content, actiontime, users_id_tech
    """
    return await glpi.put(f"/TicketTask/{task_id}", {"input": update_fields})


@mcp.tool()
async def delete_task(task_id: int) -> Any:
    """Supprime une tâche."""
    return await glpi.delete(f"/TicketTask/{task_id}")


# ── Solutions (ITILSolution) ───────────────────────────────────────────────

@mcp.tool()
async def get_solution(ticket_id: int) -> Any:
    """Retourne la solution d'un ticket."""
    return await glpi.get(f"/Ticket/{ticket_id}/ITILSolution")


@mcp.tool()
async def add_solution(ticket_id: int, content: str, solution_type_id: Optional[int] = None) -> Any:
    """
    Poste une solution sur un ticket (le clôture automatiquement selon la config GLPI).
    - solution_type_id : ID du type de solution si applicable
    """
    input_data: Dict[str, Any] = {
        "items_id": ticket_id,
        "itemtype": "Ticket",
        "content": content,
    }
    if solution_type_id:
        input_data["solutiontypes_id"] = solution_type_id

    return await glpi.post("/ITILSolution", {"input": input_data})


# ── Statistiques ───────────────────────────────────────────────────────────

@mcp.tool()
async def stats_by_status() -> Dict[str, Any]:
    """Retourne le nombre de tickets ouverts par statut."""
    tickets = await glpi.get("/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de récupérer les tickets", "raw": tickets}

    counts: Dict[str, int] = {label: 0 for label in TICKET_STATUS.values()}
    for t in tickets:
        label = TICKET_STATUS.get(t.get("status"), LABEL_UNKNOWN)
        counts[label] = counts.get(label, 0) + 1

    return {"total": len(tickets), "by_status": counts}


@mcp.tool()
async def stats_by_type() -> Dict[str, Any]:
    """Retourne le nombre de tickets par type (Incident / Demande de service)."""
    tickets = await glpi.get("/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de récupérer les tickets", "raw": tickets}

    counts: Dict[str, int] = {label: 0 for label in TICKET_TYPE.values()}
    for t in tickets:
        label = TICKET_TYPE.get(t.get("type"), LABEL_UNKNOWN)
        counts[label] = counts.get(label, 0) + 1

    return {"total": len(tickets), "by_type": counts}


@mcp.tool()
async def stats_by_priority() -> Dict[str, Any]:
    """Retourne le nombre de tickets ouverts par priorité."""
    tickets = await glpi.get("/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de récupérer les tickets", "raw": tickets}

    # Uniquement tickets non-clos
    open_tickets = [t for t in tickets if t.get("status") not in (5, 6)]
    counts: Dict[str, int] = {label: 0 for label in TICKET_PRIORITY.values()}
    for t in open_tickets:
        label = TICKET_PRIORITY.get(t.get("priority"), LABEL_UNKNOWN_F)
        counts[label] = counts.get(label, 0) + 1

    return {"total_open": len(open_tickets), "by_priority": counts}


@mcp.tool()
async def stats_by_category() -> Dict[str, Any]:
    """Retourne le nombre de tickets par catégorie ITIL."""
    tickets = await glpi.get("/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de récupérer les tickets", "raw": tickets}

    # Charger les catégories pour les libellés
    categories = await glpi.get("/ITILCategory", params={"range": "0-9999"})
    cat_map: Dict[int, str] = {}
    if isinstance(categories, list):
        for cat in categories:
            cat_map[cat.get("id", 0)] = cat.get("completename", cat.get("name", LABEL_UNKNOWN))

    counts: Dict[str, int] = {}
    for t in tickets:
        cat_id = t.get("itilcategories_id", 0)
        label = cat_map.get(cat_id, LABEL_UNCATEGORIZED) if cat_id else LABEL_UNCATEGORIZED
        counts[label] = counts.get(label, 0) + 1

    return {"total": len(tickets), "by_category": counts}


@mcp.tool()
async def stats_by_assignee() -> Dict[str, Any]:
    """Retourne le nombre de tickets par technicien assigné."""
    tickets = await glpi.get("/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de récupérer les tickets", "raw": tickets}

    # Charger les utilisateurs pour les noms
    users = await glpi.get("/User", params={"range": "0-9999"})
    user_map: Dict[int, str] = {}
    if isinstance(users, list):
        for u in users:
            user_map[u.get("id", 0)] = u.get("realname", u.get("name", LABEL_UNKNOWN))

    counts: Dict[str, int] = {}
    for t in tickets:
        user_id = t.get("users_id_lastupdater", 0)
        assigned = t.get("_users_id_assign", user_id)
        if isinstance(assigned, list):
            for a in assigned:
                uid = a if isinstance(a, int) else a.get("users_id", 0)
                label = user_map.get(uid, f"User #{uid}")
                counts[label] = counts.get(label, 0) + 1
        else:
            uid = assigned if isinstance(assigned, int) else 0
            label = user_map.get(uid, LABEL_UNASSIGNED) if uid else LABEL_UNASSIGNED
            counts[label] = counts.get(label, 0) + 1

    return {"total": len(tickets), "by_assignee": counts}


@mcp.tool()
async def stats_resolution_time() -> Dict[str, Any]:
    """Retourne le délai moyen de résolution des tickets résolus ou clos."""
    tickets = await glpi.get("/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de récupérer les tickets", "raw": tickets}

    from datetime import datetime

    resolved = [t for t in tickets if t.get("status") in (5, 6)]
    deltas: List[float] = []

    for t in resolved:
        date_open = t.get("date")
        date_solved = t.get("solvedate")
        if date_open and date_solved:
            try:
                dt_open = datetime.fromisoformat(date_open)
                dt_solved = datetime.fromisoformat(date_solved)
                delta_hours = (dt_solved - dt_open).total_seconds() / 3600
                if delta_hours >= 0:
                    deltas.append(delta_hours)
            except (ValueError, TypeError):
                continue

    avg_hours = round(sum(deltas) / len(deltas), 2) if deltas else 0
    return {
        "resolved_count": len(resolved),
        "with_dates": len(deltas),
        "avg_resolution_hours": avg_hours,
        "avg_resolution_days": round(avg_hours / 24, 2) if avg_hours else 0,
    }


@mcp.tool()
async def stats_overdue() -> Dict[str, Any]:
    """
    Retourne les tickets en retard (date d'échéance dépassée et non résolus).
    Utilise le champ time_to_resolve de GLPI.
    """
    tickets = await glpi.get("/Ticket", params={"range": "0-9999"})
    if not isinstance(tickets, list):
        return {"error": "Impossible de récupérer les tickets", "raw": tickets}

    from datetime import datetime

    now = datetime.now()
    open_tickets = [t for t in tickets if t.get("status") not in (5, 6)]
    overdue: List[Dict[str, Any]] = []

    for t in open_tickets:
        ttr = t.get("time_to_resolve")
        if ttr:
            try:
                deadline = datetime.fromisoformat(ttr)
                if deadline < now:
                    overdue.append({
                        "id": t.get("id"),
                        "name": t.get("name"),
                        "deadline": ttr,
                        "overdue_hours": round((now - deadline).total_seconds() / 3600, 1),
                        "_status_label": TICKET_STATUS.get(t.get("status"), LABEL_UNKNOWN),
                        "_priority_label": TICKET_PRIORITY.get(t.get("priority"), LABEL_UNKNOWN_F),
                    })
            except (ValueError, TypeError):
                continue

    overdue.sort(key=lambda x: x.get("overdue_hours", 0), reverse=True)
    return {
        "total_open": len(open_tickets),
        "overdue_count": len(overdue),
        "overdue_tickets": overdue,
    }


# ── Utilisateurs & Groupes (lecture seule) ─────────────────────────────────

@mcp.tool()
async def get_users() -> Any:
    """Liste les utilisateurs GLPI."""
    return await glpi.get("/User")


@mcp.tool()
async def get_groups() -> Any:
    """Liste les groupes GLPI."""
    return await glpi.get("/Group")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


# === Base de connaissances (KnowbaseItem) =====================================
# Le nom de classe GLPI est KnowbaseItem (sans 'ledge'), confirmé par
# front/knowbaseitem.form.php

@mcp.tool()
async def list_kb_articles(
    range_start: int = 0,
    range_limit: int = 50,
) -> Any:
    """List GLPI knowledge base articles with pagination.

    Each KnowbaseItem returned by the API embeds the full HTML answer.
    On large KBs this makes the JSON response heavy: in production we
    observed that range_start > 60 combined with range_limit > 10 is
    enough to exceed PHP-FPM memory_limit on the GLPI side and the
    request fails. To stay below that ceiling, range_limit is
    auto-clamped to 10 when range_start > 60. When clamping kicks in
    the response is wrapped in a dict carrying _clamped_range_limit
    and _warning so callers can detect the change. Behaviour is
    unchanged for range_start <= 60.
    """
    clamped = range_start > 60 and range_limit > 10
    effective_limit = 10 if clamped else range_limit

    params: Dict[str, Any] = {
        "range": f"{range_start}-{range_start + effective_limit - 1}",
    }
    result = await glpi.get("/KnowbaseItem", params=params)

    if not clamped:
        return result

    if isinstance(result, list):
        return {
            "_clamped_range_limit": 10,
            "_warning": LABEL_KB_CLAMP_WARNING,
            "items": result,
        }
    if isinstance(result, dict):
        result["_clamped_range_limit"] = 10
        result["_warning"] = LABEL_KB_CLAMP_WARNING
    return result


@mcp.tool()
async def get_kb_article(article_id: int) -> Any:
    """Retourne le detail complet d'un article de la base de connaissances."""
    return await glpi.get(f"/KnowbaseItem/{article_id}")


@mcp.tool()
async def search_kb_articles(
    keywords: str,
    range_start: int = 0,
    range_limit: int = 50,
    search_content: bool = False,
) -> Any:
    """Search knowledge base articles by keyword.

    By default the search runs only against the title column, which is fast
    on any GLPI instance. Set search_content=True to also match against the
    full HTML body. On a GLPI instance that has no MySQL FULLTEXT index on
    knowbaseitems.answer, that branch produces a LIKE '%keyword%' scan on
    the answer column which routinely exceeds the 30 second client timeout
    on KBs with sizeable HTML payloads.

    Field IDs are discovered at runtime via listSearchOptions/KnowbaseItem
    and looked up by column name ("name", "answer") so the tool works on
    both GLPI 10 and GLPI 11 (where numeric IDs may differ). When discovery
    fails the legacy GLPI 10 IDs (6 for title, 7 for body) are used as a
    fallback.

    Parameters:
    - keywords: text to search for
    - range_start, range_limit: pagination
    - search_content: also match against the article body (default False).
      Only enable when the GLPI database has a FULLTEXT index on
      knowbaseitems.answer, otherwise the request will be slow.
    """
    name_field = await _resolve_search_field_id("KnowbaseItem", "name", "6")
    answer_field = await _resolve_search_field_id("KnowbaseItem", "answer", "7")

    params: Dict[str, Any] = {
        "range": f"{range_start}-{range_start + range_limit - 1}",
        "criteria[0][field]": name_field,
        "criteria[0][searchtype]": "contains",
        "criteria[0][value]": keywords,
    }
    if search_content:
        params["criteria[0][link]"] = "AND"
        params["criteria[1][link]"] = "OR"
        params["criteria[1][field]"] = answer_field
        params["criteria[1][searchtype]"] = "contains"
        params["criteria[1][value]"] = keywords
    return await glpi.get("/search/KnowbaseItem", params=params)


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
    return await glpi.post("/KnowbaseItem", {"input": input_data})


@mcp.tool()
async def update_kb_article(article_id: int, update_fields: Dict[str, Any]) -> Any:
    """
    Met a jour un article de la base de connaissances.
    Exemples de champs : name, answer, is_faq, knowbaseitemcategories_id
    """
    return await glpi.put(f"/KnowbaseItem/{article_id}", {"input": update_fields})


@mcp.tool()
async def list_kb_categories() -> Any:
    """Liste toutes les categories de la base de connaissances."""
    return await glpi.get("/KnowbaseItemCategory")


@mcp.tool()
async def get_kb_article_visibility(article_id: int) -> Dict[str, Any]:
    """
    Retourne les regles de visibilite d'un article KB :
    profils, groupes, utilisateurs et entites ayant acces.
    """
    profiles = await glpi.get(f"/KnowbaseItem/{article_id}/KnowbaseItem_Profile")
    groups   = await glpi.get(f"/KnowbaseItem/{article_id}/KnowbaseItem_Group")
    users    = await glpi.get(f"/KnowbaseItem/{article_id}/KnowbaseItem_User")
    entities = await glpi.get(f"/KnowbaseItem/{article_id}/Entity_KnowbaseItem")
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
    return await glpi.post("/KnowbaseItem_Profile", {"input": {
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
    return await glpi.post("/KnowbaseItem_Group", {"input": {
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
    return await glpi.put(f"/KnowbaseItem_Profile/{visibility_id}", {"input": update_fields})


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
    return await glpi.put(f"/KnowbaseItem_Group/{visibility_id}", {"input": update_fields})
if __name__ == "__main__":
    mcp.run(transport="stdio")


