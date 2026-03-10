"use client";

import React, { useState } from 'react';
import { LinkTransactionModal } from './LinkTransactionModal';
import { SplitTransactionModal } from './SplitTransactionModal';
import { BreakMatchModal } from './BreakMatchModal';
import { API_URL, API_KEY } from '@/lib/config';
import { BankBrokerUploadModal } from './BankBrokerUploadModal';
import { Pagination } from './Pagination';



interface BankBrokerNetProps {
    bankRecords?: any[];
    brokerRecords?: any[];
    batchId?: number | null;
    onBankUpload: (file: File) => void;
    onBrokerUpload: (file: File) => void;
    isUploading: boolean;
    isBankUploading?: boolean;
    isBrokerUploading?: boolean;
    onAutoMatch: () => Promise<boolean>;
    isProcessing: boolean;
    hasBankFile: boolean;
    hasBrokerFile: boolean;
    toleranceAmount?: number;
    dateWindowDays?: number;
    onResetFiles?: () => void;
}

export function BankBrokerNet({ bankRecords = [], brokerRecords = [], batchId, onBankUpload, onBrokerUpload, isUploading, isBankUploading, isBrokerUploading, onAutoMatch, isProcessing, hasBankFile, hasBrokerFile, toleranceAmount = 50, dateWindowDays = 2, onResetFiles }: BankBrokerNetProps) {
    const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
    const [isSplitModalOpen, setIsSplitModalOpen] = useState(false);
    const [isBreakMatchModalOpen, setIsBreakMatchModalOpen] = useState(false);
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const [isReasonModalOpen, setIsReasonModalOpen] = useState(false);
    const [selectedReason, setSelectedReason] = useState<string>('');

    const handleAutoMatchWrapper = async () => {
        const success = await onAutoMatch();
        if (success) {
            setIsUploadModalOpen(false);
        }
    };
    // ...
    <BankBrokerUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onBankUpload={onBankUpload}
        onBrokerUpload={onBrokerUpload}
        isUploading={isUploading}
        isBankUploading={isBankUploading}
        isBrokerUploading={isBrokerUploading}
        onAutoMatch={handleAutoMatchWrapper}
        isProcessing={isProcessing}
        hasBankFile={hasBankFile}
        hasBrokerFile={hasBrokerFile}
    />


    const [viewFilter, setViewFilter] = useState<'ALL' | 'MATCHED' | 'EXCEPTION' | 'UNMATCHED'>('ALL');
    const [searchQuery, setSearchQuery] = useState('');

    const [selectedRow, setSelectedRow] = useState<any>(null);

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // ... existing processRows function ...

    // Process Data into Rows
    const processRows = () => {
        const rows: any[] = [];
        const matches = new Map<string, { bank?: any, broker?: any }>();

        // Track consumed IDs to prevent double counting
        const consumedBankIds = new Set<string>();
        const consumedBrokerIds = new Set<string>();

        // 1. Group Strict Matches
        bankRecords.forEach(r => {
            if (r.match_status === 'MATCHED' && r.match_id) {
                if (!matches.has(r.match_id)) matches.set(r.match_id, {});
                matches.get(r.match_id)!.bank = r;
                consumedBankIds.add(r.id || r.Reference);
            }
        });
        brokerRecords.forEach(r => {
            if (r.match_status === 'MATCHED' && r.match_id) {
                if (!matches.has(r.match_id)) matches.set(r.match_id, {});
                matches.get(r.match_id)!.broker = r;
                consumedBrokerIds.add(r.id || r.Reference);
            }
        });

        // 2. Add Matched Rows
        matches.forEach((pair, matchId) => {
            const b = pair.bank || {};
            const br = pair.broker || {};
            // Determine Status
            let status = 'MATCHED';
            const kind = b.match_kind || br.match_kind || 'AUTO';
            if (kind === 'AUTO') status = 'AUTO_MATCH';
            if (kind === 'MANUAL') status = 'MANUAL_MATCH';

            rows.push({
                bankPortfolio: b.PortfolioID || '---',
                bankDate: b.Date || '---',
                bankRef: b.Reference || '---',
                bankAmount: b.Credit ? `+${b.Credit}` : (b.Debit ? `-${b.Debit}` : '0'),
                brokerPortfolio: br.PortfolioID || '---',
                brokerDate: br.Date || '---',
                brokerRef: br.Reference || '---',
                brokerNet: br.Credit ? `+${br.Credit}` : (br.Debit ? `-${br.Debit}` : '0'),
                deltaAmount: '0',
                status: status,
                reason: b.reason || br.reason || '',
                rawBank: b,
                rawBroker: br
            });
        });

        // 3. Soft Match / Exception Grouping (Frontend Logic)
        const unmatchedBank = bankRecords.filter(r => !consumedBankIds.has(r.id || r.Reference));
        const unmatchedBroker = brokerRecords.filter(r => !consumedBrokerIds.has(r.id || r.Reference));

        // Helper to find a soft match in broker list
        const findBrokerMatch = (bankRecord: any) => {
            return unmatchedBroker.find(br => {
                if (consumedBrokerIds.has(br.id || br.Reference)) return false;

                // Criteria 1: Same Reference
                if (bankRecord.Reference && br.Reference &&
                    bankRecord.Reference.trim() === br.Reference.trim() &&
                    bankRecord.Reference !== '---') return true;

                // Criteria 2: Same Amount AND Date
                const bankAmt = bankRecord.Credit || bankRecord.Debit;
                const brokerAmt = br.Credit || br.Debit;

                if (bankRecord.Date && br.Date && bankRecord.Date === br.Date &&
                    bankAmt && brokerAmt && bankAmt == brokerAmt) return true;

                return false;
            });
        };

        unmatchedBank.forEach(b => {
            // For simplicity in list mode, we might disable heuristic pairing or keep it purely for display?
            // Lets keep the heuristic pairing for visual aid.
            const softMatch = findBrokerMatch(b);
            if (softMatch) {
                consumedBankIds.add(b.id || b.Reference);
                consumedBrokerIds.add(softMatch.id || softMatch.Reference);

                const bRef = b.Reference || '---';
                const bDate = b.Date || '---';
                const bAmt = b.Credit || b.Debit || '0.00';

                const brRef = softMatch.Reference || '---';
                const brDate = softMatch.Date || '---';
                const brAmt = softMatch.Credit || softMatch.Debit || '0.00';

                const hasMissingData =
                    bRef === '---' || bDate === '---' || bAmt === '0.00' || !b.PortfolioID ||
                    brRef === '---' || brDate === '---' || brAmt === '0.00' || !softMatch.PortfolioID ||
                    !!b.validation_error || !!softMatch.validation_error;

                rows.push({
                    bankPortfolio: b.PortfolioID || '---',
                    bankDate: bDate,
                    bankRef: bRef,
                    bankAmount: b.Credit ? `+${b.Credit}` : (b.Debit ? `-${b.Debit}` : '0'),
                    brokerPortfolio: softMatch.PortfolioID || '---',
                    brokerDate: brDate,
                    brokerRef: brRef,
                    brokerNet: softMatch.Credit ? `+${softMatch.Credit}` : (softMatch.Debit ? `-${softMatch.Debit}` : '0'),
                    deltaAmount: '0',
                    status: hasMissingData ? 'EXCEPTION' : 'UNMATCHED', // Matched by heuristic but not official
                    reason: b.reason || softMatch.reason || '',
                    rawBank: b,
                    rawBroker: softMatch
                });
            }
        });

        // 4. Add Truly Orphaned Bank
        bankRecords.filter(r => !consumedBankIds.has(r.id || r.Reference)).forEach(r => {
            const hasAmount = (r.Credit && r.Credit !== 0) || (r.Debit && r.Debit !== 0);
            const isException = r.validation_error || !hasAmount || !r.Date || !r.Reference || !r.PortfolioID;
            rows.push({
                bankPortfolio: r.PortfolioID || '---',
                bankDate: r.Date || '---',
                bankRef: r.Reference || '---',
                bankAmount: r.Credit ? `+${r.Credit}` : (r.Debit ? `-${r.Debit}` : '0'),
                brokerPortfolio: '---',
                brokerDate: '---',
                brokerRef: '---',
                brokerNet: '---',
                deltaAmount: r.Credit ? `+${r.Credit}` : `-${r.Debit}`,
                status: isException ? 'EXCEPTION' : (r.match_status || 'UNMATCHED'),
                reason: r.reason || '',
                rawBank: r,
                rawBroker: null
            });
        });

        // 5. Add Truly Orphaned Broker
        brokerRecords.filter(r => !consumedBrokerIds.has(r.id || r.Reference)).forEach(r => {
            const hasAmount = (r.Credit && r.Credit !== 0) || (r.Debit && r.Debit !== 0);
            const isException = r.validation_error || !hasAmount || !r.Date || !r.Reference || !r.PortfolioID;
            rows.push({
                bankPortfolio: '---',
                bankDate: '---',
                bankRef: '---',
                bankAmount: '---',
                brokerPortfolio: r.PortfolioID || '---',
                brokerDate: r.Date || '---',
                brokerRef: r.Reference || '---',
                brokerNet: r.Credit ? `+${r.Credit}` : (r.Debit ? `-${r.Debit}` : '0'),
                deltaAmount: r.Credit ? `+${r.Credit}` : `-${r.Debit}`,
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
        // 1. View Filter
        let matchesView = true;
        if (viewFilter === 'MATCHED') matchesView = ['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH'].includes(r.status);
        if (viewFilter === 'EXCEPTION') matchesView = r.status === 'EXCEPTION';
        if (viewFilter === 'UNMATCHED') matchesView = !['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH', 'EXCEPTION'].includes(r.status);

        // 2. Search Filter (Portfolio ID)
        let matchesSearch = true;
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase().trim();
            const pf = (r.bankPortfolio !== '---' ? r.bankPortfolio : r.brokerPortfolio) || '';
            matchesSearch = pf.toLowerCase().includes(query);
        }

        return matchesView && matchesSearch;
    });

    // Sort: Status Priority (Auto Match -> Manual Match -> Exception -> Unmatched) + ID Descending (newest first)
    const sortedRows = displayRows.sort((a, b) => {
        // Status priority
        const statusOrder: Record<string, number> = { AUTO_MATCH: 1, MANUAL_MATCH: 2, EXCEPTION: 3, UNMATCHED: 4 };
        const statusDiff = (statusOrder[a.status] || 5) - (statusOrder[b.status] || 5);
        if (statusDiff !== 0) return statusDiff;

        // ID descending (newest first within each status group)
        const aId = a.rawBank?.id || a.rawBroker?.id || 0;
        const bId = b.rawBank?.id || b.rawBroker?.id || 0;
        return bId - aId;
    });

    // Pagination
    const totalPages = Math.ceil(sortedRows.length / pageSize);
    const startIdx = (currentPage - 1) * pageSize;
    const paginatedRows = sortedRows.slice(startIdx, startIdx + pageSize);

    // Reset to page 1 when filters change
    React.useEffect(() => {
        setCurrentPage(1);
    }, [viewFilter, searchQuery]);

    const handleLinkClick = (row: any) => {
        setSelectedRow(row);
        setIsLinkModalOpen(true);
    };

    const handleBreakMatchClick = (row: any) => {
        setSelectedRow(row);
        setIsBreakMatchModalOpen(true);
    };

    // Split Logic State
    const [splitParentRow, setSplitParentRow] = useState<any>(null);
    const [splitCandidateRows, setSplitCandidateRows] = useState<any[]>([]);

    const handleSmartSplit = (row: any) => {
        // 1. Identify Search Keys from the clicked row (could be soft-match or orphan)
        // Prefer Raw Data if available
        const ref = row.rawBank?.reference_no || row.rawBroker?.reference_no || row.bankRef || row.brokerRef;
        const date = row.rawBank?.value_date || row.rawBroker?.value_date || row.bankDate || row.brokerDate;
        const portfolio = row.rawBank?.portfolio_id || row.rawBroker?.portfolio_id || row.bankPortfolio || row.brokerPortfolio;

        if (!ref || ref === '---' || !date || date === '---') {
            alert("Unable to Split: The selected record is missing a Reference Number or Date.");
            return;
        }

        // 2. Find ALL Unmatched (or Exception) records with these keys
        const relatedBanks = bankRecords.filter(r =>
            r.match_status !== 'MATCHED' &&
            r.Reference === ref &&
            r.Date === date &&
            r.PortfolioID === portfolio
        );

        const relatedBrokers = brokerRecords.filter(r =>
            r.match_status !== 'MATCHED' &&
            r.Reference === ref &&
            r.Date === date &&
            r.PortfolioID === portfolio
        );

        // 3. Determine Relationship (1-to-N or N-to-1)
        let parent = null;
        let candidates: any[] = [];
        let isBankParent = false;

        if (relatedBanks.length === 1 && relatedBrokers.length === 1) {
            alert("These records look like a direct match. Please use the 'Link' button instead of Split.");
            return;
        }

        if (relatedBanks.length === 1 && relatedBrokers.length >= 1) {
            // 1 Bank vs N Brokers -> Bank is Parent
            // (Even 1-to-1 can be treated as split for explicit confirmation)
            parent = { ...relatedBanks[0], bankRef: relatedBanks[0].Reference, bankDate: relatedBanks[0].Date, bankPortfolio: relatedBanks[0].PortfolioID, rawBank: relatedBanks[0] };
            isBankParent = true;
            candidates = relatedBrokers.map(br => ({
                brokerRef: br.Reference,
                brokerDate: br.Date,
                brokerPortfolio: br.PortfolioID,
                brokerNet: br.Credit ? `+${br.Credit}` : (br.Debit ? `-${br.Debit}` : '0'), // For display helper
                rawBroker: br
            }));

        } else if (relatedBrokers.length === 1 && relatedBanks.length >= 1) {
            // 1 Broker vs N Banks -> Broker is Parent
            parent = { ...relatedBrokers[0], brokerRef: relatedBrokers[0].Reference, brokerDate: relatedBrokers[0].Date, brokerPortfolio: relatedBrokers[0].PortfolioID, rawBroker: relatedBrokers[0] };
            isBankParent = false;
            candidates = relatedBanks.map(bk => ({
                bankRef: bk.Reference,
                bankDate: bk.Date,
                bankPortfolio: bk.PortfolioID,
                bankAmount: bk.Credit ? `+${bk.Credit}` : (bk.Debit ? `-${bk.Debit}` : '0'),
                rawBank: bk
            }));

        } else {
            // Ambiguous (N-to-N or 0-to-0)
            if (relatedBanks.length === 0 && relatedBrokers.length === 0) {
                alert("No unmatched records were found for this selection.");
            } else {
                alert(`Multiple potential matches found (Found ${relatedBanks.length} Banks and ${relatedBrokers.length} Brokers). Please manually select the correct records to split.`);
            }
            return;
        }

        // 4. Open Modal
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

        const parentIsBank = !!parent.rawBank;

        // Separate real DB records from manually-added entries
        const realCandidates = candidates.filter(c => !c.isManual);
        const manualCandidates = candidates.filter(c => c.isManual);

        const bankIds = parentIsBank
            ? [parent.rawBank.id]
            : realCandidates.map(c => c.rawBank?.id).filter(Boolean);

        const brokerIds = parentIsBank
            ? realCandidates.map(c => c.rawBroker?.id).filter(Boolean)
            : [parent.rawBroker.id];

        const manualComponents = manualCandidates.map(m => ({
            ref: m.description || '',
            amount: m.amount || 0,
        }));

        const payload = {
            batch_id: batchId,
            bank_entry_ids: bankIds,
            broker_entry_ids: brokerIds,
            note: "Smart Split Match",
            manual_components: manualComponents.length > 0 ? manualComponents : undefined,
            canonical_reference: `MAN-SPLIT-${Date.now()}`,
            parent_side: parentIsBank ? "bank" : "broker"
        };

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/api/v1/recon/manual-match`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                console.log("Split Match Success");
                handleCloseModal();
                window.location.reload();
                return true;
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.detail || "We could not complete the split match. Please try again."}`);
                return false;
            }
        } catch (e) {
            console.error(e);
            alert("Unable to connect to the server. Please check your internet connection.");
            return false;
        }
    };

    const handleCloseModal = () => {
        setIsLinkModalOpen(false);
        setIsSplitModalOpen(false);
        setIsBreakMatchModalOpen(false);

        setSelectedRow(null);
        setSplitParentRow(null);
        setSplitCandidateRows([]);
    };

    const handleConfirmLink = async (note?: string, bankRef?: string, brokerRef?: string) => {
        if (!selectedRow || !batchId) return;

        const b = selectedRow.rawBank;
        const br = selectedRow.rawBroker;

        if (!b || !br) {
            alert("Unable to link: One side of the transaction is missing.");
            return;
        }

        // Validation with tolerances
        // 1. Date Match (with date window tolerance)
        const bankDate = new Date(b.Date);
        const brokerDate = new Date(br.Date);
        const dateDiff = Math.abs((bankDate.getTime() - brokerDate.getTime()) / (1000 * 60 * 60 * 24));

        if (dateDiff > dateWindowDays) {
            alert(`Dates must be within ${dateWindowDays} days: Bank (${b.Date}) vs Broker (${br.Date}). Date difference: ${dateDiff.toFixed(1)} days.`);
            return;
        }

        // 2. Portfolio Match
        if (b.PortfolioID !== br.PortfolioID) {
            alert(`Portfolios do not match: Bank (${b.PortfolioID}) vs Broker (${br.PortfolioID}). You can only link records from the same portfolio.`);
            return;
        }

        // 3. Amount Match (with tolerance)
        const bankAmt = Math.abs(parseFloat(b.Credit || 0) - parseFloat(b.Debit || 0));
        const brokerAmt = Math.abs(parseFloat(br.Credit || 0) - parseFloat(br.Debit || 0));

        if (Math.abs(bankAmt - brokerAmt) > toleranceAmount) {
            alert(`Amounts must be within ₹${toleranceAmount} tolerance: Bank (${bankAmt.toFixed(2)}) vs Broker (${brokerAmt.toFixed(2)}). Difference: ₹${Math.abs(bankAmt - brokerAmt).toFixed(2)}`);
            return;
        }

        const payload = {
            batch_id: batchId,
            bank_entry_ids: [b.id],
            broker_entry_ids: [br.id],
            note: note,
            update_bank_ref: bankRef !== b.Reference ? bankRef : undefined,
            update_broker_ref: brokerRef !== br.Reference ? brokerRef : undefined,
            canonical_reference: `MAN-LINK-${Date.now()}`
        };

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/api/v1/recon/manual-match`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                console.log("Link Success");
                handleCloseModal();
                window.location.reload();
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.detail || "We could not link the records. Please try again."}`);
            }
        } catch (e) {
            console.error(e);
            alert("Unable to connect to the server. Please check your internet connection.");
        }
    };

    const handleDissolveMatch = async (row: any) => {
        if (!batchId) return;
        const confirmDissolve = confirm("Are you sure you want to dissolve this match? This will undo the split.");
        if (!confirmDissolve) return;

        // We need the match_id.
        // The row structure has `match_id` if matched?
        // Let's check processRows... yes, it groups by match_id but doesn't explicitly expose it on the row object?
        // Ah, `matches` map keys are match_id, but we need to put it on row.
        // Let's assume we need to update processRows to include match_id, OR check rawBank/rawBroker match_id.

        const matchId = row.rawBank?.match_id || row.rawBroker?.match_id;

        if (!matchId) {
            alert("We couldn't find the unique identifier for this record. Please refresh the page and try again.");
            return;
        }

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/api/v1/recon/dissolve-match`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    batch_id: batchId,
                    match_id: matchId
                })
            });

            if (res.ok) {
                console.log("Dissolve Success");
                window.location.reload();
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.detail || "We could not dissolve the match. Please try again."}`);
            }
        } catch (e) {
            console.error(e);
            alert("Unable to connect to the server. Please check your internet connection.");
        }
    };

    const handleConfirmBreakMatch = async (reason: string) => {
        if (!batchId || !selectedRow) return;

        const matchId = selectedRow.rawBank?.match_id || selectedRow.rawBroker?.match_id;

        if (!matchId) {
            alert("We couldn't find the unique identifier for this record. Please refresh the page and try again.");
            return;
        }

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/api/v1/recon/break-match`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    batch_id: batchId,
                    match_id: matchId,
                    reason: reason
                })
            });

            if (res.ok) {
                console.log("Break Match Success");
                handleCloseModal();
                window.location.reload();
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.detail || "We could not break the match. Please try again."}`);
            }
        } catch (e) {
            console.error(e);
            alert("Unable to connect to the server. Please check your internet connection.");
        }
    }

    const handleApplySplit = () => {
        handleCloseModal();
    };

    // ... return ...

    return (
        <div className="flex flex-col h-full">
            {/* Top Bar — matches Position Recon */}
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                {/* Pill Filter Tabs with counts */}
                <div className="flex gap-2 flex-wrap">
                    {(['ALL', 'MATCHED', 'UNMATCHED', 'EXCEPTION'] as const).map((tab) => {
                        const counts: Record<string, number> = {
                            ALL: sortedRows.length || allRows.length,
                            MATCHED: allRows.filter(r => ['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH'].includes(r.status)).length,
                            UNMATCHED: allRows.filter(r => !['MATCHED', 'AUTO_MATCH', 'MANUAL_MATCH', 'EXCEPTION'].includes(r.status)).length,
                            EXCEPTION: allRows.filter(r => r.status === 'EXCEPTION').length,
                        };
                        const inactive: Record<string, string> = {
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
                            <button
                                key={tab}
                                onClick={() => { setViewFilter(tab); setCurrentPage(1); }}
                                className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${viewFilter === tab ? activeC[tab] : inactive[tab]}`}
                            >
                                {tab === 'ALL' ? 'All' : tab === 'MATCHED' ? 'Matched' : tab === 'UNMATCHED' ? 'Unmatched' : 'Exceptions'}
                                <span className="ml-1.5 opacity-75">({counts[tab]})</span>
                            </button>
                        );
                    })}
                </div>

                <div className="flex items-center gap-2">
                    {/* Search */}
                    <div className="relative">
                        <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        <input
                            type="text"
                            placeholder="Search Portfolio ID…"
                            value={searchQuery}
                            onChange={e => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                            className="pl-8 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-56"
                        />
                    </div>
                    {/* Upload Button */}
                    <button
                        onClick={() => {
                            if (onResetFiles) onResetFiles();
                            setIsUploadModalOpen(true);
                        }}
                        className="flex items-center gap-1.5 bg-[#1e3b8b] hover:bg-[#1a337a] text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
                    >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        Upload Files
                    </button>
                </div>
            </div>

            {/* Data Table */}
            <div className="flex-1 overflow-hidden flex flex-col min-h-0">
                <div className="flex-1 overflow-auto bg-white rounded-xl border border-slate-200 shadow-sm">
                    <table className="w-full text-left border-collapse text-xs table-fixed">
                        <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                            <tr>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold">Portfolio ID</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold">Date</th>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold">Reference</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold text-right border-r border-slate-200">Bank</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold">Date</th>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold">Reference</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold text-right">Broker</th>
                                <th className="w-[9%] px-3 py-2.5 text-slate-600 font-semibold text-center">Status</th>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold">Reason</th>
                                <th className="w-[11%] px-3 py-2.5 text-slate-600 font-semibold text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {paginatedRows.length === 0 ? (
                                <tr>
                                    <td colSpan={10} className="text-center text-slate-400 py-20 text-sm italic">
                                        No records to display.
                                    </td>
                                </tr>
                            ) : (
                                paginatedRows.map((row, idx) => (
                                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                                        <td className="px-3 py-2.5 font-mono text-slate-700 truncate border-r border-slate-100" title={row.bankPortfolio !== '---' ? row.bankPortfolio : row.brokerPortfolio}>
                                            {row.bankPortfolio !== '---' ? row.bankPortfolio : row.brokerPortfolio}
                                        </td>
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
                                                        {(row.rawBank?.canonical_reference?.includes('MAN-SPLIT') || row.rawBroker?.canonical_reference?.includes('MAN-SPLIT')) && (
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
                    onPageSizeChange={(size) => { setPageSize(size); setCurrentPage(1); }}
                />
            </div>

            {/* Reason Modal */}
            {isReasonModalOpen && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full">
                        <h3 className="text-lg font-semibold mb-4">Full Reason</h3>
                        <p className="text-sm text-gray-700 mb-4 whitespace-pre-wrap">{selectedReason}</p>
                        <button
                            onClick={() => setIsReasonModalOpen(false)}
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors"
                        >
                            Close
                        </button>
                    </div>
                </div>
            )}

            {/* Link Modal (Legacy/Direct) */}
            <LinkTransactionModal
                isOpen={isLinkModalOpen}
                onClose={handleCloseModal}
                onConfirm={handleConfirmLink}
                data={selectedRow}
                toleranceAmount={toleranceAmount}
                dateWindowDays={dateWindowDays}
            />

            {/* Split Modal (New UI) */}
            <SplitTransactionModal
                isOpen={isSplitModalOpen}
                onClose={handleCloseModal}
                onConfirm={handleConfirmSplitMatch}
                parentRow={splitParentRow}
                candidateRows={splitCandidateRows}
            />

            <BreakMatchModal
                isOpen={isBreakMatchModalOpen}
                onClose={handleCloseModal}
                onConfirm={handleConfirmBreakMatch}
                data={selectedRow}
            />

            <BankBrokerUploadModal
                isOpen={isUploadModalOpen}
                onClose={() => setIsUploadModalOpen(false)}
                onBankUpload={onBankUpload}
                onBrokerUpload={onBrokerUpload}
                isUploading={isUploading}
                isBankUploading={isBankUploading}
                isBrokerUploading={isBrokerUploading}
                onAutoMatch={handleAutoMatchWrapper}
                isProcessing={isProcessing}
                hasBankFile={hasBankFile}
                hasBrokerFile={hasBrokerFile}
            />

            {/* Reason Detail Modal */}
            {isReasonModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="bg-white rounded-lg shadow-2xl w-full max-w-md mx-4 overflow-hidden">
                        {/* Header */}
                        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4 flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-white">Reason Details</h3>
                            <button
                                onClick={() => setIsReasonModalOpen(false)}
                                className="text-white/80 hover:text-white transition-colors"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        {/* Content */}
                        <div className="p-6">
                            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">
                                    {selectedReason || 'No reason provided'}
                                </p>
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="bg-gray-50 px-6 py-4 flex justify-end border-t border-gray-200">
                            <button
                                onClick={() => setIsReasonModalOpen(false)}
                                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors shadow-sm"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
}
