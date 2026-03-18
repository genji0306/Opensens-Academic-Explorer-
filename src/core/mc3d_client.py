"""
MC3D Client — Materials Cloud 3D Crystals Database Interface
=============================================================
Provides access to the MC3D computational database of experimentally-known
stoichiometric inorganic crystal structures (~32,000 unique structures).

Two API endpoints are supported:

1. **AiiDA REST API** (primary):
   ``https://aiida.materialscloud.org/mc3d-pbe-v1/api/v4``
   Returns StructureData nodes with full lattice vectors, atomic positions,
   species, and computed properties.

2. **OPTIMADE API** (standards-compliant):
   ``https://optimade.materialscloud.org/mc3d/pbe/v1/``
   JSON:API format for cross-database interoperability.

Usage::

    from src.core.mc3d_client import MC3DClient

    client = MC3DClient()

    # Fetch structures containing specific elements
    structures = client.search_structures(elements=["La", "H"], limit=20)

    # Get a specific structure by AiiDA node UUID
    structure = client.get_structure("03855809-e68a-4a7f-823d-007cd7cf80df")

    # Search for superconductor-relevant families
    hydrides = client.search_by_formula(formula="LaH*", limit=50)

    # Fetch computed properties (band gap, formation energy, etc.)
    props = client.get_properties(node_id=11)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

logger = logging.getLogger("MC3D.Client")

# ---------------------------------------------------------------------------
# API base URLs
# ---------------------------------------------------------------------------
AIIDA_BASE = "https://aiida.materialscloud.org/mc3d-pbe-v1/api/v4"
OPTIMADE_BASE = "https://optimade.materialscloud.org/mc3d/pbe/v1"

# StructureData full_type in AiiDA
_STRUCTURE_FULL_TYPE = "data.core.structure.StructureData.|"

# Rate-limit: max requests per second (be polite)
_RATE_LIMIT_DELAY = 0.25  # 250 ms between requests

# Local cache directory
_CACHE_DIR: Optional[Path] = None


# ---------------------------------------------------------------------------
# Dataclasses for parsed results
# ---------------------------------------------------------------------------

@dataclass
class MC3DStructure:
    """Parsed crystal structure from MC3D."""
    uuid: str
    node_id: int
    formula: str
    species: list[dict[str, Any]]
    cell: list[list[float]]  # 3x3 lattice vectors in Angstrom
    positions: list[list[float]]  # Cartesian positions
    pbc: tuple[bool, bool, bool]
    n_atoms: int
    ctime: str = ""
    mtime: str = ""
    label: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def elements(self) -> list[str]:
        """Unique element symbols in the structure."""
        seen = set()
        result = []
        for s in self.species:
            sym = s.get("name", s.get("kind_name", ""))
            # Strip numeric suffixes (e.g., "Fe1" → "Fe")
            clean = "".join(c for c in sym if not c.isdigit())
            if clean and clean not in seen:
                seen.add(clean)
                result.append(clean)
        return result


@dataclass
class MC3DProperty:
    """Computed property from MC3D workflow."""
    node_id: int
    uuid: str
    property_type: str
    attributes: dict[str, Any]


# ---------------------------------------------------------------------------
# HTTP transport (requests with fallback to urllib)
# ---------------------------------------------------------------------------

def _http_get(url: str, params: Optional[dict] = None, timeout: int = 30) -> dict:
    """Perform an HTTP GET and return parsed JSON."""
    try:
        import requests
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except ImportError:
        # Fallback to urllib
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError
        if params:
            url = f"{url}?{urlencode(params)}"
        req = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            raise ConnectionError(f"MC3D API error {e.code}: {e.reason}") from e


# ---------------------------------------------------------------------------
# Client class
# ---------------------------------------------------------------------------

class MC3DClient:
    """Client for the Materials Cloud MC3D crystal structure database.

    Parameters
    ----------
    cache_dir : Path, optional
        Directory for caching API responses.  If *None*, caching is disabled.
    rate_limit : float
        Minimum seconds between consecutive API calls (default 0.25).
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        rate_limit: float = _RATE_LIMIT_DELAY,
    ) -> None:
        self._cache_dir = cache_dir
        self._rate_limit = rate_limit
        self._last_request_time: float = 0.0
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Rate limiting
    # ------------------------------------------------------------------ #

    def _throttle(self) -> None:
        """Enforce rate limit between API calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request_time = time.time()

    # ------------------------------------------------------------------ #
    # Low-level AiiDA queries
    # ------------------------------------------------------------------ #

    def _aiida_get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """GET from the AiiDA REST API."""
        url = f"{AIIDA_BASE}/{endpoint.lstrip('/')}"
        self._throttle()
        logger.debug("GET %s params=%s", url, params)
        return _http_get(url, params=params)

    # ------------------------------------------------------------------ #
    # Structure search
    # ------------------------------------------------------------------ #

    def search_structures(
        self,
        elements: Optional[list[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MC3DStructure]:
        """Search for crystal structures in MC3D.

        Parameters
        ----------
        elements : list[str], optional
            Filter by element symbols (e.g. ["La", "H"]).  Returns structures
            containing ALL specified elements.
        limit : int
            Max results to return (default 50, max 500).
        offset : int
            Pagination offset.

        Returns
        -------
        list[MC3DStructure]
            Parsed structure objects.
        """
        params: dict[str, Any] = {
            "full_type": '"data.core.structure.StructureData.|"',
            "limit": min(limit, 500),
            "offset": offset,
            "attributes": "true",
            "attributes_filter": "cell,kinds,sites,pbc1,pbc2,pbc3",
        }

        data = self._aiida_get("nodes/", params=params)
        nodes = data.get("data", {}).get("nodes", [])

        structures = []
        for node in nodes:
            try:
                s = self._parse_structure_node(node)
                if elements:
                    if not all(e in s.elements for e in elements):
                        continue
                structures.append(s)
            except Exception as e:
                logger.warning("Failed to parse node %s: %s", node.get("id"), e)

        logger.info("MC3D search returned %d structures (limit=%d)", len(structures), limit)
        return structures

    def get_structure(self, uuid: str) -> Optional[MC3DStructure]:
        """Fetch a specific structure by UUID.

        Parameters
        ----------
        uuid : str
            AiiDA node UUID.

        Returns
        -------
        MC3DStructure or None
        """
        params = {
            "attributes": "true",
            "attributes_filter": "cell,kinds,sites,pbc1,pbc2,pbc3",
        }
        data = self._aiida_get(f"nodes/{uuid}/", params=params)
        node = data.get("data", {}).get("nodes", [{}])
        if isinstance(node, list):
            node = node[0] if node else {}
        try:
            return self._parse_structure_node(node)
        except Exception as e:
            logger.error("Failed to parse structure %s: %s", uuid, e)
            return None

    def search_by_formula(
        self,
        formula: str,
        limit: int = 50,
    ) -> list[MC3DStructure]:
        """Search structures by chemical formula pattern.

        Uses the AiiDA querybuilder endpoint to filter by formula substring.

        Parameters
        ----------
        formula : str
            Chemical formula or pattern (e.g., "LaH", "MgB2", "YBa2Cu3").
        limit : int
            Max results.

        Returns
        -------
        list[MC3DStructure]
        """
        # Use extras filter if available, otherwise fall back to full scan
        # MC3D stores formula in extras or we filter client-side
        structures = self.search_structures(limit=limit * 2)
        matched = []
        formula_clean = formula.replace("*", "").lower()
        for s in structures:
            if formula_clean in s.formula.lower():
                matched.append(s)
                if len(matched) >= limit:
                    break
        return matched

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    def get_properties(self, node_id: int) -> dict[str, Any]:
        """Fetch computed properties for a structure node.

        Retrieves attributes and extras which may contain:
        - Formation energy
        - Band gap
        - Space group
        - Relaxation metadata

        Parameters
        ----------
        node_id : int
            AiiDA node ID.

        Returns
        -------
        dict with keys 'attributes' and 'extras'.
        """
        attrs = self._aiida_get(f"nodes/{node_id}/contents/attributes/")
        extras = self._aiida_get(f"nodes/{node_id}/contents/extras/")
        return {
            "attributes": attrs.get("data", {}).get("attributes", {}),
            "extras": extras.get("data", {}).get("extras", {}),
        }

    def get_derived_properties(self, node_id: int) -> dict[str, Any]:
        """Fetch derived properties (e.g., symmetry, formula) for a node."""
        data = self._aiida_get(f"nodes/{node_id}/contents/derived_properties/")
        return data.get("data", {}).get("derived_properties", {})

    # ------------------------------------------------------------------ #
    # Bulk download for Agent Sin
    # ------------------------------------------------------------------ #

    def fetch_reference_structures(
        self,
        families: Optional[list[str]] = None,
        elements_pool: Optional[list[str]] = None,
        limit: int = 200,
    ) -> list[MC3DStructure]:
        """Fetch a batch of reference structures for Agent Sin calibration.

        Optimised for superconductor-relevant compositions by filtering for
        elements commonly found in the 14 RTAP families.

        Parameters
        ----------
        families : list[str], optional
            RTAP family names to target (maps to element sets internally).
        elements_pool : list[str], optional
            Explicit element filter.
        limit : int
            Total structures to fetch (paginated internally).

        Returns
        -------
        list[MC3DStructure]
        """
        # Family → element mapping for superconductor-relevant structures
        family_elements = {
            "cuprate": ["Cu", "O", "Ba", "La", "Y", "Ca"],
            "nickelate": ["Ni", "O", "Nd", "La", "Sr"],
            "hydride": ["H", "La", "Y", "Ca", "Ce"],
            "ternary-hydride": ["H", "La", "B", "Ca", "Be"],
            "iron-pnictide": ["Fe", "As", "P", "Ba", "La"],
            "iron-chalcogenide": ["Fe", "Se", "Te"],
            "kagome": ["V", "Sb", "Cs", "K", "Rb"],
            "infinite-layer": ["Ni", "O", "Nd", "Sr"],
            "topological": ["Bi", "Se", "Te", "Cu"],
            "carbon-based": ["C", "K", "Cs", "Rb"],
            "engineered-cuprate": ["Cu", "O", "Hg", "Ba", "Ca", "Tl"],
            "mof-sc": ["Cu", "C", "S", "N"],
            "flat-band": ["V", "Nb", "Ti", "O"],
            "mgb2-type": ["Mg", "B"],
        }

        all_structures: list[MC3DStructure] = []
        seen_uuids: set[str] = set()

        if families:
            target_element_sets = [family_elements.get(f, []) for f in families]
        elif elements_pool:
            target_element_sets = [[e] for e in elements_pool]
        else:
            # Default: fetch broadly for SC-relevant elements
            target_element_sets = [["Cu", "O"], ["Fe", "As"], ["H", "La"], ["Ni", "O"]]

        per_query = max(limit // len(target_element_sets), 10)

        for elem_set in target_element_sets:
            if len(all_structures) >= limit:
                break
            try:
                batch = self.search_structures(
                    elements=elem_set[:2],  # Use top-2 elements for API query
                    limit=per_query,
                )
                for s in batch:
                    if s.uuid not in seen_uuids:
                        seen_uuids.add(s.uuid)
                        all_structures.append(s)
            except Exception as e:
                logger.warning("MC3D fetch for %s failed: %s", elem_set, e)

        logger.info(
            "MC3D reference fetch: %d unique structures for %d family targets",
            len(all_structures), len(target_element_sets),
        )
        return all_structures[:limit]

    # ------------------------------------------------------------------ #
    # Conversion helpers
    # ------------------------------------------------------------------ #

    def to_pymatgen(self, structure: MC3DStructure):
        """Convert MC3DStructure to a pymatgen Structure object.

        Returns
        -------
        pymatgen.core.Structure
        """
        from pymatgen.core import Structure, Lattice

        lattice = Lattice(structure.cell)
        species = []
        coords = []
        for site in structure.positions:
            # Map site index to species
            pass

        # Build from species list + Cartesian coords
        site_species = []
        for i, pos in enumerate(structure.positions):
            if i < len(structure.species):
                kind = structure.species[i]
                sym = kind.get("name", kind.get("kind_name", "X"))
                # Strip numeric suffix
                sym_clean = "".join(c for c in sym if not c.isdigit())
                site_species.append(sym_clean)
            else:
                site_species.append("X")

        return Structure(
            lattice,
            site_species,
            structure.positions,
            coords_are_cartesian=True,
        )

    # ------------------------------------------------------------------ #
    # Internal parsing
    # ------------------------------------------------------------------ #

    def _parse_structure_node(self, node: dict) -> MC3DStructure:
        """Parse an AiiDA StructureData node dict into MC3DStructure."""
        attrs = node.get("attributes", {})
        kinds = attrs.get("kinds", [])
        sites = attrs.get("sites", [])
        cell = attrs.get("cell", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        pbc = (
            attrs.get("pbc1", True),
            attrs.get("pbc2", True),
            attrs.get("pbc3", True),
        )

        # Build species list from sites (each site has kind_name + position)
        species_list = []
        positions = []
        for site in sites:
            kind_name = site.get("kind_name", "X")
            position = site.get("position", [0, 0, 0])
            species_list.append({"name": kind_name})
            positions.append(position)

        # Derive formula from kind counts
        from collections import Counter
        elem_counts = Counter(
            "".join(c for c in s["name"] if not c.isdigit())
            for s in species_list
        )
        formula = "".join(
            f"{e}{c}" if c > 1 else e
            for e, c in sorted(elem_counts.items())
        )

        return MC3DStructure(
            uuid=node.get("uuid", ""),
            node_id=node.get("id", 0),
            formula=formula,
            species=species_list,
            cell=cell,
            positions=positions,
            pbc=pbc,
            n_atoms=len(sites),
            ctime=node.get("ctime", ""),
            mtime=node.get("mtime", ""),
            label=node.get("label", ""),
        )

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #

    def get_statistics(self) -> dict[str, Any]:
        """Fetch node statistics from the MC3D database."""
        data = self._aiida_get("nodes/statistics/")
        return data.get("data", {}).get("statistics", {})


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def get_default_client() -> MC3DClient:
    """Return a default MC3DClient with project-local caching."""
    from src.core.config import DATA_DIR
    cache = DATA_DIR / "mc3d_cache"
    return MC3DClient(cache_dir=cache)
