"use client";

import React, { useState, useMemo } from "react";
import { API_URL, API_KEY } from "@/lib/config";
import { StockLiqUploadModal } from "./StockLiqUploadModal";
import { Pagination } from "./Pagination";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SmlReconRow {
    match_id: number | null;
    match_uid: string | null;
    portfolio_id: string | null;
    scrip: string | null;
    stock_name: string | null;
    liq_qty_sum: number | null;
    th_debit_qty_sum: number | null;
    status: "MATCHED" | "UNMATCHED" | "EXCEPTION";
    match_kind: string | null;
    match_action: string | null;
    reason: string | null;
    finding_id: number | null;
    liq_entry_ids: string | null;
    th_entry_ids: string | null;
}

interface StockLiquidationReconProps {
    rows: SmlReconRow[];
    batchId: number | null;
    onLiquidationUpload: (file: File) => Promise<void>;
    onHistoryUpload: (file: File) => Promise<void>;
    onAutoMatch: () => Promise<boolean>;
    isProcessing: boolean;
    hasLiquidationFile: boolean;
    hasHistoryFile: boolean;
    isLiquidationUploading: boolean;
    isHistoryUploading: boolean;
    onRefresh: () => Promise<void>;
    onResetFiles?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert raw system reason text into plain English for non-technical users. */
function simplifyReason(raw: string | null): string {
    if (!raw) return "";

    // Auto-match success pattern: SUM(Qty)=X == SUM(Debit_Quantity)=X
    if (/auto\s*match/i.test(raw) && /sum/i.test(raw)) {
        const m = raw.match(/SUM\(Qty\)=([\d.]+)/i);
        if (m) return `Quantities matched automatically (${parseFloat(m[1]).toLocaleString()} units)`;
        return "Quantities matched automatically";
    }

    // Missing debit quantity
    if (/missing.*debit_quantity/i.test(raw) || /debit_quantity.*missing/i.test(raw)) {
        return "No sold quantity found in Transaction History for this stock";
    }

    // Missing qty
    if (/missing.*qty/i.test(raw) || /qty.*missing/i.test(raw)) {
        return "No liquidation quantity found for this stock";
    }

    // Exception – no TH rows
    if (/transaction history.*missing/i.test(raw) || /no.*transaction history/i.test(raw)) {
        return "No matching transaction history records found";
    }

    // No liquidation record
    if (/no.*liquidation/i.test(raw) || /liquidation.*not found/i.test(raw)) {
        return "No liquidation record found for this stock";
    }

    // Quantity mismatch
    if (/sum.*qty.*!= |sum.*debit.*!=/i.test(raw) || /qty.*mismatch/i.test(raw)) {
        return "Liquidation quantity does not match the sold quantity in Transaction History";
    }

    // Manually linked
    if (/linked|resolved/i.test(raw) && !/auto/i.test(raw)) {
        return `Manually resolved — ${raw}`;
    }

    // Broken match
    if (/break|broken/i.test(raw)) {
        return `Match was undone — ${raw}`;
    }

    // Fallback: return as-is but trim SQL-like noise
    return raw.replace(/SUM\([^)]+\)=?/gi, "").replace(/==/g, "equals").trim() || raw;
}

