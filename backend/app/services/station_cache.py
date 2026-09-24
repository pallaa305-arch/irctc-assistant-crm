"""
Master Offline Station & Train Cache Service.
Inspired by high-speed desktop Tatkal architectures (PROMAX local .enc datasets),
providing sub-millisecond offline station resolution, fuzzy search, and train lookup.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATIONS_FILE = DATA_DIR / "stations_master.json"
TRAINS_FILE = DATA_DIR / "trains_master.json"


class StationMasterCache:
    _instance: Optional['StationMasterCache'] = None

    def __init__(self):
        self.stations_by_code: Dict[str, Dict[str, Any]] = {}
        self.station_alias_map: Dict[str, str] = {}
        self.trains_by_number: Dict[str, Dict[str, Any]] = {}
        self._load_datasets()

    @classmethod
    def get_instance(cls) -> 'StationMasterCache':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    PRIMARY_HUBS = {
        "DELHI": "NDLS",
        "NEW DELHI": "NDLS",
        "MUMBAI": "MMCT",
        "BOMBAY": "MMCT",
        "LUCKNOW": "LKO",
        "VARANASI": "BSB",
        "BANARAS": "BSB",
        "PATNA": "PNBE",
        "KOLKATA": "HWH",
        "CALCUTTA": "HWH",
        "CHENNAI": "MAS",
        "MADRAS": "MAS",
        "BENGALURU": "SBC",
        "BANGALORE": "SBC",
        "HYDERABAD": "HYB",
        "AHMEDABAD": "ADI",
        "AGRA": "AGC",
        "BHOPAL": "BPL",
        "PRAYAGRAJ": "PRYJ",
        "ALLAHABAD": "PRYJ",
        "AYODHYA": "AY",
    }

    def _load_datasets(self):
        # Load stations
        if STATIONS_FILE.exists():
            try:
                with open(STATIONS_FILE, "r", encoding="utf-8") as f:
                    stations_list = json.load(f)
                    for st in stations_list:
                        code = st["code"].upper().strip()
                        self.stations_by_code[code] = st
                        
                        # Map direct code
                        self.station_alias_map[code] = code
                        # Map name
                        self.station_alias_map[st["name"].upper().strip()] = code
                        # Map city
                        if "city" in st and st["city"]:
                            city_u = st["city"].upper().strip()
                            if city_u not in self.station_alias_map or code in self.PRIMARY_HUBS.values():
                                self.station_alias_map[city_u] = code
                        # Map aliases
                        for alias in st.get("aliases", []):
                            alias_u = alias.upper().strip()
                            if alias_u not in self.station_alias_map or code in self.PRIMARY_HUBS.values():
                                self.station_alias_map[alias_u] = code

                    # Explicitly enforce primary hubs
                    for city_alias, hub_code in self.PRIMARY_HUBS.items():
                        self.station_alias_map[city_alias] = hub_code
            except Exception as e:
                print(f"[StationCache] Error loading stations_master.json: {e}")

        # Load trains
        if TRAINS_FILE.exists():
            try:
                with open(TRAINS_FILE, "r", encoding="utf-8") as f:
                    trains_list = json.load(f)
                    for tr in trains_list:
                        tnum = tr["train_number"].strip()
                        self.trains_by_number[tnum] = tr
            except Exception as e:
                print(f"[StationCache] Error loading trains_master.json: {e}")

    def resolve_station_code(self, query: str) -> Optional[str]:
        """
        Fast resolver: Returns 2 to 5 character uppercase station code for any query.
        Handles: Exact code, city alias, Hindi/English station name, or clean regex.
        """
        if not query:
            return None
        
        q = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip().upper()
        if not q:
            return None

        # 1. Direct code or alias hit
        if q in self.station_alias_map:
            return self.station_alias_map[q]

        # 2. Check if query is already a known station code
        if q in self.stations_by_code:
            return q

        # 3. Substring matching in aliases
        for alias, code in self.station_alias_map.items():
            if q == alias or q in alias.split():
                return code

        for alias, code in self.station_alias_map.items():
            if len(q) >= 3 and (q in alias or alias in q):
                return code

        # If nothing matched, return the uppercase query if it looks like a valid code
        if 2 <= len(q) <= 5 and q.isalpha():
            return q

        return None

    def get_station_name(self, code: str) -> str:
        """Returns the human-friendly name of a station code."""
        code_u = code.upper().strip()
        if code_u in self.stations_by_code:
            st = self.stations_by_code[code_u]
            return f"{st['name']} ({code_u})"
        return code_u

    def get_station_details(self, code: str) -> Optional[Dict[str, Any]]:
        return self.stations_by_code.get(code.upper().strip())

    def search_stations(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Fast fuzzy autocomplete search for stations.
        Matches: Station Code, Station Name, State Name, City, Aliases, Hindi Names.
        """
        if not query:
            return []
        q = query.upper().strip()
        matches = []
        seen = set()

        for code, st in self.stations_by_code.items():
            score = 0
            code_u = code.upper()
            name_u = st.get("name", "").upper()
            city_u = st.get("city", "").upper()
            state_u = st.get("state", "").upper()
            aliases = [a.upper() for a in st.get("aliases", [])]

            # 1. Exact Station Code Match
            if code_u == q:
                score = 120
            # 2. Station Code Starts With Query
            elif code_u.startswith(q):
                score = 100
            # 3. Exact City or Name Match
            elif name_u == q or city_u == q:
                score = 90
            # 4. Name Starts With Query
            elif any(word.startswith(q) for word in name_u.split()):
                score = 80
            # 5. City Starts With Query
            elif any(word.startswith(q) for word in city_u.split()):
                score = 75
            # 6. State Match (Allows searching by state name e.g. "Rajasthan", "Maharashtra", "Gujarat", "Delhi")
            elif state_u == q or q in state_u or state_u in q:
                score = 70
            # 7. Query is contained in Station Name
            elif q in name_u:
                score = 65
            # 8. Query is contained in City
            elif q in city_u:
                score = 60
            # 9. Alias Match
            elif any(q == a or q in a or a in q for a in aliases):
                score = 55
            # 10. Hindi Name Match
            elif st.get("hindi") and query in st.get("hindi"):
                score = 50

            if score > 0 and code not in seen:
                matches.append((score, st))
                seen.add(code)

        # Sort primarily by match score, secondarily alphabetically by station name
        matches.sort(key=lambda x: (-x[0], x[1].get("name", "")))
        return [item[1] for item in matches[:limit]]

    def get_train_details(self, train_number: str) -> Optional[Dict[str, Any]]:
        return self.trains_by_number.get(train_number.strip())

    def get_all_trains(self) -> Dict[str, Dict[str, Any]]:
        return self.trains_by_number


station_cache = StationMasterCache.get_instance()
