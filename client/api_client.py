from typing import Optional, Any
from datetime import date

import httpx

from config import API_BASE


class APIError(Exception):
    """Raised when the server returns an error response."""

    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class APIClient:
    def __init__(self, base_url: str = API_BASE, timeout: float = 30.0):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self):
        self.client.close()

    # -- internal helpers ------------------------------------------------

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            resp = self.client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                body = exc.response.json()
                detail = body.get("detail", str(body))
            except Exception:
                detail = exc.response.text
            raise APIError(exc.response.status_code, detail) from exc
        except httpx.RequestError as exc:
            raise APIError(0, f"Connection error: {exc}") from exc

    def _get(self, url: str, **kwargs) -> Any:
        return self._request("GET", url, **kwargs).json()

    def _post(self, url: str, **kwargs) -> Any:
        return self._request("POST", url, **kwargs).json()

    def _put(self, url: str, **kwargs) -> Any:
        return self._request("PUT", url, **kwargs).json()

    def _delete(self, url: str, **kwargs) -> None:
        self._request("DELETE", url, **kwargs)

    def _get_bytes(self, url: str, **kwargs) -> bytes:
        return self._request("GET", url, **kwargs).content

    # ====================================================================
    #  AWARDS  /awards
    # ====================================================================

    def get_awards(self, award_type: Optional[str] = None) -> list:
        params: dict = {}
        if award_type:
            params["award_type"] = award_type
        return self._get("/awards/", params=params)

    def create_award(self, data: dict) -> dict:
        return self._post("/awards/", json=data)

    def get_award(self, award_id: int) -> dict:
        return self._get(f"/awards/{award_id}")

    def update_award(self, award_id: int, data: dict) -> dict:
        return self._put(f"/awards/{award_id}", json=data)

    def delete_award(self, award_id: int) -> None:
        self._delete(f"/awards/{award_id}")

    # -- Characteristics -------------------------------------------------

    def get_characteristics(self, award_id: int) -> list:
        return self._get(f"/awards/{award_id}/characteristics")

    def create_characteristic(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/characteristics", json=data)

    # -- Establishment ---------------------------------------------------

    def get_establishment(self, award_id: int) -> dict:
        return self._get(f"/awards/{award_id}/establishment")

    def create_establishment(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/establishment", json=data)

    def update_establishment(self, award_id: int, data: dict) -> dict:
        return self._put(f"/awards/{award_id}/establishment", json=data)

    # -- Development -----------------------------------------------------

    def get_development(self, award_id: int) -> dict:
        return self._get(f"/awards/{award_id}/development")

    def create_development(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/development", json=data)

    def update_development(self, award_id: int, data: dict) -> dict:
        return self._put(f"/awards/{award_id}/development", json=data)

    # -- Approvals -------------------------------------------------------

    def get_approvals(self, award_id: int) -> list:
        return self._get(f"/awards/{award_id}/approvals")

    def create_approval(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/approvals", json=data)

    # -- Productions -----------------------------------------------------

    def get_productions(self, award_id: int) -> list:
        return self._get(f"/awards/{award_id}/productions")

    def create_production(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/productions", json=data)

    # -- Inventory -------------------------------------------------------

    def get_inventory(self, award_id: int) -> list:
        return self._get(f"/awards/{award_id}/inventory")

    def create_inventory_item(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/inventory", json=data)

    def update_inventory_item(self, item_id: int, data: dict) -> dict:
        return self._put(f"/awards/inventory/{item_id}", json=data)

    # -- Award-level reports (on the awards router) ----------------------

    def get_award_lifecycle_report(self) -> list:
        return self._get("/awards/lifecycle")

    def get_warehouse_report(self) -> list:
        return self._get("/awards/warehouse")

    # ====================================================================
    #  LAUREATES  /laureates
    # ====================================================================

    def get_laureates(self, category: Optional[str] = None) -> list:
        params: dict = {}
        if category:
            params["category"] = category
        return self._get("/laureates/", params=params)

    def create_laureate(self, data: dict) -> dict:
        return self._post("/laureates/", json=data)

    def get_laureate(self, laureate_id: int) -> dict:
        return self._get(f"/laureates/{laureate_id}")

    def update_laureate(self, laureate_id: int, data: dict) -> dict:
        return self._put(f"/laureates/{laureate_id}", json=data)

    def delete_laureate(self, laureate_id: int) -> None:
        self._delete(f"/laureates/{laureate_id}")

    # -- Laureate ↔ Award links -----------------------------------------

    def get_laureate_awards(self, laureate_id: int) -> list:
        return self._get(f"/laureates/{laureate_id}/awards")

    def link_award_to_laureate(self, laureate_id: int, data: dict) -> dict:
        return self._post(f"/laureates/{laureate_id}/awards", json=data)

    # -- Lifecycle -------------------------------------------------------

    def get_laureate_lifecycle(self, laureate_award_id: int) -> dict:
        return self._get(f"/laureates/{laureate_award_id}/lifecycle")

    def create_laureate_lifecycle(self, laureate_award_id: int, data: dict) -> dict:
        return self._post(f"/laureates/{laureate_award_id}/lifecycle", json=data)

    def update_laureate_lifecycle(self, laureate_award_id: int, data: dict) -> dict:
        return self._put(f"/laureates/{laureate_award_id}/lifecycle", json=data)

    # -- Laureate reports (on the laureates router) ----------------------

    def get_awards_laureates_report_v1(self) -> list:
        return self._get("/laureates/reports/awards-laureates")

    def get_incomplete_lifecycle_report_v1(self) -> list:
        return self._get("/laureates/reports/incomplete-lifecycle")

    def get_statistics_report_v1(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> list:
        params: dict = {}
        if from_date:
            params["from_date"] = from_date.isoformat()
        if to_date:
            params["to_date"] = to_date.isoformat()
        return self._get("/laureates/reports/statistics", params=params)

    # ====================================================================
    #  COMMITTEE  /committee
    # ====================================================================

    def get_committee_members(self, is_active: Optional[bool] = None) -> list:
        params: dict = {}
        if is_active is not None:
            params["is_active"] = str(is_active).lower()
        return self._get("/committee/", params=params)

    def create_committee_member(self, data: dict) -> dict:
        return self._post("/committee/", json=data)

    def get_committee_member(self, member_id: int) -> dict:
        return self._get(f"/committee/{member_id}")

    def update_committee_member(self, member_id: int, data: dict) -> dict:
        return self._put(f"/committee/{member_id}", json=data)

    def delete_committee_member(self, member_id: int) -> None:
        self._delete(f"/committee/{member_id}")

    # -- Signing rights --------------------------------------------------

    def get_signing_rights(self, member_id: int) -> list:
        return self._get(f"/committee/{member_id}/signing-rights")

    def assign_signing_right(self, member_id: int, data: dict) -> dict:
        return self._post(f"/committee/{member_id}/signing-rights", json=data)

    def remove_signing_right(self, right_id: int) -> None:
        self._delete(f"/committee/signing-rights/{right_id}")

    # ====================================================================
    #  VOTING  /voting
    # ====================================================================

    # -- Bulletins -------------------------------------------------------

    def get_bulletins(self) -> list:
        return self._get("/voting/bulletins")

    def create_bulletin(self, data: dict) -> dict:
        return self._post("/voting/bulletins", json=data)

    def get_bulletin(self, bulletin_id: int) -> dict:
        return self._get(f"/voting/bulletins/{bulletin_id}")

    def update_bulletin(self, bulletin_id: int, data: dict) -> dict:
        return self._put(f"/voting/bulletins/{bulletin_id}", json=data)

    def delete_bulletin(self, bulletin_id: int) -> None:
        self._delete(f"/voting/bulletins/{bulletin_id}")

    # -- Sections --------------------------------------------------------

    def add_bulletin_section(self, bulletin_id: int, data: dict) -> dict:
        return self._post(f"/voting/bulletins/{bulletin_id}/sections", json=data)

    # -- Questions -------------------------------------------------------

    def add_section_question(self, section_id: int, data: dict) -> dict:
        return self._post(f"/voting/sections/{section_id}/questions", json=data)

    # -- Distribution ----------------------------------------------------

    def distribute_bulletin(self, bulletin_id: int, member_ids: list[int]) -> list:
        return self._post(
            f"/voting/bulletins/{bulletin_id}/distribute",
            json={"member_ids": member_ids},
        )

    def update_distribution(self, distribution_id: int, data: dict) -> dict:
        return self._put(f"/voting/distributions/{distribution_id}", json=data)

    # -- Monitoring ------------------------------------------------------

    def get_bulletin_monitoring(self, bulletin_id: int) -> list:
        return self._get(f"/voting/bulletins/{bulletin_id}/monitoring")

    # -- Votes -----------------------------------------------------------

    def record_vote(self, question_id: int, data: dict) -> dict:
        return self._post(f"/voting/questions/{question_id}/votes", json=data)

    # -- Results (vote counting) -----------------------------------------

    def get_vote_results(self, bulletin_id: int) -> list:
        return self._get(f"/voting/bulletins/{bulletin_id}/results")

    # -- Protocols -------------------------------------------------------

    def get_protocols(self) -> list:
        return self._get("/voting/protocols")

    def create_protocol(self, bulletin_id: int, data: dict) -> dict:
        return self._post(f"/voting/bulletins/{bulletin_id}/protocol", json=data)

    def update_protocol(self, protocol_id: int, data: dict) -> dict:
        return self._put(f"/voting/protocols/{protocol_id}", json=data)

    # -- Protocol Extracts -----------------------------------------------

    def create_protocol_extract(self, protocol_id: int, data: dict) -> dict:
        return self._post(f"/voting/protocols/{protocol_id}/extracts", json=data)

    # -- PPZ Submissions -------------------------------------------------

    def create_ppz_submission(self, data: dict) -> dict:
        return self._post("/voting/ppz-submissions", json=data)

    # ====================================================================
    #  REPORTS  /reports
    # ====================================================================

    def report_award_lifecycle(self) -> list:
        return self._get("/reports/award-lifecycle")

    def report_warehouse_summary(self) -> list:
        return self._get("/reports/warehouse-summary")

    def report_awards_laureates(self) -> list:
        return self._get("/reports/awards-laureates")

    def report_incomplete_lifecycle(self) -> list:
        return self._get("/reports/incomplete-lifecycle")

    def report_statistics(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict:
        params: dict = {}
        if from_date:
            params["from_date"] = from_date.isoformat()
        if to_date:
            params["to_date"] = to_date.isoformat()
        return self._get("/reports/statistics", params=params)

    # ====================================================================
    #  BACKUP  /backup
    # ====================================================================

    def export_database(self) -> bytes:
        return self._get_bytes("/backup/export")

    def import_database(self, file_path: str) -> dict:
        with open(file_path, "rb") as f:
            resp = self._request(
                "POST",
                "/backup/import",
                files={"file": ("backup.dump", f, "application/octet-stream")},
            )
        return resp.json()

    def export_csv(self, table_name: str) -> bytes:
        return self._get_bytes(f"/backup/export/csv/{table_name}")

    # ====================================================================
    #  HEALTH CHECK
    # ====================================================================

    def health_check(self) -> dict:
        return self._get("/")