function fmtNum(v: number | null) {
    if (v == null) return <span className="text-gray-300">—</span>;
    return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

// ---------------------------------------------------------------------------
// Status Badge  (matches broker recon style)
// ---------------------------------------------------------------------------

function StatusBadge({ status, matchKind }: { status: string; matchKind?: string | null }) {
    if (status === "MATCHED") {
        if (matchKind === "MANUAL") {
            return (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                    Manual Match
                </span>
            );
        }
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />
                Auto Match
            </span>
        );
    }
    if (status === "EXCEPTION") {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" />
                Exception
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-100 text-red-600 border border-red-200">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block" />
            Unmatched
        </span>
    );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function StockLiquidationRecon({
    rows,
    batchId,
    onLiquidationUpload,
    onHistoryUpload,
    onAutoMatch,
    isProcessing,
    hasLiquidationFile,
    hasHistoryFile,
    isLiquidationUploading,
    isHistoryUploading,
    onRefresh,
    onResetFiles,
}: StockLiquidationReconProps) {
    const [showUpload, setShowUpload] = useState(false);
    const [filterTab, setFilterTab] = useState<"ALL" | "MATCHED" | "UNMATCHED" | "EXCEPTION">("ALL");
    const [searchText, setSearchText] = useState("");
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // Break state
    const [breakKey, setBreakKey] = useState<string | null>(null);
    const [breakTargetRow, setBreakTargetRow] = useState<SmlReconRow | null>(null);
    const [breakReason, setBreakReason] = useState("");
    const [breakError, setBreakError] = useState("");
    const [isBreaking, setIsBreaking] = useState(false);

    // Link state
    const [linkFindingId, setLinkFindingId] = useState<number | null>(null);
    const [linkReason, setLinkReason] = useState("");
    const [linkError, setLinkError] = useState("");
    const [isLinking, setIsLinking] = useState(false);

    // Reset break/link state when new data arrives (e.g. after auto-recon)
    React.useEffect(() => {
        setBreakKey(null);
        setBreakTargetRow(null);
        setBreakReason("");
        setBreakError("");
        setLinkFindingId(null);
        setLinkReason("");
        setLinkError("");
    }, [rows]);

    // ── Counts ───────────────────────────────────────────────────────────────
    const counts = useMemo(() => ({
        ALL: rows.length,
        MATCHED: rows.filter(r => r.status === "MATCHED").length,
        UNMATCHED: rows.filter(r => r.status === "UNMATCHED").length,
        EXCEPTION: rows.filter(r => r.status === "EXCEPTION").length,
    }), [rows]);

    // ── Filtered rows ────────────────────────────────────────────────────────
    const filtered = useMemo(() => {
        let result = rows;
        if (filterTab !== "ALL") result = result.filter(r => r.status === filterTab);
        const q = searchText.trim().toLowerCase();
        if (q) {
            result = result.filter(r =>
                (r.portfolio_id ?? "").toLowerCase().includes(q) ||
                (r.scrip ?? "").toLowerCase().includes(q) ||
                (r.stock_name ?? "").toLowerCase().includes(q)
            );
        }
        return result;
    }, [rows, filterTab, searchText]);

    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const pageRows = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

    const resetPage = () => setCurrentPage(1);

    // ── Auth header ──────────────────────────────────────────────────────────
    const makeHeaders = () => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        return {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };
    };

    // ── Break ────────────────────────────────────────────────────────────────
    const handleBreak = async () => {
        if (!breakReason.trim()) { setBreakError("Please enter a reason."); return; }
        if (!breakTargetRow) return;
        setIsBreaking(true); setBreakError("");
        try {
            const isMatchRow = breakTargetRow.match_id !== null;
            const url = isMatchRow
                ? `${API_URL}/api/v1/sml-recon/match/break`
                : `${API_URL}/api/v1/sml-recon/finding/break`;
            const body = isMatchRow
                ? { match_id: breakTargetRow.match_id, reason: breakReason.trim() }
                : { finding_id: breakTargetRow.finding_id, reason: breakReason.trim() };
            const res = await fetch(url, { method: "POST", headers: makeHeaders(), body: JSON.stringify(body) });
            if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail ?? "Break failed"); }
            setBreakKey(null); setBreakTargetRow(null); setBreakReason(""); setBreakError("");
            await onRefresh();
        } catch (e: any) { setBreakError(e.message ?? "An error occurred"); }
        finally { setIsBreaking(false); }
    };

    // ── Link ─────────────────────────────────────────────────────────────────
    const handleConfirmLink = async () => {
        if (!linkReason.trim()) { setLinkError("Please enter a reason."); return; }
        if (linkFindingId == null) return;
        setIsLinking(true); setLinkError("");
        try {
            const res = await fetch(`${API_URL}/api/v1/sml-recon/finding/link`, {
                method: "POST",
                headers: makeHeaders(),
                body: JSON.stringify({ finding_id: linkFindingId, reason: linkReason.trim() }),
            });
            if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail ?? "Link failed"); }
            setLinkFindingId(null); setLinkReason(""); setLinkError("");
            await onRefresh();
        } catch (e: any) { setLinkError(e.message ?? "An error occurred"); }
        finally { setIsLinking(false); }
    };

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 flex flex-col">

            {/* Upload Modal */}
            {showUpload && (
                <StockLiqUploadModal
                    onClose={() => setShowUpload(false)}
                    onAutoMatch={onAutoMatch}
                    isProcessing={isProcessing}
                    hasLiquidationFile={hasLiquidationFile}
                    hasHistoryFile={hasHistoryFile}
                    onLiquidationUpload={onLiquidationUpload}
                    onHistoryUpload={onHistoryUpload}
                    isLiquidationUploading={isLiquidationUploading}
                    isHistoryUploading={isHistoryUploading}
                />
            )}

            {/* ── Top bar ── */}
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                {/* Filter pill tabs */}
                <div className="flex gap-2 flex-wrap">
                    {(["ALL", "MATCHED", "UNMATCHED", "EXCEPTION"] as const).map((tab) => {
                        const colors: Record<string, string> = {
                            ALL: "bg-slate-100 text-slate-700 border-slate-200",
                            MATCHED: "bg-blue-50 text-blue-700 border-blue-200",
                            UNMATCHED: "bg-red-50 text-red-700 border-red-200",
                            EXCEPTION: "bg-amber-50 text-amber-700 border-amber-200",
                        };
                        const activeColors: Record<string, string> = {
                            ALL: "bg-slate-700 text-white border-slate-700",
                            MATCHED: "bg-blue-700 text-white border-blue-700",
                            UNMATCHED: "bg-red-600 text-white border-red-600",
                            EXCEPTION: "bg-amber-600 text-white border-amber-600",
                        };
                        return (
                            <button
                                key={tab}
                                onClick={() => { setFilterTab(tab); resetPage(); }}
                                className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${filterTab === tab ? activeColors[tab] : colors[tab]}`}
                            >
                                {tab === "ALL" ? "All" : tab === "MATCHED" ? "Matched" : tab === "UNMATCHED" ? "Unmatched" : "Exceptions"}
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
                            value={searchText}
                            onChange={e => { setSearchText(e.target.value); resetPage(); }}
                            placeholder="Search Portfolio, Scrip…"
                            className="pl-8 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-56"
                        />
                    </div>
                    {/* Upload Files button */}
                    <button
                        onClick={() => { onResetFiles?.(); setShowUpload(true); }}
                        className="flex items-center gap-1.5 bg-[#1e3b8b] hover:bg-[#1a337a] text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
                    >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        Upload Files
                    </button>
                </div>
            </div>

            {/* ── Table ── */}
            <div className="flex-1 overflow-auto bg-white rounded-xl border border-slate-200 shadow-sm">
                {rows.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-48 text-gray-400 gap-2">
                        <svg className="w-10 h-10 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6M5 20h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v11a2 2 0 002 2z" />
                        </svg>
                        <p className="text-sm font-semibold">No data yet</p>
                        <p className="text-xs">Upload files and run Auto Recon to get started</p>
                        <button
                            onClick={() => { onResetFiles?.(); setShowUpload(true); }}
                            className="mt-2 px-4 py-2 text-xs font-semibold text-white bg-[#1e3b8b] rounded hover:bg-[#1a337a] transition-colors"
                        >
                            Upload Files
                        </button>
                    </div>
                ) : (
                    <table className="w-full text-left border-collapse text-xs table-fixed">
                        <colgroup>
                            <col className="w-[12%]" />
                            <col className="w-[10%]" />
                            <col className="w-[14%]" />
                            <col className="w-[10%]" />
                            <col className="w-[11%]" />
                            <col className="w-[11%]" />
                            <col className="w-[12%]" />
                            <col className="w-[20%]" />
                        </colgroup>
                        <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                            <tr>
                                <th className="px-3 py-2.5 text-slate-600 font-semibold whitespace-nowrap">Portfolio ID</th>
                                <th className="px-3 py-2.5 text-slate-600 font-semibold whitespace-nowrap">Scrip</th>
                                <th className="px-3 py-2.5 text-slate-600 font-semibold whitespace-nowrap">Stock Name</th>
                                <th className="px-3 py-2.5 text-slate-600 font-semibold text-right whitespace-nowrap">Liq Qty Sum</th>
                                <th className="px-3 py-2.5 text-slate-600 font-semibold text-right whitespace-nowrap">MERO Debit Qty Sum</th>
                                <th className="px-3 py-2.5 text-slate-600 font-semibold text-center whitespace-nowrap">Status</th>
                                <th className="px-3 py-2.5 text-slate-600 font-semibold text-center whitespace-nowrap">Action</th>
                                <th className="px-3 py-2.5 text-slate-600 font-semibold whitespace-nowrap">Reason</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {pageRows.length === 0 ? (
                                <tr>
                                    <td colSpan={8} className="text-center py-10 text-gray-400">No rows match your filters</td>
                                </tr>
                            ) : (
                                pageRows.map((row, idx) => {
                                    const rowKey = row.match_id != null ? `m_${row.match_id}` : `f_${row.finding_id}`;
                                    const displayReason = simplifyReason(row.reason);

                                    return (
                                        <tr key={rowKey} className="hover:bg-slate-50 transition-colors">
                                            {/* Portfolio ID */}
                                            <td className="px-3 py-2.5 font-mono text-slate-700 whitespace-nowrap">
                                                {row.portfolio_id ?? <span className="text-slate-300">—</span>}
                                            </td>

                                            {/* Scrip */}
                                            <td className="px-4 py-3 font-semibold text-gray-900 whitespace-nowrap">
                                                {row.scrip ?? <span className="text-gray-300">—</span>}
                                            </td>

                                            {/* Stock Name */}
                                            <td className="px-4 py-3 text-gray-700 max-w-[160px] truncate" title={row.stock_name ?? ""}>
                                                {row.stock_name ?? <span className="text-gray-300">—</span>}
                                            </td>

                                            {/* Liq Qty Sum */}
                                            <td className="px-4 py-3 text-right font-mono text-gray-700">
                                                {fmtNum(row.liq_qty_sum)}
                                            </td>

                                            {/* TH Debit Qty Sum */}
                                            <td className="px-4 py-3 text-right font-mono text-gray-700">
                                                {fmtNum(row.th_debit_qty_sum)}
                                            </td>

                                            {/* Status */}
                                            <td className="px-4 py-3 text-center">
                                                <StatusBadge status={row.status} matchKind={row.match_kind} />
                                            </td>

                                            {/* Action */}
                                            <td className="px-4 py-3 text-center">
                                                {row.status === "MATCHED" ? (
                                                    breakKey === rowKey ? (
                                                        <div className="flex flex-col gap-1 min-w-[160px] text-left">
                                                            <input
                                                                type="text"
                                                                value={breakReason}
                                                                onChange={e => setBreakReason(e.target.value)}
                                                                placeholder="Enter reason…"
                                                                className="border border-gray-300 rounded px-2 py-1 text-xs w-full focus:outline-none focus:ring-1 focus:ring-red-400"
                                                            />
                                                            {breakError && <p className="text-red-500 text-[10px]">{breakError}</p>}
                                                            <div className="flex gap-1">
                                                                <button
                                                                    onClick={handleBreak}
                                                                    disabled={isBreaking}
                                                                    className="flex-1 bg-red-600 hover:bg-red-700 text-white rounded px-2 py-1 text-[10px] font-bold disabled:opacity-50"
                                                                >
                                                                    {isBreaking ? "…" : "Confirm"}
                                                                </button>
                                                                <button
                                                                    onClick={() => { setBreakKey(null); setBreakTargetRow(null); setBreakReason(""); setBreakError(""); }}
                                                                    className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-600 rounded px-2 py-1 text-[10px] font-bold"
                                                                >
                                                                    Cancel
                                                                </button>
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <button
                                                            onClick={() => { setBreakKey(rowKey); setBreakTargetRow(row); setBreakReason(""); setBreakError(""); }}
                                                            className="text-[11px] font-bold text-red-600 hover:text-white hover:bg-red-600 border border-red-300 px-3 py-1 rounded transition-colors"
                                                        >
                                                            Break
                                                        </button>
                                                    )
                                                ) : (
                                                    linkFindingId === row.finding_id ? (
                                                        <div className="flex flex-col gap-1 min-w-[160px] text-left">
                                                            <input
                                                                type="text"
                                                                value={linkReason}
                                                                onChange={e => setLinkReason(e.target.value)}
                                                                placeholder="Enter reason…"
                                                                className="border border-gray-300 rounded px-2 py-1 text-xs w-full focus:outline-none focus:ring-1 focus:ring-blue-400"
                                                            />
                                                            {linkError && <p className="text-red-500 text-[10px]">{linkError}</p>}
                                                            <div className="flex gap-1">
                                                                <button
                                                                    onClick={handleConfirmLink}
                                                                    disabled={isLinking}
                                                                    className="flex-1 bg-[#1e3b8b] hover:bg-[#1a337a] text-white rounded px-2 py-1 text-[10px] font-bold disabled:opacity-50"
                                                                >
                                                                    {isLinking ? "…" : "Confirm"}
                                                                </button>
                                                                <button
                                                                    onClick={() => { setLinkFindingId(null); setLinkReason(""); setLinkError(""); }}
                                                                    className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-600 rounded px-2 py-1 text-[10px] font-bold"
                                                                >
                                                                    Cancel
                                                                </button>
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <button
                                                            onClick={() => { if (row.finding_id == null) return; setLinkFindingId(row.finding_id); setLinkReason(""); setLinkError(""); }}
                                                            className="text-[11px] font-bold text-[#1e3b8b] hover:text-white hover:bg-[#1e3b8b] border border-blue-300 px-3 py-1 rounded transition-colors"
                                                        >
                                                            Link
                                                        </button>
                                                    )
                                                )}
                                            </td>

                                            {/* Reason — plain English, full text, no truncation */}
                                            <td className="px-4 py-3 text-gray-500 text-[11px] leading-snug whitespace-normal max-w-[220px]">
                                                {displayReason || (row.status === "MATCHED" ? (row.match_kind === "MANUAL" ? "Manual Match" : "Auto Match") : <span className="text-gray-300">—</span>)}
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                )}
            </div>

            {/* ── Pagination ── */}
            {filtered.length > 0 && (
                <Pagination
                    currentPage={currentPage}
                    totalPages={totalPages}
                    pageSize={pageSize}
                    totalItems={filtered.length}
                    onPageChange={setCurrentPage}
                    onPageSizeChange={(size) => { setPageSize(size); setCurrentPage(1); }}
                />
            )}
        </div>
    );
}
