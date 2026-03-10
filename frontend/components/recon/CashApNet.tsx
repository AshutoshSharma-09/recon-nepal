"use client";

import React, { useState } from 'react';
import { LinkTransactionModal } from './LinkTransactionModal';
import { SplitTransactionModal } from './SplitTransactionModal';
import { BreakMatchModal } from './BreakMatchModal';
import { API_URL, API_KEY } from '@/lib/config';
import { CashARAPUploadModal } from './CashARAPUploadModal';
import { Pagination } from './Pagination';

interface CashApNetProps {
    cashRecords?: any[];
    apRecords?: any[];
    batchId?: number | null;
    onCashUpload: (file: File) => void;
    onApUpload: (file: File) => void;
    isUploading: boolean;
    onAutoMatch: () => Promise<boolean>;
    isProcessing: boolean;
    hasCashFile: boolean;
    hasApFile: boolean;
    toleranceAmount?: number;
    dateWindowDays?: number;
    onResetFiles?: () => void;
}

export function CashApNet({
    cashRecords = [],
    apRecords = [],
    batchId,
    onCashUpload,
    onApUpload,
    isUploading,
    onAutoMatch,
    isProcessing,
    hasCashFile,
    hasApFile,
    toleranceAmount = 50,
    dateWindowDays = 2,
    onResetFiles
}: CashApNetProps) {
    const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
    const [isSplitModalOpen, setIsSplitModalOpen] = useState(false);
    const [isBreakMatchModalOpen, setIsBreakMatchModalOpen] = useState(false);
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const [isReasonModalOpen, setIsReasonModalOpen] = useState(false);
    const [selectedReason, setSelectedReason] = useState<string>('');
    const [selectedRow, setSelectedRow] = useState<any>(null);

    // Split State
    const [splitParentRow, setSplitParentRow] = useState<any>(null);
    const [splitCandidateRows, setSplitCandidateRows] = useState<any[]>([]);

    const [viewFilter, setViewFilter] = useState<'ALL' | 'MATCHED' | 'EXCEPTION' | 'UNMATCHED'>('ALL');
    const [searchQuery, setSearchQuery] = useState('');

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    const handleAutoMatchWrapper = async () => {
        const success = await onAutoMatch();
        if (success) {
            setIsUploadModalOpen(false);
        }
    };

    // ─── Process Data into Rows ───────────────────────────────────────────────
    // NOTE: We map Cash → "Bank" and AP → "Broker" throughout so that
    // LinkTransactionModal and SplitTransactionModal work without modification.
    const processRows = () => {
        const rows: any[] = [];
        const matches = new Map<string, { cash?: any, ap?: any }>();

        const consumedCashIds = new Set<string>();
        const consumedApIds = new Set<string>();

        // 1. Group Strict Matches (backend-confirmed)
        cashRecords.forEach(r => {
            if (r.match_status === 'MATCHED' && r.match_id) {
                if (!matches.has(r.match_id)) matches.set(r.match_id, {});
                matches.get(r.match_id)!.cash = r;
                consumedCashIds.add(r.id || r.VchID);
            }
        });
        apRecords.forEach(r => {
            if (r.match_status === 'MATCHED' && r.match_id) {
                if (!matches.has(r.match_id)) matches.set(r.match_id, {});
                matches.get(r.match_id)!.ap = r;
                consumedApIds.add(r.id || r.VchID);
            }
        });

        // 2. Add Matched Rows
        matches.forEach((pair) => {
            const c = pair.cash || {};
            const a = pair.ap || {};
            let status = 'MATCHED';
            const kind = c.match_kind || a.match_kind || 'AUTO';
            if (kind === 'AUTO') status = 'AUTO_MATCH';
            if (kind === 'MANUAL') status = 'MANUAL_MATCH';

            rows.push({
                // Cash side (mapped as "bank" for modal compatibility)
                bankPortfolio: c.PortfolioID || '---',
                bankDate: c.Date || '---',
                bankRef: c.VchID || '---',
                bankAmount: c.Debit ? `-${c.Debit}` : (c.Credit ? `+${c.Credit}` : '0'),
                // AP side (mapped as "broker" for modal compatibility)
                brokerPortfolio: a.PortfolioID || '---',
                brokerDate: a.Date || '---',
                brokerRef: a.VchID || '---',
                // For AP: DB_Amount is typically Debit (positive in our context of matching Credit Cash)
                // If it came as Debit, display as such.
                brokerNet: a.Debit ? `-${a.Debit}` : (a.Credit ? `+${a.Credit}` : '0'),
                status,
                reason: c.reason || a.reason || '',
                rawBank: c,   // Cash record stored as rawBank
                rawBroker: a  // AP record stored as rawBroker
            });
        });

        // 3. Soft Match / Heuristic Pairing for unmatched records
        const unmatchedCash = cashRecords.filter(r => !consumedCashIds.has(r.id || r.VchID));
        const unmatchedAp = apRecords.filter(r => !consumedApIds.has(r.id || r.VchID));

        // Helper: find a soft AP match for a cash record
        const findApMatch = (cashRecord: any) => {
            return unmatchedAp.find(ap => {
                if (consumedApIds.has(ap.id || ap.VchID)) return false;

                // Criteria 1: Same VchID
                if (cashRecord.VchID && ap.VchID &&
                    cashRecord.VchID.trim() === ap.VchID.trim() &&
                    cashRecord.VchID !== '---') return true;

                // Criteria 2: Same Amount AND Date
                // Cash Credit vs AP Debit
                const cashAmt = cashRecord.Credit || cashRecord.Debit;
                const apAmt = ap.Credit || ap.Debit;
                if (cashRecord.Date && ap.Date && cashRecord.Date === ap.Date &&
                    cashAmt && apAmt && cashAmt == apAmt) return true;

                return false;
            });
        };

        unmatchedCash.forEach(c => {
            const softMatch = findApMatch(c);
            if (softMatch) {
                consumedCashIds.add(c.id || c.VchID);
                consumedApIds.add(softMatch.id || softMatch.VchID);

                const cRef = c.VchID || '---';
                const cDate = c.Date || '---';
                const cAmt = c.Credit || c.Debit || '0.00';

                const apRef = softMatch.VchID || '---';
                const apDate = softMatch.Date || '---';
                const apAmt = softMatch.Credit || softMatch.Debit || '0.00';

                const hasMissingData =
                    cRef === '---' || cDate === '---' || cAmt === '0.00' || !c.PortfolioID ||
                    apRef === '---' || apDate === '---' || apAmt === '0.00' || !softMatch.PortfolioID ||
                    !!c.validation_error || !!softMatch.validation_error;

                rows.push({
                    bankPortfolio: c.PortfolioID || '---',
                    bankDate: cDate,
                    bankRef: cRef,
                    bankAmount: c.Debit ? `-${c.Debit}` : (c.Credit ? `+${c.Credit}` : '0'),
                    brokerPortfolio: softMatch.PortfolioID || '---',
                    brokerDate: apDate,
                    brokerRef: apRef,
                    brokerNet: softMatch.Debit ? `-${softMatch.Debit}` : (softMatch.Credit ? `+${softMatch.Credit}` : '0'),
                    status: hasMissingData ? 'EXCEPTION' : 'UNMATCHED',
                    reason: c.reason || softMatch.reason || '',
                    rawBank: c,
                    rawBroker: softMatch
                });
            }
        });

        // 4. Truly Orphaned Cash
        cashRecords.filter(r => !consumedCashIds.has(r.id || r.VchID)).forEach(r => {
            const hasAmount = (r.Credit && r.Credit !== 0) || (r.Debit && r.Debit !== 0);
            const isException = r.validation_error || !hasAmount || !r.Date || !r.VchID || !r.PortfolioID;
            rows.push({
                bankPortfolio: r.PortfolioID || '---',
                bankDate: r.Date || '---',
                bankRef: r.VchID || '---',
                bankAmount: r.Debit ? `-${r.Debit}` : (r.Credit ? `+${r.Credit}` : '0'),
                brokerPortfolio: '---',
                brokerDate: '---',
                brokerRef: '---',
                brokerNet: '---',
                status: isException ? 'EXCEPTION' : (r.match_status || 'UNMATCHED'),
                reason: r.reason || '',
                rawBank: r,
                rawBroker: null
            });
        });

        // 5. Truly Orphaned AP
        apRecords.filter(r => !consumedApIds.has(r.id || r.VchID)).forEach(r => {
            const hasAmount = (r.Credit && r.Credit !== 0) || (r.Debit && r.Debit !== 0);
            const isException = r.validation_error || !hasAmount || !r.Date || !r.VchID || !r.PortfolioID;
            rows.push({
                bankPortfolio: '---',
                bankDate: '---',
                bankRef: '---',
                bankAmount: '---',
                brokerPortfolio: r.PortfolioID || '---',
                brokerDate: r.Date || '---',
                brokerRef: r.VchID || '---',
                brokerNet: r.Debit ? `-${r.Debit}` : (r.Credit ? `+${r.Credit}` : '0'),
                status: isException ? 'EXCEPTION' : (r.match_status || 'UNMATCHED'),
                reason: r.reason || '',
                rawBank: null,
                rawBroker: r
            });
        });

        return rows;
    };

    const allRows = processRows();
    const displayRows = allRows.filter(r => {
        let matchesView = true;
        if (viewFilter === 'MATCHED') matchesView = ['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH'].includes(r.status);
        if (viewFilter === 'EXCEPTION') matchesView = r.status === 'EXCEPTION';
        if (viewFilter === 'UNMATCHED') matchesView = !['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH', 'EXCEPTION'].includes(r.status);

        let matchesSearch = true;
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase().trim();
            const pf = (r.bankPortfolio !== '---' ? r.bankPortfolio : r.brokerPortfolio) || '';
            matchesSearch = pf.toLowerCase().includes(query);
        }
        return matchesView && matchesSearch;
    });

    const sortedRows = displayRows.sort((a, b) => {
        const statusOrder: Record<string, number> = { AUTO_MATCH: 1, MANUAL_MATCH: 2, EXCEPTION: 3, UNMATCHED: 4 };
        const statusDiff = (statusOrder[a.status] || 5) - (statusOrder[b.status] || 5);
        if (statusDiff !== 0) return statusDiff;
        const aId = a.rawBank?.id || a.rawBroker?.id || 0;
        const bId = b.rawBank?.id || b.rawBroker?.id || 0;
        return bId - aId;
    });

    // Pagination
    const totalPages = Math.ceil(sortedRows.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const paginatedRows = sortedRows.slice(startIdx, startIdx + pageSize);

    React.useEffect(() => { setCurrentPage(1); }, [viewFilter, searchQuery]);

    // ─── Modal Handlers ───────────────────────────────────────────────────────

    const handleLinkClick = (row: any) => {
        setSelectedRow(row);
        setIsLinkModalOpen(true);
    };

    const handleBreakMatchClick = (row: any) => {
        setSelectedRow(row);
        setIsBreakMatchModalOpen(true);
    };

    const handleCloseModal = () => {
        setIsLinkModalOpen(false);
        setIsSplitModalOpen(false);
        setIsBreakMatchModalOpen(false);
        setSelectedRow(null);
        setSplitParentRow(null);
        setSplitCandidateRows([]);
    };

    // ─── Smart Split ──────────────────────────────────────────────────────────

    const handleSmartSplit = (row: any) => {
        const ref = row.rawBank?.VchID || row.rawBroker?.VchID || row.bankRef || row.brokerRef;
        const date = row.rawBank?.Date || row.rawBroker?.Date || row.bankDate || row.brokerDate;
        const portfolio = row.rawBank?.PortfolioID || row.rawBroker?.PortfolioID || row.bankPortfolio || row.brokerPortfolio;

        if (!ref || ref === '---' || !date || date === '---') {
            alert("Unable to Split: The selected record is missing a Voucher ID or Date.");
            return;
        }

        const relatedCash = cashRecords.filter(r =>
            r.match_status !== 'MATCHED' &&
            r.VchID === ref &&
            r.Date === date &&
            r.PortfolioID === portfolio
        );

        const relatedAp = apRecords.filter(r =>
            r.match_status !== 'MATCHED' &&
            r.VchID === ref &&
            r.Date === date &&
            r.PortfolioID === portfolio
        );

        let parent = null;
        let candidates: any[] = [];

        if (relatedCash.length === 1 && relatedAp.length === 1) {
            alert("These records look like a direct match. Please use the 'Link' button instead of Split.");
            return;
        }

        if (relatedCash.length === 1 && relatedAp.length >= 1) {
            // 1 Cash vs N AP → Cash is Parent (mapped as rawBank)
            parent = {
                ...relatedCash[0],
                bankRef: relatedCash[0].VchID,
                bankDate: relatedCash[0].Date,
                bankPortfolio: relatedCash[0].PortfolioID,
                rawBank: relatedCash[0]
            };
            candidates = relatedAp.map(ap => ({
                brokerRef: ap.VchID,
                brokerDate: ap.Date,
                brokerPortfolio: ap.PortfolioID,
                // Display Debit as negative
                brokerNet: ap.Debit ? `-${ap.Debit}` : (ap.Credit ? `+${ap.Credit}` : '0'),
                rawBroker: ap
            }));
        } else if (relatedAp.length === 1 && relatedCash.length >= 1) {
            // 1 AP vs N Cash → AP is Parent (mapped as rawBroker)
            parent = {
                ...relatedAp[0],
                brokerRef: relatedAp[0].VchID,
                brokerDate: relatedAp[0].Date,
                brokerPortfolio: relatedAp[0].PortfolioID,
                rawBroker: relatedAp[0]
            };
            candidates = relatedCash.map(c => ({
                bankRef: c.VchID,
                bankDate: c.Date,
                bankPortfolio: c.PortfolioID,
                bankAmount: c.Debit ? `-${c.Debit}` : (c.Credit ? `+${c.Credit}` : '0'),
                rawBank: c
            }));
        } else {
            if (relatedCash.length === 0 && relatedAp.length === 0) {
                alert("No unmatched records were found for this selection.");
            } else {
                alert(`Multiple potential matches found (${relatedCash.length} Cash and ${relatedAp.length} AP). Please use Link for direct matches.`);
            }
            return;
        }

        setSplitParentRow(parent);
        setSplitCandidateRows(candidates);
        setIsSplitModalOpen(true);
    };

    const handleConfirmSplitMatch = async (parentRow: any, selectedCandidates: any[]) => {
        if (!processSplitMatch(parentRow, selectedCandidates)) {
            alert("We encountered an issue while processing the split match. Please try again.");
        }
    };

    const processSplitMatch = async (parent: any, candidates: any[]) => {
        if (!batchId) return false;

        const parentIsCash = !!parent.rawBank;

        const realCandidates = candidates.filter(c => !c.isManual);
        const manualCandidates = candidates.filter(c => c.isManual);

        const cashIds = parentIsCash
            ? [parent.rawBank.id]
            : realCandidates.map(c => c.rawBank?.id).filter(Boolean);

        const apIds = parentIsCash
            ? realCandidates.map(c => c.rawBroker?.id).filter(Boolean)
            : [parent.rawBroker.id];

        const manualComponents = manualCandidates.map(m => ({
            ref: m.description || '',
            amount: m.amount || 0,
        }));

        const payload = {
            batch_id: batchId,
            cash_entry_ids: cashIds,
            ap_entry_ids: apIds,
            note: "Smart Split Match",
            manual_components: manualComponents.length > 0 ? manualComponents : undefined,
            canonical_reference: `MAN-SPLIT-${Date.now()}`,
            parent_side: parentIsCash ? "cash" : "ap"
        };

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/api/v1/cap-recon/manual-match`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                handleCloseModal();
                window.location.reload();
                return true;
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.detail || "Could not complete the split match."}`);
                return false;
            }
        } catch (e) {
            alert("Unable to connect to the server.");
            return false;
        }
    };

    // ─── Link Confirm ─────────────────────────────────────────────────────────

    const handleConfirmLink = async (note?: string, cashRef?: string, apRef?: string) => {
        if (!selectedRow || !batchId) return;

        const c = selectedRow.rawBank;
        const a = selectedRow.rawBroker;

        if (!c || !a) {
            alert("Unable to link: One side of the transaction is missing.");
            return;
        }

        // Date tolerance
        const cashDate = new Date(c.Date);
        const apDate = new Date(a.Date);
        const dateDiff = Math.abs((cashDate.getTime() - apDate.getTime()) / (1000 * 60 * 60 * 24));
        if (dateDiff > dateWindowDays) {
            alert(`Dates must be within ${dateWindowDays} days: Cash (${c.Date}) vs AP (${a.Date}). Difference: ${dateDiff.toFixed(1)} days.`);
            return;
        }

        // Portfolio match
        if (c.PortfolioID !== a.PortfolioID) {
            alert(`Portfolios do not match: Cash (${c.PortfolioID}) vs AP (${a.PortfolioID}).`);
            return;
        }

        // Amount tolerance
        const cashAmt = Math.abs(parseFloat(c.Credit || 0) - parseFloat(c.Debit || 0));
        const apAmt = Math.abs(parseFloat(a.Credit || 0) - parseFloat(a.Debit || 0));
        if (Math.abs(cashAmt - apAmt) > toleranceAmount) {
            alert(`Amounts must be within ₹${toleranceAmount} tolerance: Cash (${cashAmt.toFixed(2)}) vs AP (${apAmt.toFixed(2)}). Difference: ₹${Math.abs(cashAmt - apAmt).toFixed(2)}`);
            return;
        }

        const payload = {
            batch_id: batchId,
            cash_entry_ids: [c.id],
            ap_entry_ids: [a.id],
            note,
            canonical_reference: `MAN-LINK-${Date.now()}`
        };

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/api/v1/cap-recon/manual-match`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                handleCloseModal();
                window.location.reload();
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.detail || "Could not link records."}`);
            }
        } catch (e) {
            alert("Unable to connect to the server.");
        }
    };

    // ─── Dissolve ─────────────────────────────────────────────────────────────

    const handleDissolveMatch = async (row: any) => {
        if (!batchId) return;
        const confirmDissolve = confirm("Are you sure you want to dissolve this match? This will undo the split.");
        if (!confirmDissolve) return;

        const matchId = row.rawBank?.match_id || row.rawBroker?.match_id;
        if (!matchId) {
            alert("Could not find the match identifier. Please refresh and try again.");
            return;
        }

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/api/v1/cap-recon/match/dissolve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ batch_id: batchId, match_id: matchId })
            });
            if (res.ok) {
                window.location.reload();
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.detail || "Could not dissolve the match."}`);
            }
        } catch (e) {
            alert("Unable to connect to the server.");
        }
    };

    // ─── Break ────────────────────────────────────────────────────────────────

    const handleConfirmBreakMatch = async (reason: string) => {
        if (!batchId || !selectedRow) return;
        const matchId = selectedRow.rawBank?.match_id || selectedRow.rawBroker?.match_id;
        if (!matchId) return;

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/api/v1/cap-recon/match/break`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ batch_id: batchId, match_id: matchId, reason })
            });
            if (res.ok) {
                handleCloseModal();
                window.location.reload();
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.detail || "Could not break the match."}`);
            }
        } catch (e) {
            alert("Unable to connect to the server.");
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Top Bar — Position Recon style */}
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div className="flex gap-2 flex-wrap">
                    {(['ALL', 'MATCHED', 'UNMATCHED', 'EXCEPTION'] as const).map((tab) => {
                        const tabCounts: Record<string, number> = {
                            ALL: allRows.length,
                            MATCHED: allRows.filter(r => ['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH'].includes(r.status)).length,
                            UNMATCHED: allRows.filter(r => !['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH', 'EXCEPTION'].includes(r.status)).length,
                            EXCEPTION: allRows.filter(r => r.status === 'EXCEPTION').length,
                        };
                        const inactiveC: Record<string, string> = {
                            ALL: 'bg-slate-100 text-slate-700 border-slate-200',
                            MATCHED: 'bg-blue-50 text-blue-700 border-blue-200',
                            UNMATCHED: 'bg-red-50 text-red-700 border-red-200',
                            EXCEPTION: 'bg-amber-50 text-amber-700 border-amber-200',
                        };
                        const activeC: Record<string, string> = {
                            ALL: 'bg-slate-700 text-white border-slate-700',
                            MATCHED: 'bg-blue-700 text-white border-blue-700',
                            UNMATCHED: 'bg-red-600 text-white border-red-600',
                            EXCEPTION: 'bg-amber-500 text-white border-amber-600',
                        };
                        return (
                            <button key={tab} onClick={() => { setViewFilter(tab); setCurrentPage(1); }}
                                className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${viewFilter === tab ? activeC[tab] : inactiveC[tab]}`}>
                                {tab === 'ALL' ? 'All' : tab === 'MATCHED' ? 'Matched' : tab === 'UNMATCHED' ? 'Unmatched' : 'Exceptions'}
                                <span className="ml-1.5 opacity-75">({tabCounts[tab]})</span>
                            </button>
                        );
                    })}
                </div>
                <div className="flex items-center gap-2">
                    <div className="relative">
                        <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        <input type="text" placeholder="Search Portfolio ID…" value={searchQuery}
                            onChange={e => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                            className="pl-8 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-56" />
                    </div>
                    <button onClick={() => {
                        if (onResetFiles) onResetFiles();
                        setIsUploadModalOpen(true);
                    }}
                        className="flex items-center gap-1.5 bg-[#1e3b8b] hover:bg-[#1a337a] text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        Upload Files
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-hidden flex flex-col min-h-0">
                <div className="flex-1 overflow-auto bg-white rounded-xl border border-slate-200 shadow-sm">
                    <table className="w-full text-left border-collapse text-xs table-fixed">
                        <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                            <tr>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold">Portfolio ID</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold">Date</th>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold">Voucher ID</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold text-right border-r border-slate-200">Cash Amt</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold">Date</th>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold">Voucher ID</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold text-right">AP Amt</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold text-center">Status</th>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold">Reason</th>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {paginatedRows.length === 0 ? (
                                <tr><td colSpan={10} className="text-center text-slate-400 py-20 text-sm italic">No records to display.</td></tr>
                            ) : (
                                paginatedRows.map((row, idx) => (
                                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                                        <td className="px-3 py-2.5 font-mono text-slate-700 truncate border-r border-slate-100" title={row.bankPortfolio !== '---' ? row.bankPortfolio : row.brokerPortfolio}>{row.bankPortfolio !== '---' ? row.bankPortfolio : row.brokerPortfolio}</td>

                                        <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap truncate" title={row.bankDate}>{row.bankDate}</td>
                                        <td className="px-3 py-2.5 text-slate-600 truncate" title={row.bankRef}>{row.bankRef}</td>
                                        <td className={`px-3 py-2.5 font-mono text-right border-r border-slate-100 ${row.bankAmount === '---' ? 'text-slate-400' : row.bankAmount.startsWith('-') ? 'text-red-600' : 'text-emerald-600'}`}>{row.bankAmount}</td>
                                        <td className="px-3 py-2.5 text-slate-500 whitespace-nowrap truncate" title={row.brokerDate}>{row.brokerDate}</td>
                                        <td className="px-3 py-2.5 text-slate-500 truncate" title={row.brokerRef}>{row.brokerRef}</td>
                                        <td className={`px-3 py-2.5 font-mono text-right ${row.brokerNet === '---' ? 'text-slate-400' : row.brokerNet.startsWith('-') ? 'text-red-600' : 'text-emerald-600'}`}>{row.brokerNet}</td>

                                        <td className="px-3 py-2.5 text-center">
                                            <span className={`inline-flex items-center justify-center px-2 py-1 rounded-lg border text-[10px] font-semibold whitespace-nowrap ${row.status === 'AUTO_MATCH' || row.status === 'MATCHED' ? 'bg-blue-50 text-blue-700 border-blue-200' : row.status === 'MANUAL_MATCH' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : row.status === 'EXCEPTION' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
                                                {row.status === 'AUTO_MATCH' || row.status === 'MATCHED' ? 'Auto Match' : row.status === 'MANUAL_MATCH' ? 'Manual Match' : row.status === 'EXCEPTION' ? 'Exception' : 'Unmatched'}
                                            </span>
                                        </td>
                                        <td className="px-3 py-2.5 text-slate-600 text-xs">
                                            <span className="whitespace-normal leading-snug">{row.reason || '—'}</span>
                                        </td>

                                        <td className="px-3 py-2.5 text-center">
                                            <div className="flex flex-col items-center gap-1.5">
                                                {!['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH'].includes(row.status) ? (
                                                    <>
                                                        <button onClick={() => handleLinkClick(row)} className="w-16 px-3 py-1.5 rounded-lg text-[10px] font-semibold bg-[#0891b2] hover:bg-[#06b6d4] text-white transition-colors">Link</button>
                                                        <button onClick={() => handleSmartSplit(row)} className="w-16 px-3 py-1.5 rounded-lg text-[10px] font-semibold bg-[#1e40ae] hover:bg-[#2563eb] text-white transition-colors">Split</button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <button onClick={() => handleBreakMatchClick(row)} className="w-16 px-3 py-1.5 rounded-lg text-[10px] font-semibold bg-amber-500 hover:bg-amber-600 text-white transition-colors">Break</button>
                                                        {(row.rawBank?.match_action === 'MANUAL_SPLIT' || row.rawBroker?.match_action === 'MANUAL_SPLIT') && (
                                                            <button onClick={() => handleDissolveMatch(row)} className="w-16 px-3 py-1.5 rounded-lg text-[10px] font-semibold bg-red-600 hover:bg-red-700 text-white transition-colors">Dissolve</button>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                <Pagination
                    currentPage={currentPage}
                    totalPages={totalPages}
                    pageSize={pageSize}
                    totalItems={sortedRows.length}
                    onPageChange={setCurrentPage}
                    onPageSizeChange={(size) => {
                        setPageSize(size);
                        setCurrentPage(1);
                    }}
                />
            </div>

            {/* Reason Detail Modal */}
            {isReasonModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="bg-white rounded-lg shadow-2xl w-full max-w-md mx-4 overflow-hidden">
                        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4 flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-white">Reason Details</h3>
                            <button onClick={() => setIsReasonModalOpen(false)} className="text-white/80 hover:text-white transition-colors">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="p-6">
                            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">
                                    {selectedReason || 'No reason provided'}
                                </p>
                            </div>
                        </div>
                        <div className="bg-gray-50 px-6 py-4 flex justify-end border-t border-gray-200">
                            <button onClick={() => setIsReasonModalOpen(false)} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors shadow-sm">
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Link Modal — Cash/AP labels override Bank/Broker defaults */}
            <LinkTransactionModal
                isOpen={isLinkModalOpen}
                onClose={handleCloseModal}
                onConfirm={handleConfirmLink}
                data={selectedRow}
                leftLabel="Cash Entry"
                rightLabel="AP Entry"
                refFieldLabel="Voucher ID"
                notePlaceholder="Required: voucher id mismatch, manual adjustment required"
                toleranceAmount={toleranceAmount}
                dateWindowDays={dateWindowDays}
            />

            {/* Split Modal — Cash Ledger / Amount Payable labels */}
            <SplitTransactionModal
                isOpen={isSplitModalOpen}
                onClose={handleCloseModal}
                onConfirm={handleConfirmSplitMatch}
                parentRow={splitParentRow}
                candidateRows={splitCandidateRows}
                parentTypeName={splitParentRow?.rawBank ? "Cash Ledger" : "Amount Payable"}
                candidateTypeName={splitParentRow?.rawBank ? "Amount Payable" : "Cash Ledger"}
                refColumnLabel="Voucher ID"
            />

            {/* Break Modal */}
            <BreakMatchModal
                isOpen={isBreakMatchModalOpen}
                onClose={handleCloseModal}
                onConfirm={handleConfirmBreakMatch}
                data={selectedRow}
            />

            {/* Upload Modal */}
            <CashARAPUploadModal
                isOpen={isUploadModalOpen}
                onClose={() => setIsUploadModalOpen(false)}
                onCashLedgerUpload={onCashUpload}
                onARUpload={() => { }}
                onAPUpload={onApUpload}
                onAutoMatch={handleAutoMatchWrapper}
                isUploading={isUploading}
                isProcessing={isProcessing}
                showAp={true}
                showAr={false}
                hasCashFile={hasCashFile}
                hasArFile={false}
                hasApFile={hasApFile}
            />
        </div>
    );
}
