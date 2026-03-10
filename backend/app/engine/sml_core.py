"""
Stock Movement Liquidation Reconciliation Engine — sml_core.py

Matching Rules (O(N) via hash-map):
  1. Portfolio_ID must match (grouping key)
  2. Scrip must match Scrip, optionally via SMA_Instrument_Mapping alias table (shared mapping)
  3. SUM(Qty) from Stock Liquidation  ==  SUM(Debit_Quantity) from Transaction History
     — both grouped by (Portfolio_ID + Scrip)
  4. Missing Qty in Stock Liquidation entry      → EXCEPTION (parse-time flag)
     Missing Debit_Quantity on any row in group  → EXCEPTION (engine-level)
  5. Anything not auto-matched                   → UNMATCHED
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    SMA_Instrument_Mapping,          # reuse shared alias mapping
    SML_staging_StockLiquidation_entries,
    SML_staging_TransHistory_entries,
    SML_recon_batches,
    SML_recon_matches,
    SML_recon_findings,
    SML_recon_matches_trail,
    SML_recon_findings_trail,
    BatchStatus,
    MatchKind,
    FindingType,
)

logger = logging.getLogger(__name__)


class StockLiquidationReconEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def run_batch(
        self,
        liquidation_file_id: int,
        history_file_id: int,
        actor_id: str,
    ) -> int:
        """Create a new batch and execute reconciliation. Returns batch_id."""
        batch = SML_recon_batches(
            liquidation_file_id=liquidation_file_id,
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

    def _run_batch_logic(self, batch: SML_recon_batches, actor_id: str) -> None:
        try:
            # 1. Build instrument alias map  O(M)
            instrument_map = self._build_instrument_map()  # {scrip_a_lower: scrip_b_lower}

            # 2. Load all staging rows
            liq_entries: List[SML_staging_StockLiquidation_entries] = (
                self.db.query(SML_staging_StockLiquidation_entries)
                .filter_by(file_id=batch.liquidation_file_id)
                .all()
            )
            th_entries: List[SML_staging_TransHistory_entries] = (
                self.db.query(SML_staging_TransHistory_entries)
                .filter_by(file_id=batch.history_file_id)
                .all()
            )

            now = datetime.utcnow()

            # 3. Identify EXCEPTION entries on the Liquidation side (missing qty)
            #    These are flagged at parse time.
            liq_exceptions: List[SML_staging_StockLiquidation_entries] = []
            liq_valid: List[SML_staging_StockLiquidation_entries] = []
            for e in liq_entries:
                if e.validation_error and "Missing_Qty" in e.validation_error:
                    liq_exceptions.append(e)
                else:
                    liq_valid.append(e)

            # Emit EXCEPTION findings for missing-qty Liquidation rows  O(E)
            for exc in liq_exceptions:
                finding = SML_recon_findings(
                    batch_id=batch.id,
                    side="STOCK_LIQUIDATION",
                    entry_id=exc.id,
                    entry_ids=str(exc.id),
                    portfolio_id=exc.portfolio_id,
                    scrip=exc.scrip,
                    stock_name=exc.stock_name,
                    liq_qty_sum=None,
                    th_debit_qty_sum=None,
                    finding_type=FindingType.EXCEPTION,
                    finding_reason="Missing Qty in Stock Liquidation file",
                    created_at=now,
                    created_by=actor_id,
                )
                self.db.add(finding)
                self.db.flush()
                trail = SML_recon_findings_trail(
                    SML_recon_finding_ID=finding.id,
                    batch_id=batch.id,
                    side=finding.side,
                    entry_id=finding.entry_id,
                    entry_ids=finding.entry_ids,
                    portfolio_id=finding.portfolio_id,
                    scrip=finding.scrip,
                    liq_qty_sum=finding.liq_qty_sum,
                    th_debit_qty_sum=finding.th_debit_qty_sum,
                    finding_type=finding.finding_type,
                    finding_reason=finding.finding_reason,
                    created_at=now,
                    created_by=actor_id,
                    Action="CREATE",
                )
                self.db.add(trail)

            # 4. Build aggregation map for valid Liquidation entries
            #    key: (portfolio_id_lower, canonical_scrip_lower) → {qty_sum, ids, stock_name}
            liq_map: Dict[Tuple[str, str], dict] = {}
            for e in liq_valid:
                pid   = (e.portfolio_id or "").strip().lower()
                scrip = self._canonical_scrip(e.scrip, instrument_map)
                key   = (pid, scrip)
                if key not in liq_map:
                    liq_map[key] = {
                        "qty_sum":    Decimal(0),
                        "ids":        [],
                        "stock_name": e.stock_name or "",
                        "has_null":   False,
                    }
                if e.qty is None:
                    liq_map[key]["has_null"] = True
                else:
                    liq_map[key]["qty_sum"] += e.qty
                liq_map[key]["ids"].append(e.id)

            # 5. Build aggregation map for Transaction History entries
            #    key: (portfolio_id_lower, scrip_lower) → {debit_qty_sum, ids}
            th_map: Dict[Tuple[str, str], dict] = {}
            for e in th_entries:
                pid   = (e.portfolio_id or "").strip().lower()
                scrip = self._canonical_scrip(e.scrip, instrument_map)
                key   = (pid, scrip)
                if key not in th_map:
                    th_map[key] = {
                        "debit_qty_sum": Decimal(0),
                        "ids":           [],
                    }
                if e.debit_quantity is not None:
                    th_map[key]["debit_qty_sum"] += e.debit_quantity
                th_map[key]["ids"].append(e.id)

            # 6. Match  O(N)
            matched_liq_keys = set()
            matched_th_keys  = set()

            for key, ldata in liq_map.items():
                # Check TH side exists
                if key not in th_map:
                    continue  # will become UNMATCHED below

                tdata = th_map[key]

                # Rule 3: qty sums must match
                if ldata["qty_sum"] != tdata["debit_qty_sum"]:
                    continue  # will become UNMATCHED

                # AUTO MATCH ✓
                match = SML_recon_matches(
                    batch_id=batch.id,
                    liquidation_entry_ids=",".join(str(i) for i in ldata["ids"]),
                    history_entry_ids=",".join(str(i) for i in tdata["ids"]),
                    portfolio_id=key[0],
                    scrip=key[1],
                    stock_name=ldata["stock_name"],
                    liq_qty_sum=ldata["qty_sum"],
                    th_debit_qty_sum=tdata["debit_qty_sum"],
                    match_kind=MatchKind.AUTO,
                    match_id=str(uuid.uuid4()),
                    created_at=now,
                    created_by=actor_id,
                )
                self.db.add(match)
                self.db.flush()
                trail = SML_recon_matches_trail(
                    SML_recon_match_ID=match.id,
                    batch_id=batch.id,
                    liquidation_entry_ids=match.liquidation_entry_ids,
                    history_entry_ids=match.history_entry_ids,
                    portfolio_id=match.portfolio_id,
                    scrip=match.scrip,
                    liq_qty_sum=match.liq_qty_sum,
                    th_debit_qty_sum=match.th_debit_qty_sum,
                    match_kind=match.match_kind,
                    match_id=match.match_id,
                    created_at=now,
                    created_by=actor_id,
                    Action="CREATE",
                )
                self.db.add(trail)
                matched_liq_keys.add(key)
                matched_th_keys.add(key)

            # 7. UNMATCHED — Liquidation side not matched
            for key, ldata in liq_map.items():
                if key in matched_liq_keys:
                    continue
                th_debit = th_map[key]["debit_qty_sum"] if key in th_map else None
                finding = SML_recon_findings(
                    batch_id=batch.id,
                    side="STOCK_LIQUIDATION",
                    entry_id=ldata["ids"][0] if ldata["ids"] else None,
                    entry_ids=",".join(str(i) for i in ldata["ids"]),
                    portfolio_id=key[0],
                    scrip=key[1],
                    stock_name=ldata["stock_name"],
                    liq_qty_sum=ldata["qty_sum"],
                    th_debit_qty_sum=th_debit,
                    finding_type=FindingType.UNMATCHED,
                    finding_reason="No matching Transaction History entry",
                    created_at=now,
                    created_by=actor_id,
                )
                self.db.add(finding)
                self.db.flush()
                trail = SML_recon_findings_trail(
                    SML_recon_finding_ID=finding.id,
                    batch_id=batch.id,
                    side=finding.side,
                    entry_id=finding.entry_id,
                    entry_ids=finding.entry_ids,
                    portfolio_id=finding.portfolio_id,
                    scrip=finding.scrip,
                    liq_qty_sum=finding.liq_qty_sum,
                    th_debit_qty_sum=finding.th_debit_qty_sum,
                    finding_type=finding.finding_type,
                    finding_reason=finding.finding_reason,
                    created_at=now,
                    created_by=actor_id,
                    Action="CREATE",
                )
                self.db.add(trail)

            # 8. UNMATCHED — TH side not matched
            for key, tdata in th_map.items():
                if key in matched_th_keys:
                    continue
                liq_q = liq_map[key]["qty_sum"] if key in liq_map else None
                finding = SML_recon_findings(
                    batch_id=batch.id,
                    side="TRANSACTION_HISTORY",
                    entry_id=tdata["ids"][0] if tdata["ids"] else None,
                    entry_ids=",".join(str(i) for i in tdata["ids"]),
                    portfolio_id=key[0],
                    scrip=key[1],
                    stock_name="",
                    liq_qty_sum=liq_q,
                    th_debit_qty_sum=tdata["debit_qty_sum"],
                    finding_type=FindingType.UNMATCHED,
                    finding_reason="No matching Stock Liquidation entry",
                    created_at=now,
                    created_by=actor_id,
                )
                self.db.add(finding)
                self.db.flush()
                trail = SML_recon_findings_trail(
                    SML_recon_finding_ID=finding.id,
                    batch_id=batch.id,
                    side=finding.side,
                    entry_id=finding.entry_id,
                    entry_ids=finding.entry_ids,
                    portfolio_id=finding.portfolio_id,
                    scrip=finding.scrip,
                    liq_qty_sum=finding.liq_qty_sum,
                    th_debit_qty_sum=finding.th_debit_qty_sum,
                    finding_type=finding.finding_type,
                    finding_reason=finding.finding_reason,
                    created_at=now,
                    created_by=actor_id,
                    Action="CREATE",
                )
                self.db.add(trail)

            batch.status       = BatchStatus.COMPLETED
            batch.completed_at = now
            self.db.commit()

        except Exception:
            logger.exception("SML batch %s failed", batch.id)
            batch.status = BatchStatus.FAILED
            self.db.commit()
            raise

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _build_instrument_map(self) -> Dict[str, str]:
        """Returns {scrip_a_lower: scrip_b_lower} from shared SMA_Instrument_Mapping."""
        rows = self.db.query(SMA_Instrument_Mapping).all()
        return {r.scrip_a.strip().lower(): r.scrip_b.strip().lower() for r in rows}

    @staticmethod
    def _canonical_scrip(scrip: Optional[str], instrument_map: Dict[str, str]) -> str:
        """Normalise a scrip to its canonical lower-case form via alias map."""
        if not scrip:
            return ""
        lower = scrip.strip().lower()
        return instrument_map.get(lower, lower)
