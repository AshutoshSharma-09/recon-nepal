"use client";

import React from 'react';

interface BankBrokerUploadModalProps {
    isOpen: boolean;
    onClose: () => void;
    onBankUpload: (file: File) => void;
    onBrokerUpload: (file: File) => void;
    isUploading: boolean;
    isBankUploading?: boolean;
    isBrokerUploading?: boolean;
    onAutoMatch: () => void;
    isProcessing: boolean;
    hasBankFile: boolean;
    hasBrokerFile: boolean;
}

export function BankBrokerUploadModal({ isOpen, onClose, onBankUpload, onBrokerUpload, isUploading, isBankUploading, isBrokerUploading, onAutoMatch, isProcessing, hasBankFile, hasBrokerFile }: BankBrokerUploadModalProps) {
    const bankInputRef = React.useRef<HTMLInputElement>(null);
    const brokerInputRef = React.useRef<HTMLInputElement>(null);

    const [bankFileName, setBankFileName] = React.useState<string>('');
    const [brokerFileName, setBrokerFileName] = React.useState<string>('');

    // Backward compatibility if granular states aren't provided
    const bankLoading = isBankUploading ?? isUploading;
    const brokerLoading = isBrokerUploading ?? isUploading;

    React.useEffect(() => {
        if (!hasBankFile && !isBankUploading) {
            if (bankInputRef.current) bankInputRef.current.value = '';
            setBankFileName('');
        }
    }, [hasBankFile, isBankUploading]);

    React.useEffect(() => {
        if (!hasBrokerFile && !isBrokerUploading) {
            if (brokerInputRef.current) brokerInputRef.current.value = '';
            setBrokerFileName('');
        }
    }, [hasBrokerFile, isBrokerUploading]);

    React.useEffect(() => {
        if (!isOpen) {
            setBankFileName('');
            setBrokerFileName('');
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'bank' | 'broker') => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            const ext = file.name.split('.').pop()?.toLowerCase();

            if (type === 'bank') {
                if (ext !== 'txt') {
                    alert("Please upload a .txt file for Bank Statement");
                    if (bankInputRef.current) bankInputRef.current.value = '';
                    setBankFileName('');
                    return;
                }
                setBankFileName(file.name);
                onBankUpload(file);
            } else {
                if (ext !== 'csv') {
                    alert("Please upload a .csv file for Broker Ledger");
                    if (brokerInputRef.current) brokerInputRef.current.value = '';
                    setBrokerFileName('');
                    return;
                }
                setBrokerFileName(file.name);
                onBrokerUpload(file);
            }
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
                {/* Header */}
                <div className="bg-gradient-to-r from-[#172554] to-[#1e3a8a] px-6 py-4 flex items-center justify-between">
                    <div>
                        <h2 className="text-white font-bold text-sm tracking-widest uppercase">Upload Files</h2>
                        <p className="text-blue-200 text-xs mt-0.5">Bank ↔ Broker Reconciliation</p>
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
                    {/* Bank Statement Upload */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            Bank Statement (.txt)
                            <span className="text-red-500 ml-1">*</span>
                        </label>
                        <button
                            type="button"
                            onClick={() => bankInputRef.current?.click()}
                            disabled={bankLoading}
                            className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasBankFile
                                    ? "border-green-400 bg-green-50 text-green-700"
                                    : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                } ${bankLoading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                        >
                            {bankLoading ? (
                                <svg className="w-5 h-5 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                            ) : hasBankFile ? (
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
                                    {bankLoading ? "Uploading…" : bankFileName || "Click to select Bank Statement"}
                                </p>
                            </div>
                        </button>
                        <input
                            ref={bankInputRef}
                            type="file"
                            accept=".txt"
                            className="hidden"
                            onChange={(e) => handleFileChange(e, 'bank')}
                        />
                    </div>

                    {/* Broker Ledger Upload */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            Broker Ledger CSV
                            <span className="text-red-500 ml-1">*</span>
                        </label>
                        <button
                            type="button"
                            onClick={() => brokerInputRef.current?.click()}
                            disabled={brokerLoading}
                            className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasBrokerFile
                                    ? "border-green-400 bg-green-50 text-green-700"
                                    : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                } ${brokerLoading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                        >
                            {brokerLoading ? (
                                <svg className="w-5 h-5 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                            ) : hasBrokerFile ? (
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
                                    {brokerLoading ? "Uploading…" : brokerFileName || "Click to select Broker Ledger CSV"}
                                </p>
                            </div>
                        </button>
                        <input
                            ref={brokerInputRef}
                            type="file"
                            accept=".csv"
                            className="hidden"
                            onChange={(e) => handleFileChange(e, 'broker')}
                        />
                    </div>
                </div>

                {/* Footer Actions */}
                <div className="px-6 pb-6 flex gap-3">
                    <button
                        onClick={onAutoMatch}
                        disabled={isProcessing || bankLoading || brokerLoading || !hasBankFile || !hasBrokerFile}
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
