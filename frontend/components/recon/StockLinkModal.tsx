"use client";

import React, { useState } from "react";

interface StockLinkModalProps {
    portfolioId: string;
    symbol: string;
    scrip?: string;
    stockName?: string;
    ssQty?: number | null;
    thBalance?: number | null;
    ssEntryId: number;
    thEntryId: number;
    batchId: number;
    onClose: () => void;
    onConfirm: (ssEntryId: number, thEntryId: number, reason: string) => Promise<void>;
}

export function StockLinkModal({
    portfolioId,
    symbol,
    scrip,
    stockName,
    ssQty,
    thBalance,
    ssEntryId,
    thEntryId,
    batchId,
    onClose,
    onConfirm,
}: StockLinkModalProps) {
    const [reason, setReason] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const handleConfirm = async () => {
        if (!reason.trim()) {
            setError("A reason is required to link these entries.");
            return;
        }
        setError("");
        setIsLoading(true);
        try {
            await onConfirm(ssEntryId, thEntryId, reason.trim());
            onClose();
        } catch (e: any) {
            setError(e.message || "Failed to link entries.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden">
                {/* Header */}
                <div className="bg-gradient-to-r from-[#172554] to-[#1e3a8a] px-5 py-4">
                    <h2 className="text-white font-bold text-sm tracking-wide uppercase">Manual Link</h2>
                    <p className="text-blue-200 text-xs mt-0.5">Stock Position Reconciliation</p>
                </div>

                <div className="p-5 space-y-4">
                    {/* Entry Info */}
                    <div className="bg-slate-50 rounded-lg p-3 space-y-2 text-xs">
                        <div className="flex justify-between">
                            <span className="text-slate-500 font-medium">Portfolio</span>
                            <span className="text-slate-800 font-semibold">{portfolioId || "—"}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-slate-500 font-medium">Symbol</span>
                            <span className="text-slate-800 font-semibold">{symbol || "—"}</span>
                        </div>
                        {scrip && (
                            <div className="flex justify-between">
                                <span className="text-slate-500 font-medium">Scrip</span>
                                <span className="text-slate-800">{scrip}</span>
                            </div>
                        )}
                        {stockName && (
                            <div className="flex justify-between">
                                <span className="text-slate-500 font-medium">Stock Name</span>
                                <span className="text-slate-800">{stockName}</span>
                            </div>
                        )}
                        <div className="border-t border-slate-200 pt-2 flex justify-between">
                            <span className="text-slate-500 font-medium">SS Qty</span>
                            <span className="text-slate-800">{ssQty != null ? ssQty.toLocaleString() : "—"}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-slate-500 font-medium">TH Balance</span>
                            <span className="text-slate-800">{thBalance != null ? thBalance.toLocaleString() : "—"}</span>
                        </div>
                    </div>

                    {error && (
                        <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-xs">
                            {error}
                        </div>
                    )}

                    {/* Reason */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">
                            Reason <span className="text-red-500">*</span>
                        </label>
                        <textarea
                            rows={3}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            placeholder="Provide a reason for this manual link…"
                            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                        />
                    </div>
                </div>

                {/* Actions */}
                <div className="px-5 pb-5 flex gap-3">
                    <button
                        onClick={handleConfirm}
                        disabled={isLoading || !reason.trim()}
                        className="flex-1 bg-[#1e3b8b] hover:bg-[#1a337a] disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold py-2.5 px-4 rounded-lg transition-all flex items-center justify-center gap-2"
                    >
                        {isLoading ? (
                            <>
                                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Linking…
                            </>
                        ) : (
                            "Confirm Link"
                        )}
                    </button>
                    <button
                        onClick={onClose}
                        className="px-4 py-2.5 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                    >
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    );
}
