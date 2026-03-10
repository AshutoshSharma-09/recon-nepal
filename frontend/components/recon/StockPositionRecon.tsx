"use client";

import React, { useState, useMemo } from "react";
import { API_URL, API_KEY } from "@/lib/config";
import { StockUploadModal } from "./StockUploadModal";
import { Pagination } from "./Pagination";

// ─── Types ────────────────────────────────────────────────────────────────────

interface SrRow {
    match_id: number | null;
    match_uid: string | null;
    finding_id: number | null;
    portfolio_id: string;
    symbol: string | null;
    scrip: string | null;
    stock_name: string | null;
    ss_qty: number | null;
    th_balance: number | null;
    status: string; // MATCHED | UNMATCHED | EXCEPTION
    match_kind: string | null;
    match_action: string | null;
    reason: string | null;
    ss_entry_id: number | null;
    th_entry_id: number | null;
}

interface StockPositionReconProps {
    rows: SrRow[];
    batchId: number | null;
    onSummaryUpload: (file: File) => Promise<void>;
    onHistoryUpload: (file: File) => Promise<void>;
    onAutoMatch: () => Promise<boolean>;
    isProcessing: boolean;
    hasSummaryFile: boolean;
    hasHistoryFile: boolean;
    isSummaryUploading: boolean;
    isHistoryUploading: boolean;
    onRefresh: () => void;
    onResetFiles?: () => void;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Convert raw system reason text into plain English for non-technical users. */
function simplifyReason(raw: string | null): string {
    if (!raw) return "";

    // Auto-match success pattern: ss_qty=X == th_balance=X
    if (/auto\s*match/i.test(raw) && /qty/i.test(raw)) {
        return "Quantities matched automatically";
    }

    // Missing balance/qty
    if (/missing.*balance/i.test(raw) || /balance.*missing/i.test(raw)) {
        return "No balance found in Transaction History for this stock";
    }
    if (/missing.*qty/i.test(raw) || /qty.*missing/i.test(raw)) {
        return "No quantity found in Statement of Holding for this stock";
    }

    // Exception – no TH rows
    if (/transaction history.*missing/i.test(raw) || /no.*transaction history/i.test(raw)) {
        return "No matching transaction history records found";
    }

    // Quantity mismatch
    if (/qty.*!= |balance.*!=/i.test(raw) || /mismatch/i.test(raw)) {
        return "Quantity mismatch between Statement of Holding and Transaction History Balance";
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
    // UNMATCHED
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-100 text-red-600 border border-red-200">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block" />
            Unmatched
        </span>
    );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function StockPositionRecon({
    rows,
    batchId,
    onSummaryUpload,
    onHistoryUpload,
    onAutoMatch,
    isProcessing,
    hasSummaryFile,
    hasHistoryFile,
    isSummaryUploading,
    isHistoryUploading,
    onRefresh,
    onResetFiles,
}: StockPositionReconProps) {
    const [filterTab, setFilterTab] = useState<"ALL" | "MATCHED" | "UNMATCHED" | "EXCEPTION">("ALL");
    const [searchText, setSearchText] = useState("");
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // Break state — string key: "m_{match_id}" for matches, "f_{finding_id}" for resolved findings
    const [breakKey, setBreakKey] = useState<string | null>(null);
    const [breakTargetRow, setBreakTargetRow] = useState<SrRow | null>(null);
    const [breakReason, setBreakReason] = useState("");
    const [isBreaking, setIsBreaking] = useState(false);
    const [breakError, setBreakError] = useState("");

    // Link state (inline, mirrors Break)
    const [linkFindingId, setLinkFindingId] = useState<number | null>(null);
    const [linkRow, setLinkRow] = useState<SrRow | null>(null);
    const [linkReason, setLinkReason] = useState("");
    const [isLinking, setIsLinking] = useState(false);
    const [linkError, setLinkError] = useState("");

    // Reset break/link UI when new data arrives (e.g. after auto-recon)
    React.useEffect(() => {
        setBreakKey(null);
        setBreakTargetRow(null);
        setBreakReason("");
        setBreakError("");
        setLinkFindingId(null);
        setLinkRow(null);
        setLinkReason("");
        setLinkError("");
    }, [rows]);

    // ── Summary counts ─────────────────────────────────────────────────────────
    const counts = useMemo(() => ({
        ALL: rows.length,
        MATCHED: rows.filter(r => r.status === "MATCHED").length,
        UNMATCHED: rows.filter(r => r.status === "UNMATCHED").length,
        EXCEPTION: rows.filter(r => r.status === "EXCEPTION").length,
    }), [rows]);

    // ── Filtered rows ─────────────────────────────────────────────────────────
    const filtered = useMemo(() => {
        let result = rows;
        if (filterTab !== "ALL") {
            result = result.filter(r => r.status === filterTab);
        }
        const q = searchText.trim().toLowerCase();
        if (q) {
            result = result.filter(r =>
                (r.portfolio_id || "").toLowerCase().includes(q) ||
                (r.symbol || "").toLowerCase().includes(q) ||
                (r.scrip || "").toLowerCase().includes(q) ||
                (r.stock_name || "").toLowerCase().includes(q)
            );
        }
        return result;
    }, [rows, filterTab, searchText]);

    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const paged = filtered.slice((page - 1) * pageSize, page * pageSize);

    // ── Break action ───────────────────────────────────────────────────────────
    const handleBreak = async () => {
        if (!breakReason.trim()) { setBreakError("A reason is required."); return; }
        if (!breakKey || !breakTargetRow) return;
        setIsBreaking(true);
        setBreakError("");
        try {
            const token = localStorage.getItem("token");
            let url: string;
            let body: object;
            if (breakKey.startsWith("m_") && breakTargetRow.match_id) {
                // Real match → call /match/break
                url = `${API_URL}/api/v1/sr-recon/match/break`;
                body = { match_id: breakTargetRow.match_id, reason: breakReason.trim() };
            } else {
                // Resolved finding → call /finding/break
                url = `${API_URL}/api/v1/sr-recon/finding/break`;
                body = { finding_id: breakTargetRow.finding_id, reason: breakReason.trim() };
            }
            const res = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": API_KEY,
                    "Authorization": `Bearer ${token}`,
                },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Break failed");
            }
            setBreakKey(null);
            setBreakTargetRow(null);
            setBreakReason("");
            onRefresh();
        } catch (e: any) {
            setBreakError(e.message);
        } finally {
            setIsBreaking(false);
        }
    };

