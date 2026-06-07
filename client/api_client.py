from typing import Optional, Any
from datetime import date
import os

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

    def get_award_image_bytes(self, award_id: int, side: str = "front") -> Optional[bytes]:
        """Байты изображения (лицо или оборот) или None, если 404."""
        if side not in ("front", "back"):
            side = "front"
        try:
            return self._get_bytes(f"/awards/{award_id}/image", params={"side": side})
        except APIError as e:
            if e.status_code == 404:
                return None
            raise

    def upload_award_images(
        self,
        award_id: int,
        front_path: Optional[str] = None,
        back_path: Optional[str] = None,
    ) -> dict:
        """Multipart: загрузка файлов лица и/или оборота."""
        import os

        opened: list = []
        try:
            parts: list = []
            if front_path:
                f = open(front_path, "rb")
                opened.append(f)
                parts.append(
                    (
                        "image_front",
                        (os.path.basename(front_path), f, "application/octet-stream"),
                    )
                )
            if back_path:
                f = open(back_path, "rb")
                opened.append(f)
                parts.append(
                    (
                        "image_back",
                        (os.path.basename(back_path), f, "application/octet-stream"),
                    )
                )
            if not parts:
                return {}
            resp = self._request("POST", f"/awards/{award_id}/images", files=parts)
            return resp.json()
        finally:
            for f in opened:
                f.close()

    def delete_award_image(self, award_id: int, side: str) -> None:
        if side not in ("front", "back"):
            raise ValueError("side must be front or back")
        self._delete(f"/awards/{award_id}/images/{side}")

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

    def upload_establishment_protocol(self, award_id: int, file_path: str) -> None:
        with open(file_path, "rb") as f:
            self._request(
                "POST",
                f"/awards/{award_id}/establishment/protocol-file",
                files={"file": (os.path.basename(file_path), f, "application/octet-stream")},
            )

    def download_establishment_protocol(self, award_id: int) -> bytes:
        return self._get_bytes(f"/awards/{award_id}/establishment/protocol-file")

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

    def update_approval(self, approval_id: int, data: dict) -> dict:
        return self._put(f"/awards/approvals/{approval_id}", json=data)

    def delete_approval(self, approval_id: int) -> None:
        self._delete(f"/awards/approvals/{approval_id}")

    # -- Productions -----------------------------------------------------

    def get_productions(self, award_id: int) -> list:
        return self._get(f"/awards/{award_id}/productions")

    def create_production(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/productions", json=data)

    def update_production(self, production_id: int, data: dict) -> dict:
        return self._put(f"/awards/productions/{production_id}", json=data)

    def delete_production(self, production_id: int) -> None:
        self._delete(f"/awards/productions/{production_id}")

    def get_production_stages(self, award_id: int) -> dict:
        return self._get(f"/awards/{award_id}/production-stages")

    def update_production_stages(self, award_id: int, data: dict) -> dict:
        return self._put(f"/awards/{award_id}/production-stages", json=data)

    def list_production_stage_attachments(
        self, award_id: int, component_type: str, stage_key: str,
    ) -> list:
        return self._get(
            f"/awards/{award_id}/production-stages/{component_type}/{stage_key}/attachments",
        )

    def upload_production_stage_attachment(
        self, award_id: int, component_type: str, stage_key: str, file_path: str,
    ) -> dict:
        with open(file_path, "rb") as f:
            return self._post(
                f"/awards/{award_id}/production-stages/{component_type}/{stage_key}/attachments",
                files={"file": (file_path.split("/")[-1].split("\\")[-1], f)},
            )

    def download_production_stage_attachment(self, attachment_id: int) -> bytes:
        return self._get_bytes(f"/awards/production-stage-attachments/{attachment_id}")

    def delete_production_stage_attachment(self, attachment_id: int) -> None:
        self._delete(f"/awards/production-stage-attachments/{attachment_id}")

    # -- Inventory -------------------------------------------------------

    def get_inventory(self, award_id: int) -> list:
        return self._get(f"/awards/{award_id}/inventory")

    def create_inventory_item(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/inventory", json=data)

    def update_inventory_item(self, item_id: int, data: dict) -> dict:
        return self._put(f"/awards/inventory/{item_id}", json=data)

    def get_kit_status(self, award_id: int) -> dict:
        return self._get(f"/awards/{award_id}/inventory/kit-status")

    def assemble_kits(self, award_id: int, quantity: int = 1, kit_type: str | None = None) -> dict:
        body: dict = {"quantity": quantity}
        if kit_type:
            body["kit_type"] = kit_type
        return self._post(f"/awards/{award_id}/inventory/assemble", json=body)

    def disassemble_kits(self, award_id: int, quantity: int = 1, kit_type: str | None = None) -> dict:
        body: dict = {"quantity": quantity}
        if kit_type:
            body["kit_type"] = kit_type
        return self._post(f"/awards/{award_id}/inventory/disassemble", json=body)

    def list_decoration_disposals(self, award_id: int) -> list:
        return self._get(f"/awards/{award_id}/decoration-disposals")

    def create_decoration_disposal(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/decoration-disposals", json=data)

    def list_kit_disposals(self, award_id: int) -> list:
        return self._get(f"/awards/{award_id}/kit-disposals")

    def create_kit_disposal(self, award_id: int, data: dict) -> dict:
        return self._post(f"/awards/{award_id}/kit-disposals", json=data)

    def get_universal_stock(self) -> dict:
        return self._get("/awards/universal-stock")

    def update_universal_stock(self, data: dict) -> dict:
        return self._put("/awards/universal-stock", json=data)

    def transfer_to_kit(self, award_id: int, component: str, quantity: int = 1) -> dict:
        return self._post(
            f"/awards/{award_id}/inventory/to-kit",
            json={"component": component, "quantity": quantity},
        )

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

    def get_laureate_awards_monitor(self, laureate_id: int) -> list:
        return self._get(f"/laureates/{laureate_id}/awards-monitor")

    def upload_laureate_photo(self, laureate_id: int, file_path: str) -> None:
        with open(file_path, "rb") as f:
            self._request(
                "POST",
                f"/laureates/{laureate_id}/photo",
                files={"file": (os.path.basename(file_path), f, "application/octet-stream")},
            )

    def download_laureate_photo(self, laureate_id: int) -> bytes:
        return self._get_bytes(f"/laureates/{laureate_id}/photo")

    def update_laureate(self, laureate_id: int, data: dict) -> dict:
        return self._put(f"/laureates/{laureate_id}", json=data)

    def delete_laureate(self, laureate_id: int) -> None:
        self._delete(f"/laureates/{laureate_id}")

    # -- Laureate ↔ Award links -----------------------------------------

    def get_laureate_awards(self, laureate_id: int) -> list:
        return self._get(f"/laureates/{laureate_id}/awards")

    def link_award_to_laureate(self, laureate_id: int, data: dict) -> dict:
        return self._post(f"/laureates/{laureate_id}/awards", json=data)

    def get_laureate_award_context(self, laureate_award_id: int) -> dict:
        """ФИО лауреата и награда по ID связки (для печати удостоверения и т.п.)."""
        return self._get(f"/laureates/links/{laureate_award_id}")

    def get_laureate_awards_by_bulletin_number(self, bulletin_number: str) -> list:
        """Связки с заданным номером бюллетеня (для раздела бюллетеня «Награждение»)."""
        bn = (bulletin_number or "").strip()
        if not bn:
            return []
        return self._get(
            "/laureates/laureate-awards/by-bulletin",
            params={"bulletin_number": bn},
        )

    def get_laureate_awards_for_voting(self) -> list:
        """Связки на этапе «На голосование» (незав. ЖЦ)."""
        return self._get("/laureates/laureate-awards/for-voting")

    # -- Lifecycle -------------------------------------------------------

    def get_laureate_lifecycle(self, laureate_award_id: int) -> dict:
        return self._get(f"/laureates/{laureate_award_id}/lifecycle")

    def create_laureate_lifecycle(self, laureate_award_id: int, data: dict) -> dict:
        return self._post(f"/laureates/{laureate_award_id}/lifecycle", json=data)

    def update_laureate_lifecycle(self, laureate_award_id: int, data: dict) -> dict:
        return self._put(f"/laureates/{laureate_award_id}/lifecycle", json=data)

    # -- Consent PD ------------------------------------------------------

    def get_consent_file_info(self, laureate_award_id: int) -> dict:
        return self._get(f"/laureates/{laureate_award_id}/consent/file/info")

    def download_consent_file(self, laureate_award_id: int) -> bytes:
        return self._get_bytes(f"/laureates/{laureate_award_id}/consent/file")

    def upload_consent_file(self, laureate_award_id: int, file_path: str) -> None:
        import os

        with open(file_path, "rb") as f:
            resp = self._request(
                "POST",
                f"/laureates/{laureate_award_id}/consent/file",
                files={"file": (os.path.basename(file_path), f)},
            )
            # 204 or JSON; ignore body
            if resp.status_code >= 400:
                raise APIError(resp.status_code, resp.text)

    def delete_consent_file(self, laureate_award_id: int) -> None:
        self._delete(f"/laureates/{laureate_award_id}/consent/file")

    def generate_consent_doc(self, laureate_award_id: int) -> bytes:
        return self._get_bytes(f"/laureates/{laureate_award_id}/consent/generate")

    def download_certificate_docx(self, laureate_award_id: int) -> bytes:
        return self._get_bytes(f"/laureates/{laureate_award_id}/certificate/docx")

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

    def upload_committee_member_photo(self, member_id: int, file_path: str) -> None:
        with open(file_path, "rb") as f:
            self._request(
                "POST",
                f"/committee/{member_id}/photo",
                files={"file": (file_path.split("/")[-1].split("\\")[-1], f)},
            )

    def download_committee_member_photo(self, member_id: int) -> bytes:
        return self._get_bytes(f"/committee/{member_id}/photo")

    def delete_committee_member_photo(self, member_id: int) -> None:
        self._delete(f"/committee/{member_id}/photo")

    # -- Signing rights --------------------------------------------------

    def get_signing_rights(self, member_id: int) -> list:
        return self._get(f"/committee/{member_id}/signing-rights")

    def assign_signing_right(self, member_id: int, data: dict) -> dict:
        return self._post(f"/committee/{member_id}/signing-rights", json=data)

    def remove_signing_right(self, right_id: int) -> None:
        self._delete(f"/committee/signing-rights/{right_id}")

    def get_signers_for_award(self, award_id: int, role: str = "signer") -> list:
        return self._get(
            f"/committee/signers/by-award/{award_id}",
            params={"role": role},
        )

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

    def get_bulletin_full(self, bulletin_id: int) -> dict:
        """Бюллетень с разделами и вопросами."""
        return self._get(f"/voting/bulletins/{bulletin_id}/full")

    def download_bulletin_docx(self, bulletin_id: int) -> bytes:
        return self._get_bytes(f"/voting/bulletins/{bulletin_id}/docx")

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

    def delete_section_question(self, question_id: int) -> None:
        self._delete(f"/voting/questions/{question_id}")

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

    def get_bulletin_monitoring_summary(self, bulletin_id: int) -> dict:
        return self._get(f"/voting/bulletins/{bulletin_id}/monitoring-summary")

    def export_bulletin_distributions_csv(self, bulletin_id: int) -> bytes:
        return self._get_bytes(f"/voting/bulletins/{bulletin_id}/distributions.csv")

    def export_bulletin_distributions_xlsx(self, bulletin_id: int) -> bytes:
        return self._get_bytes(f"/voting/bulletins/{bulletin_id}/distributions.xlsx")

    def list_bulletin_distributions(self, bulletin_id: int) -> list:
        return self._get(f"/voting/bulletins/{bulletin_id}/distributions")

    # -- Votes -----------------------------------------------------------

    def record_vote(self, question_id: int, data: dict) -> dict:
        return self._post(f"/voting/questions/{question_id}/votes", json=data)

    # -- Results (vote counting) -----------------------------------------

    def get_vote_results(self, bulletin_id: int) -> list:
        return self._get(f"/voting/bulletins/{bulletin_id}/results")

    # -- Protocols -------------------------------------------------------

    def get_protocols(self) -> list:
        return self._get("/voting/protocols")

    def download_protocol_docx(self, protocol_id: int, variant: str = "full") -> bytes:
        return self._get_bytes(
            f"/voting/protocols/{protocol_id}/docx",
            params={"variant": variant},
        )

    def download_bulletin_monitoring_docx(self, bulletin_id: int) -> bytes:
        return self._get_bytes(f"/voting/bulletins/{bulletin_id}/monitoring.docx")

    def create_protocol(self, bulletin_id: int, data: dict) -> dict:
        return self._post(f"/voting/bulletins/{bulletin_id}/protocol", json=data)

    def update_protocol(self, protocol_id: int, data: dict) -> dict:
        return self._put(f"/voting/protocols/{protocol_id}", json=data)

    def delete_protocol(self, protocol_id: int) -> None:
        self._delete(f"/voting/protocols/{protocol_id}")

    # -- Protocol Extracts -----------------------------------------------

    def create_protocol_extract(self, protocol_id: int, data: dict) -> dict:
        return self._post(f"/voting/protocols/{protocol_id}/extracts", json=data)

    def list_protocol_extracts(self) -> list:
        return self._get("/voting/extracts")

    def download_extract_docx(self, extract_id: int) -> bytes:
        return self._get_bytes(f"/voting/extracts/{extract_id}/docx")

    def delete_protocol_extract(self, extract_id: int) -> None:
        self._delete(f"/voting/extracts/{extract_id}")

    # -- PPZ Submissions -------------------------------------------------

    def create_ppz_submission(self, data: dict) -> dict:
        return self._post("/voting/ppz-submissions", json=data)

    def list_ppz_submissions(self) -> list:
        return self._get("/voting/ppz-submissions")

    def download_ppz_submission_docx(self, ppz_id: int) -> bytes:
        return self._get_bytes(f"/voting/ppz-submissions/{ppz_id}/docx")

    def delete_ppz_submission(self, ppz_id: int) -> None:
        self._delete(f"/voting/ppz-submissions/{ppz_id}")

    # ====================================================================
    #  REPORTS  /reports
    # ====================================================================

    def report_award_lifecycle(self) -> list:
        return self._get("/reports/award-lifecycle")

    def report_warehouse_summary(self) -> list:
        return self._get("/reports/warehouse-summary")

    def report_warehouse_summary_grouped(self, award_type: str | None = None) -> list:
        params = {"award_type": award_type} if award_type else None
        return self._get("/reports/warehouse-summary-grouped", params=params)

    def report_warehouse_reservations(self) -> dict:
        return self._get("/reports/warehouse-reservations")

    def report_kit_disposals_journal(self) -> dict:
        return self._get("/reports/kit-disposals-journal")

    def report_approvals_monitor(
        self,
        approval_type: str | None = None,
        status: str | None = None,
    ) -> list:
        params: dict = {}
        if approval_type:
            params["approval_type"] = approval_type
        if status:
            params["status"] = status
        return self._get("/reports/approvals-monitor", params=params or None)

    def report_awards_by_bulletin(self) -> dict:
        return self._get("/reports/awards-by-bulletin")

    def report_awards_laureates(self, award_id: int | None = None) -> list:
        params = {"award_id": award_id} if award_id else None
        return self._get("/reports/awards-laureates", params=params)

    def report_incomplete_lifecycle(self) -> list:
        return self._get("/reports/incomplete-lifecycle")

    def report_incomplete_lifecycle_sections(self) -> dict:
        return self._get("/reports/incomplete-lifecycle-sections")

    def download_incomplete_lifecycle_sections_xlsx(self) -> bytes:
        return self._get_bytes("/reports/incomplete-lifecycle-sections.xlsx")

    def download_warehouse_summary_xlsx(self) -> bytes:
        return self._get_bytes("/reports/warehouse-summary.xlsx")

    def download_warehouse_grouped_xlsx(self, award_type: str | None = None) -> bytes:
        params = {"award_type": award_type} if award_type else None
        return self._get_bytes("/reports/warehouse-summary-grouped.xlsx", params=params)

    def download_awards_laureates_xlsx(self, award_id: int | None = None) -> bytes:
        params = {"award_id": award_id} if award_id else None
        return self._get_bytes("/reports/awards-laureates.xlsx", params=params)

    def report_statistics(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        award_id: int | None = None,
    ) -> dict:
        params: dict = {}
        if from_date:
            params["from_date"] = from_date.isoformat()
        if to_date:
            params["to_date"] = to_date.isoformat()
        if award_id is not None:
            params["award_id"] = award_id
        return self._get("/reports/statistics", params=params)

    def report_lifecycle_by_stage(self) -> dict:
        """Сводка: сколько связок на каждом этапе ЖЦ лауреата."""
        return self._get("/reports/lifecycle-by-stage")

    def report_site_export(self) -> dict:
        """JSON для публикации на сайте (лауреаты и награды)."""
        return self._get("/reports/site-export")

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
    #  ACCESS MIRROR (полные таблицы как в CSV Access)
    # ====================================================================

    def list_access_mirror_tables(self) -> list:
        return self._get("/access-mirror/tables")

    def get_access_mirror_data(self, table: str) -> dict:
        return self._get("/access-mirror/data", params={"table": table})

    # ====================================================================
    #  HEALTH CHECK
    # ====================================================================

    def health_check(self) -> dict:
        # Не использовать "/" — при base_url .../api это даёт GET /api/ и раньше давало 404.
        # Относительный "health" и "/health" оба дают .../api/health (см. httpx merge_urls).
        return self._get("health")
