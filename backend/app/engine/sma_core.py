"""
Stock Movement Acquisition Reconciliation Engine — sma_core.py

Matching Rules (O(N) via hash-map):
  1. Portfolio_ID must match (grouping key)
  2. Scrip must match Scrip, optionally via SMA_Instrument_Mapping alias table
  3. SUM(Qty) from Stock Acquisitions  ==  SUM(Credit_Quantity) from Transaction History
     — both grouped by (Portfolio_ID + Scrip)
  4. Missing Qty in Stock Acquisition  → EXCEPTION (parse-time flag)
     Missing Credit_Quantity on any row in group → EXCEPTION (engine-level)
  5. Anything not auto-matched         → UNMATCHED
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    SMA_Instrument_Mapping,
    SMA_staging_StockAcquisition_entries,
    SMA_staging_TransHistory_entries,
    SMA_recon_batches,
    SMA_recon_matches,
    SMA_recon_findings,
    SMA_recon_matches_trail,
    SMA_recon_findings_trail,
    BatchStatus,
    MatchKind,
    FindingType,
)

logger = logging.getLogger(__name__)


class StockAcquisitionReconEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def run_batch(
        self,
        acquisition_file_id: int,
        history_file_id: int,
        actor_id: str,
    ) -> int:
        """Create a new batch and execute reconciliation. Returns batch_id."""
        batch = SMA_recon_batches(
            acquisition_file_id=acquisition_file_id,
            history_file_id=history_file_id,
            status=BatchStatus.RUNNING,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        self._run_batch_logic(batch, actor_id)
        return batch.id

    # ------------------------------------------------------------------
    # CORE LOGIC
    # ------------------------------------------------------------------

    def _run_batch_logic(self, batch: SMA_recon_batches, actor_id: str) -> None:
        try:
            # 1. Build instrument alias map  O(M)
            instrument_map = self._build_instrument_map()  # {scrip_a_lower: scrip_b_lower}

            # 2. Load all staging rows
            acq_entries: List[SMA_staging_StockAcquisition_entries] = (
                self.db.query(SMA_staging_StockAcquisition_entries)
                .filter_by(file_id=batch.acquisition_file_id)
                .all()
            )
            th_entries: List[SMA_staging_TransHistory_entries] = (
                self.db.query(SMA_staging_TransHistory_entries)
                .filter_by(file_id=batch.history_file_id)
                .all()
            )

            # 3. Split out parse-time exceptions
            acq_ok, acq_exceptions = self._split_exceptions(acq_entries)
            th_ok, th_exceptions = self._split_exceptions(th_entries)

            # 4. Record parse-time exceptions
            for entry in acq_exceptions:
                self._create_finding(
                    batch, "STOCK_ACQUISITION", entry.id,
                    entry.portfolio_id, entry.scrip, entry.stock_name,
                    FindingType.EXCEPTION,
                    f"Parse error: {entry.validation_error}",
                    actor_id,
                    acq_qty_sum=None,
                    th_credit_qty_sum=None,
                )
            for entry in th_exceptions:
                self._create_finding(
                    batch, "TRANSACTION_HISTORY", entry.id,
                    entry.portfolio_id, entry.scrip, None,
                    FindingType.EXCEPTION,
                    f"Parse error: {entry.validation_error}",
                    actor_id,
                    acq_qty_sum=None,
                    th_credit_qty_sum=None,
                )

            # 5. Build SUM maps  O(N) each
            # key = (portfolio_id_lower, scrip_lower)

            # Acquisition SUM map: key → {sum, ids, stock_name}
            acq_sum_map: Dict[Tuple[str, str], dict] = {}
            for entry in acq_ok:
                pid   = (entry.portfolio_id or "").strip().lower()
                scrip = (entry.scrip or "").strip()
                scrip_resolved = instrument_map.get(scrip.lower(), scrip)
                key   = (pid, scrip_resolved.lower())
                if key not in acq_sum_map:
                    acq_sum_map[key] = {
                        "sum": Decimal("0"),
                        "ids": [],
                        "stock_name": entry.stock_name or "",
                        "portfolio_id": entry.portfolio_id,
                        "scrip": entry.scrip,          # original case
                        "has_null_qty": False,
                    }
                if entry.qty is None:
                    acq_sum_map[key]["has_null_qty"] = True
                else:
                    acq_sum_map[key]["sum"] += Decimal(str(entry.qty))
                acq_sum_map[key]["ids"].append(entry.id)

            # TH SUM map: key → {sum, ids}
            th_sum_map: Dict[Tuple[str, str], dict] = {}
            for entry in th_ok:
                pid   = (entry.portfolio_id or "").strip().lower()
                scrip = (entry.scrip or "").strip()
                key   = (pid, scrip.lower())
                if key not in th_sum_map:
                    th_sum_map[key] = {
                        "sum": Decimal("0"),
                        "ids": [],
                        "portfolio_id": entry.portfolio_id,
                        "scrip": entry.scrip,
                    }
                if entry.credit_quantity is not None:
                    th_sum_map[key]["sum"] += Decimal(str(entry.credit_quantity))
                th_sum_map[key]["ids"].append(entry.id)

            # 6. Match loop  O(N) over acquisition keys
            consumed_th_keys: set = set()

            for key, acq_data in acq_sum_map.items():
                portfolio_id = acq_data["portfolio_id"]
                scrip        = acq_data["scrip"]
                stock_name   = acq_data["stock_name"]
                acq_ids_str  = ",".join(str(i) for i in acq_data["ids"])

                # Rule 4a: any row in group had null qty → EXCEPTION
                if acq_data["has_null_qty"]:
                    self._create_finding(
                        batch, "STOCK_ACQUISITION", acq_data["ids"][0],
                        portfolio_id, scrip, stock_name,
                        FindingType.EXCEPTION,
                        "One or more Acquisition rows have missing Qty",
                        actor_id,
                        acq_qty_sum=None,
                        th_credit_qty_sum=None,
                        entry_ids=acq_ids_str,
                    )
                    continue

                th_data = th_sum_map.get(key)
                if th_data is None:
                    # Rule 5: no TH group → UNMATCHED
                    self._create_finding(
                        batch, "STOCK_ACQUISITION", acq_data["ids"][0],
                        portfolio_id, scrip, stock_name,
                        FindingType.UNMATCHED,
                        "No matching Transaction History rows for this Portfolio+Scrip",
                        actor_id,
                        acq_qty_sum=float(acq_data["sum"]),
                        th_credit_qty_sum=None,
                        entry_ids=acq_ids_str,
                    )
                    continue

                th_ids_str = ",".join(str(i) for i in th_data["ids"])

                acq_sum = acq_data["sum"]
                th_sum  = th_data["sum"]

                if acq_sum == th_sum:
                    # Rule 3: AUTO MATCH
                    self._create_match(
                        batch,
                        portfolio_id=portfolio_id,
                        scrip=scrip,
                        stock_name=stock_name,
                        acq_ids_str=acq_ids_str,
                        th_ids_str=th_ids_str,
                        acq_sum=acq_sum,
                        th_sum=th_sum,
                        kind=MatchKind.AUTO,
                        reason=f"Auto Match: SUM(Qty)={acq_sum} == SUM(Credit_Quantity)={th_sum}",
                        actor_id=actor_id,
                    )
                    consumed_th_keys.add(key)
                else:
                    # Rule 5: Quantity sum mismatch → UNMATCHED
                    reason = (
                        f"Sum mismatch: Acquisition SUM(Qty)={acq_sum}, "
                        f"Transaction History SUM(Credit_Quantity)={th_sum}"
                    )
                    self._create_finding(
                        batch, "STOCK_ACQUISITION", acq_data["ids"][0],
                        portfolio_id, scrip, stock_name,
                        FindingType.UNMATCHED,
                        reason,
                        actor_id,
                        acq_qty_sum=float(acq_sum),
                        th_credit_qty_sum=float(th_sum),
                        entry_ids=acq_ids_str,
                    )

            # 7. Orphaned TH groups  O(N)
            for key, th_data in th_sum_map.items():
                if key not in consumed_th_keys:
                    th_ids_str = ",".join(str(i) for i in th_data["ids"])
                    self._create_finding(
                        batch, "TRANSACTION_HISTORY", th_data["ids"][0],
                        th_data["portfolio_id"], th_data["scrip"], None,
                        FindingType.UNMATCHED,
                        "No matching Stock Acquisition rows for this Portfolio+Scrip",
                        actor_id,
                        acq_qty_sum=None,
                        th_credit_qty_sum=float(th_data["sum"]),
                        entry_ids=th_ids_str,
                    )

            # 8. Mark complete
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info(
                "SMA batch %s completed. Acq=%d rows, TH=%d rows.",
                batch.id, len(acq_entries), len(th_entries)
            )

        except Exception as exc:
            logger.exception("SMA batch %s failed: %s", batch.id, exc)
            batch.status = BatchStatus.FAILED
            batch.completed_at = datetime.utcnow()
            self.db.commit()
            raise

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _build_instrument_map(self) -> Dict[str, str]:
        """Return {scrip_a_lower: scrip_b_lower} from SMA_Instrument_Mapping."""
        rows = self.db.query(SMA_Instrument_Mapping).all()
        return {r.scrip_a.strip().lower(): r.scrip_b.strip().lower() for r in rows}

    @staticmethod
    def _split_exceptions(entries):
        ok, exceptions = [], []
        for e in entries:
            if e.validation_error:
                exceptions.append(e)
            else:
                ok.append(e)
        return ok, exceptions

    def _create_match(
        self,
        batch: SMA_recon_batches,
        portfolio_id: str,
        scrip: str,
        stock_name: str,
        acq_ids_str: str,
        th_ids_str: str,
        acq_sum: Decimal,
        th_sum: Decimal,
        kind: MatchKind,
        reason: str,
        actor_id: str,
    ) -> SMA_recon_matches:
        mid = f"SMA-{batch.id}-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()

        match = SMA_recon_matches(
            batch_id=batch.id,
            acquisition_entry_ids=acq_ids_str,
            history_entry_ids=th_ids_str,
            portfolio_id=portfolio_id,
            scrip=scrip,
            stock_name=stock_name,
            acq_qty_sum=acq_sum,
            th_credit_qty_sum=th_sum,
            match_kind=kind,
            match_id=mid,
            reason=reason,
            created_by=actor_id,
            created_at=now,
        )
        self.db.add(match)
        self.db.flush()

        trail = SMA_recon_matches_trail(
            SMA_recon_match_ID=match.id,
            batch_id=batch.id,
            acquisition_entry_ids=acq_ids_str,
            history_entry_ids=th_ids_str,
            portfolio_id=portfolio_id,
            scrip=scrip,
            acq_qty_sum=acq_sum,
            th_credit_qty_sum=th_sum,
            match_kind=kind,
            match_id=mid,
            reason=reason,
            created_by=actor_id,
            created_at=now,
            Action="CREATE",
        )
        self.db.add(trail)
        return match

    def _create_finding(
        self,
        batch: SMA_recon_batches,
        side: str,
        entry_id: Optional[int],
        portfolio_id: Optional[str],
        scrip: Optional[str],
        stock_name: Optional[str],
        finding_type: FindingType,
        reason: str,
        actor_id: str,
        acq_qty_sum=None,
        th_credit_qty_sum=None,
        entry_ids: Optional[str] = None,
    ) -> SMA_recon_findings:
        now = datetime.utcnow()

        finding = SMA_recon_findings(
            batch_id=batch.id,
            side=side,
            entry_id=entry_id,
            entry_ids=entry_ids,
            portfolio_id=portfolio_id,
            scrip=scrip,
            stock_name=stock_name,
            acq_qty_sum=acq_qty_sum,
            th_credit_qty_sum=th_credit_qty_sum,
            finding_type=finding_type,
            finding_reason=reason,
            created_at=now,
            created_by=actor_id,
        )
        self.db.add(finding)
        self.db.flush()

        trail = SMA_recon_findings_trail(
            SMA_recon_finding_ID=finding.id,
            batch_id=batch.id,
            side=side,
            entry_id=entry_id,
            entry_ids=entry_ids,
            portfolio_id=portfolio_id,
            scrip=scrip,
            acq_qty_sum=acq_qty_sum,
            th_credit_qty_sum=th_credit_qty_sum,
            finding_type=finding_type,
            finding_reason=reason,
            created_at=now,
            created_by=actor_id,
            Action="CREATE",
        )
        self.db.add(trail)
        return finding
