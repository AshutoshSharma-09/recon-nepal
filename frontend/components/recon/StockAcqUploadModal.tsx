"use client";

import React, { useState, useRef } from "react";
import { API_URL, API_KEY } from "@/lib/config";

interface StockAcqUploadModalProps {
    onClose: () => void;
    onAutoMatch: () => Promise<boolean>;
    isProcessing: boolean;
    hasAcquisitionFile: boolean;
    hasHistoryFile: boolean;
    onAcquisitionUpload: (file: File) => Promise<void>;
    onHistoryUpload: (file: File) => Promise<void>;
    isAcquisitionUploading: boolean;
    isHistoryUploading: boolean;
}

export function StockAcqUploadModal({
    onClose,
    onAutoMatch,
    isProcessing,
    hasAcquisitionFile,
    hasHistoryFile,
    onAcquisitionUpload,
    onHistoryUpload,
    isAcquisitionUploading,
    isHistoryUploading,
}: StockAcqUploadModalProps) {
    const acqRef = useRef<HTMLInputElement>(null);
    const histRef = useRef<HTMLInputElement>(null);
    const [acqName, setAcqName] = useState<string>("");
    const [histName, setHistName] = useState<string>("");
    const [error, setError] = useState<string>("");

    const handleAcqChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        if (!file.name.toLowerCase().endsWith(".csv")) {
            setError("Only CSV files are accepted for Stock Acquisitions.");
            return;
        }
        setError("");
        setAcqName(file.name);
        await onAcquisitionUpload(file);
    };

    const handleHistChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        if (!file.name.toLowerCase().endsWith(".csv")) {
            setError("Only CSV files are accepted for Transaction History.");
            return;
        }
        setError("");
        setHistName(file.name);
        await onHistoryUpload(file);
    };

    const handleAutoRecon = async () => {
        if (!hasAcquisitionFile || !hasHistoryFile) {
            setError("Please upload both files before running Auto Recon.");
            return;
        }
        setError("");
        const ok = await onAutoMatch();
        if (ok) onClose();
    };

    const isUploading = isAcquisitionUploading || isHistoryUploading;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
                {/* Header */}
                <div className="bg-gradient-to-r from-[#172554] to-[#1e3a8a] px-6 py-4 flex items-center justify-between">
                    <div>
                        <h2 className="text-white font-bold text-sm tracking-widest uppercase">Upload Files</h2>
                        <p className="text-blue-200 text-xs mt-0.5">Stock Acquisition Reconciliation</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-white/70 hover:text-white transition-colors p-1 rounded-md hover:bg-white/10"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-6 space-y-5">
                    {error && (
                        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-xs">
                            {error}
                        </div>
                    )}

                    {/* Stock Acquisition CSV Upload */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            Stock Acquisitions CSV
                            <span className="text-red-500 ml-1">*</span>
                        </label>
                        <button
                            type="button"
                            onClick={() => acqRef.current?.click()}
                            disabled={isAcquisitionUploading}
                            className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasAcquisitionFile
                                    ? "border-green-400 bg-green-50 text-green-700"
                                    : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                } ${isAcquisitionUploading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                        >
                            {isAcquisitionUploading ? (
                                <svg className="w-5 h-5 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                            ) : hasAcquisitionFile ? (
                                <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            ) : (
                                <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                            )}
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium truncate">
                                    {isAcquisitionUploading ? "Uploading…" : acqName || "Click to select Stock Acquisitions CSV"}
                                </p>
                                {!acqName && !isAcquisitionUploading && (
                                    <p className="text-xs text-slate-400 mt-0.5">Expected: Portfolio_ID, Scrip, Qty</p>
                                )}
                            </div>
                        </button>
                        <input ref={acqRef} type="file" accept=".csv" className="hidden" onChange={handleAcqChange} />
                    </div>

                    {/* Transaction History CSV Upload */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            Transaction History CSV
                            <span className="text-red-500 ml-1">*</span>
                        </label>
                        <button
                            type="button"
                            onClick={() => histRef.current?.click()}
                            disabled={isHistoryUploading}
                            className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasHistoryFile
                                    ? "border-green-400 bg-green-50 text-green-700"
                                    : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                } ${isHistoryUploading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                        >
                            {isHistoryUploading ? (
                                <svg className="w-5 h-5 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                            ) : hasHistoryFile ? (
                                <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            ) : (
                                <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                            )}
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium truncate">
                                    {isHistoryUploading ? "Uploading…" : histName || "Click to select Transaction History CSV"}
                                </p>
                                {!histName && !isHistoryUploading && (
                                    <p className="text-xs text-slate-400 mt-0.5">Expected: Portfolio_ID, Scrip, Transaction_Date, Credit_Quantity</p>
                                )}
                            </div>
                        </button>
                        <input ref={histRef} type="file" accept=".csv" className="hidden" onChange={handleHistChange} />
                    </div>
                </div>

                {/* Footer Actions */}
                <div className="px-6 pb-6 flex gap-3">
                    <button
                        onClick={handleAutoRecon}
                        disabled={isProcessing || isUploading || !hasAcquisitionFile || !hasHistoryFile}
                        className="flex-1 bg-[#1e3b8b] hover:bg-[#1a337a] disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold py-2.5 px-4 rounded-lg transition-all flex items-center justify-center gap-2"
                    >
                        {isProcessing ? (
                            <>
                                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Running…
                            </>
                        ) : (
                            <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                                Auto Recon
                            </>
                        )}
                    </button>
                    <button
                        onClick={onClose}
                        className="px-4 py-2.5 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
}
