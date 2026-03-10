"""
Stock Position Reconciliation Engine — sr_core.py

Matching Rules:
  1. Portfolio_ID must match
  2. Symbol (Stock Summary) must match Scrip (Transaction History),
     optionally via SR_Instrument_Mapping alias table
  3. Quantity (Stock Summary) must equal latest Balance_After_Transaction
     (Transaction History — max Transaction_Date row per portfolio+scrip key)
  4. Missing Qty in Stock Summary  → EXCEPTION
     Missing Balance on latest-date TH row      → EXCEPTION
  5. Any entry not auto-matched     → UNMATCHED

All major loops run in O(N) via hash-map lookups.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    SR_Instrument_Mapping,
    SR_staging_StockSummary_entries,
    SR_staging_TransHistory_entries,
    SR_recon_batches,
    SR_recon_matches,
    SR_recon_findings,
    SR_recon_matches_trail,
    SR_recon_findings_trail,
    BatchStatus,
    MatchKind,
    FindingType,
)

logger = logging.getLogger(__name__)


class StockPositionReconEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def run_batch(
        self,
        summary_file_id: int,
        history_file_id: int,
        actor_id: str,
    ) -> int:
        """Create a new batch and execute reconciliation. Returns batch_id."""
        batch = SR_recon_batches(
            summary_file_id=summary_file_id,
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

    def _run_batch_logic(self, batch: SR_recon_batches, actor_id: str) -> None:
        try:
            # 1. Load instrument map (Symbol -> Scrip alias)  O(M)
            instrument_map = self._build_instrument_map()

            # 2. Load staging rows
            ss_entries: List[SR_staging_StockSummary_entries] = (
                self.db.query(SR_staging_StockSummary_entries)
                .filter_by(file_id=batch.summary_file_id)
                .all()
            )
            th_entries: List[SR_staging_TransHistory_entries] = (
                self.db.query(SR_staging_TransHistory_entries)
                .filter_by(file_id=batch.history_file_id)
                .all()
            )

            # 3. Separate exceptions (parse-time flagged)
            ss_ok, ss_exceptions = self._split_exceptions(ss_entries)
            th_ok, th_exceptions = self._split_exceptions(th_entries)

            # 4. Create findings for parse-time exceptions
            for entry in ss_exceptions:
                self._create_finding(
                    batch, "STOCK_SUMMARY", entry.id,
                    entry.portfolio_id, entry.symbol,
                    FindingType.EXCEPTION,
                    f"Parse error: {entry.validation_error}",
                    actor_id,
                )
            for entry in th_exceptions:
                self._create_finding(
                    batch, "TRANSACTION_HISTORY", entry.id,
                    entry.portfolio_id, entry.scrip,
                    FindingType.EXCEPTION,
                    f"Parse error: {entry.validation_error}",
                    actor_id,
                )

            # 5. Build latest-balance map from valid TH entries  O(N)
            # key = (portfolio_id_lower, scrip_lower)
            # value = (entry, balance_after_transaction)
            latest_balance_map: Dict[
                Tuple[str, str],
                SR_staging_TransHistory_entries
            ] = {}

            for th in th_ok:
                pid = (th.portfolio_id or "").strip().lower()
                scrip = (th.scrip or "").strip().lower()
                key = (pid, scrip)
                existing = latest_balance_map.get(key)
                if existing is None:
                    latest_balance_map[key] = th
                else:
                    # Keep row with latest date
                    if th.transaction_date and (
                        existing.transaction_date is None
                        or th.transaction_date > existing.transaction_date
                    ):
                        latest_balance_map[key] = th

            # 6. Flag TH entries where latest row has NULL balance  O(N)
            for key, th in latest_balance_map.items():
                if th.balance_after_transaction is None:
                    self._create_finding(
                        batch, "TRANSACTION_HISTORY", th.id,
                        th.portfolio_id, th.scrip,
                        FindingType.EXCEPTION,
                        "Missing Balance_After_Transaction on latest date row",
                        actor_id,
                    )

            consumed_th_keys: set = set()  # tracks (pid, scrip) keys matched

            # 7. Auto-match loop — O(N) over Stock Summary
            for ss in ss_ok:
                pid = (ss.portfolio_id or "").strip().lower()
                symbol_raw = (ss.symbol or "").strip()

                # Resolve scrip from symbol via instrument map (O(1))
                scrip_resolved = instrument_map.get(symbol_raw.lower(), symbol_raw)
                scrip_key = scrip_resolved.strip().lower()

                th_key = (pid, scrip_key)
                th_entry = latest_balance_map.get(th_key)

                if th_entry is None:
                    # No TH row — Unmatched
                    self._create_finding(
                        batch, "STOCK_SUMMARY", ss.id,
                        ss.portfolio_id, ss.symbol,
                        FindingType.UNMATCHED,
                        "No matching Transaction History row (Portfolio+Scrip)",
                        actor_id,
                    )
                    continue

                if th_entry.balance_after_transaction is None:
                    # Already flagged as exception above; also flag SS side
                    self._create_finding(
                        batch, "STOCK_SUMMARY", ss.id,
                        ss.portfolio_id, ss.symbol,
                        FindingType.EXCEPTION,
                        "Matched TH row has missing Balance_After_Transaction",
                        actor_id,
                    )
                    continue

                # Compare quantities
                ss_qty = Decimal(str(ss.qty))
                th_balance = Decimal(str(th_entry.balance_after_transaction))

                if ss_qty == th_balance:
                    # AUTO MATCH
                    self._create_match(
                        batch, ss, th_entry,
                        MatchKind.AUTO,
                        "Auto Match: Portfolio_ID + Symbol/Scrip + Qty == Balance",
                        actor_id,
                    )
                    consumed_th_keys.add(th_key)
                else:
                    # Quantity mismatch — Unmatched
                    reason = (
                        f"Quantity mismatch: Stock Summary Qty={ss_qty}, "
                        f"Transaction History Balance={th_balance}"
                    )
                    self._create_finding(
                        batch, "STOCK_SUMMARY", ss.id,
                        ss.portfolio_id, ss.symbol,
                        FindingType.UNMATCHED,
                        reason,
                        actor_id,
                    )

            # 8. Orphaned TH rows (not consumed by any SS match)  O(N)
            for th_key, th_entry in latest_balance_map.items():
                if th_key not in consumed_th_keys:
                    # Only flag as unmatched if not already flagged as exception
                    if th_entry.balance_after_transaction is not None:
                        self._create_finding(
                            batch, "TRANSACTION_HISTORY", th_entry.id,
                            th_entry.portfolio_id, th_entry.scrip,
                            FindingType.UNMATCHED,
                            "No matching Stock Summary row for this Portfolio+Scrip",
                            actor_id,
                        )

            # 9. Mark batch complete
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = datetime.utcnow()
            self.db.commit()

            # Audit log
            logger.info(
                "SR batch %s completed. SS=%d rows, TH=%d rows.",
                batch.id, len(ss_entries), len(th_entries)
            )

        except Exception as exc:
            logger.exception("SR batch %s failed: %s", batch.id, exc)
            batch.status = BatchStatus.FAILED
            batch.completed_at = datetime.utcnow()
            self.db.commit()
            raise

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _build_instrument_map(self) -> Dict[str, str]:
        """Return {symbol_lower: scrip_lower} from SR_Instrument_Mapping."""
        rows = self.db.query(SR_Instrument_Mapping).all()
        return {r.symbol.strip().lower(): r.scrip.strip().lower() for r in rows}

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
        batch: SR_recon_batches,
        ss: SR_staging_StockSummary_entries,
        th: SR_staging_TransHistory_entries,
        kind: MatchKind,
        reason: str,
        actor_id: str,
    ) -> SR_recon_matches:
        mid = f"SR-{batch.id}-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()

        match = SR_recon_matches(
            batch_id=batch.id,
            summary_entry_id=ss.id,
            history_entry_id=th.id,
            portfolio_id=ss.portfolio_id,
            symbol=ss.symbol,
            scrip=th.scrip,
            match_kind=kind,
            match_id=mid,
            reason=reason,
            created_by=actor_id,
            created_at=now,
        )
        self.db.add(match)
        self.db.flush()

        trail = SR_recon_matches_trail(
            SR_recon_match_ID=match.id,
            batch_id=batch.id,
            summary_entry_id=ss.id,
            history_entry_id=th.id,
            portfolio_id=ss.portfolio_id,
            symbol=ss.symbol,
            scrip=th.scrip,
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
        batch: SR_recon_batches,
        side: str,
        entry_id: int,
        portfolio_id: Optional[str],
        symbol_or_scrip: Optional[str],
        finding_type: FindingType,
        reason: str,
        actor_id: str,
    ) -> SR_recon_findings:
        now = datetime.utcnow()

        finding = SR_recon_findings(
            batch_id=batch.id,
            side=side,
            entry_id=entry_id,
            portfolio_id=portfolio_id,
            symbol_or_scrip=symbol_or_scrip,
            finding_type=finding_type,
            finding_reason=reason,
            created_at=now,
            created_by=actor_id,
        )
        self.db.add(finding)
        self.db.flush()

        trail = SR_recon_findings_trail(
            SR_recon_finding_ID=finding.id,
            batch_id=batch.id,
            side=side,
            entry_id=entry_id,
            portfolio_id=portfolio_id,
            symbol_or_scrip=symbol_or_scrip,
            finding_type=finding_type,
            finding_reason=reason,
            created_at=now,
            created_by=actor_id,
            Action="CREATE",
        )
        self.db.add(trail)
        return finding