    // ── Link action (inline, mirrors Break) ──────────────────────────────────
    const handleConfirmLink = async () => {
        if (!linkReason.trim()) { setLinkError("A reason is required."); return; }
        if (!linkRow) return;
        setIsLinking(true);
        setLinkError("");
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_URL}/api/v1/sr-recon/finding/link`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": API_KEY,
                    "Authorization": `Bearer ${token}`,
                },
                body: JSON.stringify({
                    batch_id: batchId,
                    ss_entry_id: linkRow.ss_entry_id,
                    th_entry_id: linkRow.th_entry_id,
                    reason: linkReason.trim(),
                }),
            });
            if (!res.ok) {
                const data = await res.json();
                const raw = data.detail;
                const message =
                    typeof raw === "string"
                        ? raw
                        : Array.isArray(raw)
                            ? raw.map((d: any) => d.msg ?? JSON.stringify(d)).join("; ")
                            : JSON.stringify(raw) || "Link failed";
                throw new Error(message);
            }
            setLinkFindingId(null);
            setLinkRow(null);
            setLinkReason("");
            onRefresh();
        } catch (e: any) {
            setLinkError(e.message);
        } finally {
            setIsLinking(false);
        }
    };

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <div className="flex flex-col h-full">
            {/* Top Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                {/* Summary Cards */}
                <div className="flex gap-2 flex-wrap">
                    {(["ALL", "MATCHED", "UNMATCHED", "EXCEPTION"] as const).map((tab) => {
                        const colors: Record<string, string> = {
                            ALL: "bg-slate-100 text-slate-700 border-slate-200",
                            MATCHED: "bg-blue-50 text-blue-700 border-blue-200",
                            UNMATCHED: "bg-red-50 text-red-700 border-red-200",
                            EXCEPTION: "bg-amber-50 text-amber-700 border-amber-200",
                        };
                        const active: Record<string, string> = {
                            ALL: "bg-slate-700 text-white border-slate-700",
                            MATCHED: "bg-blue-700 text-white border-blue-700",
                            UNMATCHED: "bg-red-600 text-white border-red-600",
                            EXCEPTION: "bg-amber-600 text-white border-amber-600",
                        };
                        return (
                            <button
                                key={tab}
                                onClick={() => { setFilterTab(tab); setPage(1); }}
                                className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${filterTab === tab ? active[tab] : colors[tab]}`}
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
                            onChange={(e) => { setSearchText(e.target.value); setPage(1); }}
                            placeholder="Search Portfolio, Symbol, Scrip…"
                            className="pl-8 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-56"
                        />
                    </div>
                    {/* Upload Button */}
                    <button
                        onClick={() => { onResetFiles?.(); setShowUploadModal(true); }}
                        className="flex items-center gap-1.5 bg-[#1e3b8b] hover:bg-[#1a337a] text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
                    >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        Upload Files
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto bg-white rounded-xl border border-slate-200 shadow-sm">
                {rows.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-48 text-slate-400">
                        <svg className="w-10 h-10 mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <p className="text-sm font-medium">No reconciliation data</p>
                        <p className="text-xs mt-1">Upload both files and run Auto Recon to get started</p>
                        <button
                            onClick={() => { onResetFiles?.(); setShowUploadModal(true); }}
                            className="mt-4 bg-[#1e3b8b] text-white text-xs font-semibold px-4 py-2 rounded-lg hover:bg-[#1a337a] transition-colors"
                        >
                            Upload Files
                        </button>
                    </div>
                ) : (
                    <table className="w-full text-xs table-fixed border-collapse">
                        <colgroup>
                            <col className="w-[12%]" />
                            <col className="w-[10%]" />
                            <col className="w-[10%]" />
                            <col className="w-[14%]" />
                            <col className="w-[8%]" />
                            <col className="w-[8%]" />
                            <col className="w-[10%]" />
                            <col className="w-[10%]" />
                            <col className="w-[18%]" />
                        </colgroup>
                        <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                            <tr>
                                <th className="text-left px-3 py-2.5 text-slate-600 font-semibold">Portfolio ID</th>
                                <th className="text-left px-3 py-2.5 text-slate-600 font-semibold">Symbol</th>
                                <th className="text-left px-3 py-2.5 text-slate-600 font-semibold">Scrip</th>
                                <th className="text-left px-3 py-2.5 text-slate-600 font-semibold">Stock Name</th>
                                <th className="text-right px-3 py-2.5 text-slate-600 font-semibold">SS Qty</th>
                                <th className="text-right px-3 py-2.5 text-slate-600 font-semibold">MERO Balance</th>
                                <th className="text-center px-3 py-2.5 text-slate-600 font-semibold">Status</th>
                                <th className="text-center px-3 py-2.5 text-slate-600 font-semibold">Action</th>
                                <th className="text-left px-3 py-2.5 text-slate-600 font-semibold">Reason</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {paged.map((row, idx) => (
                                <tr key={idx} className="hover:bg-slate-50 transition-colors">
                                    <td className="px-3 py-2.5 font-mono text-slate-700 truncate">{row.portfolio_id || "—"}</td>
                                    <td className="px-3 py-2.5 text-slate-700 truncate">{row.symbol || "—"}</td>
                                    <td className="px-3 py-2.5 text-slate-600 truncate">{row.scrip || "—"}</td>
                                    <td className="px-3 py-2.5 text-slate-600 truncate" title={row.stock_name || ""}>{row.stock_name || "—"}</td>
                                    <td className="px-3 py-2.5 text-right font-mono text-slate-700">
                                        {row.ss_qty != null ? row.ss_qty.toLocaleString() : <span className="text-slate-300">—</span>}
                                    </td>
                                    <td className="px-3 py-2.5 text-right font-mono text-slate-700">
                                        {row.th_balance != null ? row.th_balance.toLocaleString() : <span className="text-slate-300">—</span>}
                                    </td>
                                    <td className="px-3 py-2.5 text-center">
                                        <StatusBadge status={row.status} matchKind={row.match_kind} />
                                    </td>
                                    <td className="px-3 py-2.5 text-center">
                                        {row.status === "MATCHED" ? (
                                            breakKey === (row.match_id ? `m_${row.match_id}` : `f_${row.finding_id}`) ? (
                                                // Inline break confirm
                                                <div className="flex flex-col gap-1 w-[160px] text-left mx-auto">
                                                    <input
                                                        type="text"
                                                        value={breakReason}
                                                        onChange={e => setBreakReason(e.target.value)}
                                                        placeholder="Enter reason…"
                                                        className="border border-slate-300 rounded px-2 py-1 text-xs w-full focus:outline-none focus:ring-1 focus:ring-red-400"
                                                    />
                                                    {breakError && <p className="text-red-500 text-[10px]">{breakError}</p>}
                                                    <div className="flex gap-1">
                                                        <button
                                                            onClick={handleBreak}
                                                            disabled={isBreaking}
                                                            className="flex-1 bg-red-600 hover:bg-red-700 text-white rounded px-2 py-1 text-[10px] font-semibold disabled:opacity-50"
                                                        >
                                                            {isBreaking ? "…" : "Confirm"}
                                                        </button>
                                                        <button
                                                            onClick={() => { setBreakKey(null); setBreakTargetRow(null); setBreakReason(""); setBreakError(""); }}
                                                            className="flex-1 bg-slate-200 hover:bg-slate-300 text-slate-600 rounded px-2 py-1 text-[10px] font-semibold"
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <button
                                                    onClick={() => {
                                                        setBreakKey(row.match_id ? `m_${row.match_id}` : `f_${row.finding_id}`);
                                                        setBreakTargetRow(row);
                                                        setBreakReason("");
                                                        setBreakError("");
                                                    }}
                                                    className="w-14 shrink-0 text-[10px] font-semibold text-red-600 hover:text-red-800 border border-red-200 hover:bg-red-50 px-2 py-1 rounded transition-colors mx-auto block"
                                                >
                                                    Break
                                                </button>
                                            )
                                        ) : (
                                            // UNMATCHED or EXCEPTION → inline Link (always active)
                                            linkFindingId === (row.finding_id ?? row.ss_entry_id ?? row.th_entry_id) ? (
                                                // Inline link confirm — mirrors Break UX exactly
                                                <div className="flex flex-col gap-1 w-[160px] text-left mx-auto">
                                                    <input
                                                        type="text"
                                                        value={linkReason}
                                                        onChange={e => setLinkReason(e.target.value)}
                                                        placeholder="Enter reason…"
                                                        className="border border-slate-300 rounded px-2 py-1 text-xs w-full focus:outline-none focus:ring-1 focus:ring-blue-400"
                                                    />
                                                    {linkError && <p className="text-red-500 text-[10px]">{linkError}</p>}
                                                    <div className="flex gap-1">
                                                        <button
                                                            onClick={handleConfirmLink}
                                                            disabled={isLinking}
                                                            className="flex-1 bg-[#1e3b8b] hover:bg-[#1a337a] text-white rounded px-2 py-1 text-[10px] font-semibold disabled:opacity-50"
                                                        >
                                                            {isLinking ? "…" : "Confirm"}
                                                        </button>
                                                        <button
                                                            onClick={() => { setLinkFindingId(null); setLinkRow(null); setLinkReason(""); setLinkError(""); }}
                                                            className="flex-1 bg-slate-200 hover:bg-slate-300 text-slate-600 rounded px-2 py-1 text-[10px] font-semibold"
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <button
                                                    onClick={() => {
                                                        setLinkFindingId(row.finding_id ?? row.ss_entry_id ?? row.th_entry_id!);
                                                        setLinkRow(row);
                                                        setLinkReason("");
                                                        setLinkError("");
                                                    }}
                                                    className="w-14 shrink-0 text-[10px] font-semibold text-blue-600 hover:text-blue-800 border border-blue-200 hover:bg-blue-50 px-2 py-1 rounded transition-colors mx-auto block"
                                                >
                                                    Link
                                                </button>
                                            )
                                        )}
                                    </td>
                                    <td className="px-3 py-2.5 text-left">
                                        {row.reason && (
                                            <span className="text-slate-400 italic text-[10px] whitespace-normal" title={row.reason}>
                                                {simplifyReason(row.reason)}
                                            </span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Pagination */}
            {filtered.length > 0 && (
                <Pagination
                    currentPage={page}
                    totalPages={totalPages}
                    pageSize={pageSize}
                    totalItems={filtered.length}
                    onPageChange={setPage}
                    onPageSizeChange={(size) => { setPageSize(size); setPage(1); }}
                />
            )}

            {/* Upload Modal */}
            {showUploadModal && (
                <StockUploadModal
                    onClose={() => setShowUploadModal(false)}
                    onAutoMatch={onAutoMatch}
                    isProcessing={isProcessing}
                    hasSummaryFile={hasSummaryFile}
                    hasHistoryFile={hasHistoryFile}
                    onSummaryUpload={onSummaryUpload}
                    onHistoryUpload={onHistoryUpload}
                    isSummaryUploading={isSummaryUploading}
                    isHistoryUploading={isHistoryUploading}
                />
            )}
        </div>
    );
}
