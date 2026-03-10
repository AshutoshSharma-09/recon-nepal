import React from 'react';

interface BrokerCashUploadModalProps {
    isOpen: boolean;
    onClose: () => void;
    onBrokerLedgerUpload: (file: File) => void;
    onCashLedgerUpload: (file: File) => void;
    onARUpload: (file: File) => void;
    onAPUpload: (file: File) => void;
    onAutoMatch: () => void;
    isUploading: boolean;
    isProcessing: boolean;
    showAr?: boolean;
    showAp?: boolean;
}

export function BrokerCashUploadModal({
    isOpen, onClose, onBrokerLedgerUpload, onCashLedgerUpload, onARUpload, onAPUpload,
    onAutoMatch, isUploading, isProcessing, showAr = true, showAp = true
}: BrokerCashUploadModalProps) {
    const brokerRef = React.useRef<HTMLInputElement>(null);
    const cashRef = React.useRef<HTMLInputElement>(null);
    const arRef = React.useRef<HTMLInputElement>(null);
    const apRef = React.useRef<HTMLInputElement>(null);

    const [brokerFile, setBrokerFile] = React.useState('');
    const [cashFile, setCashFile] = React.useState('');
    const [arFile, setArFile] = React.useState('');
    const [apFile, setApFile] = React.useState('');

    React.useEffect(() => { if (!isOpen) { setBrokerFile(''); setCashFile(''); setArFile(''); setApFile(''); } }, [isOpen]);

    if (!isOpen) return null;

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'broker' | 'cash' | 'ar' | 'ap') => {
        const file = e.target.files?.[0];
        if (!file) return;
        switch (type) {
            case 'broker': setBrokerFile(file.name); onBrokerLedgerUpload(file); break;
            case 'cash': setCashFile(file.name); onCashLedgerUpload(file); break;
            case 'ar': setArFile(file.name); onARUpload(file); break;
            case 'ap': setApFile(file.name); onAPUpload(file); break;
        }
    };

    const hasBrokerFile = !!brokerFile;
    const hasCashFile = !!cashFile;
    const hasArFile = !!arFile;
    const hasApFile = !!apFile;

    const canAutoMatch = hasBrokerFile && hasCashFile && (!showAr || hasArFile) && (!showAp || hasApFile);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
                {/* Header */}
                <div className="bg-gradient-to-r from-[#172554] to-[#1e3a8a] px-6 py-4 flex items-center justify-between">
                    <div>
                        <h2 className="text-white font-bold text-sm tracking-widest uppercase">Upload Files</h2>
                        <p className="text-blue-200 text-xs mt-0.5">Broker vs Cash Recon</p>
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
                    {/* Broker Ledger Upload */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            Broker Ledger CSV
                            <span className="text-red-500 ml-1">*</span>
                        </label>
                        <button
                            type="button"
                            onClick={() => brokerRef.current?.click()}
                            disabled={isUploading}
                            className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasBrokerFile
                                    ? "border-green-400 bg-green-50 text-green-700"
                                    : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                } ${isUploading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                        >
                            {hasBrokerFile ? (
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
                                    {brokerFile || "Click to select Broker Ledger CSV"}
                                </p>
                            </div>
                        </button>
                        <input
                            ref={brokerRef}
                            type="file"
                            accept=".csv"
                            className="hidden"
                            onChange={(e) => handleChange(e, 'broker')}
                        />
                    </div>

                    {/* Cash Ledger Upload */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            Cash Ledger CSV
                            <span className="text-red-500 ml-1">*</span>
                        </label>
                        <button
                            type="button"
                            onClick={() => cashRef.current?.click()}
                            disabled={isUploading}
                            className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasCashFile
                                    ? "border-green-400 bg-green-50 text-green-700"
                                    : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                } ${isUploading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                        >
                            {hasCashFile ? (
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
                                    {cashFile || "Click to select Cash Ledger CSV"}
                                </p>
                            </div>
                        </button>
                        <input
                            ref={cashRef}
                            type="file"
                            accept=".csv"
                            className="hidden"
                            onChange={(e) => handleChange(e, 'cash')}
                        />
                    </div>

                    {/* AR Upload */}
                    {showAr && (
                        <div>
                            <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                                AR CSV
                                <span className="text-red-500 ml-1">*</span>
                            </label>
                            <button
                                type="button"
                                onClick={() => arRef.current?.click()}
                                disabled={isUploading}
                                className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasArFile
                                        ? "border-green-400 bg-green-50 text-green-700"
                                        : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                    } ${isUploading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                            >
                                {hasArFile ? (
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
                                        {arFile || "Click to select AR CSV"}
                                    </p>
                                </div>
                            </button>
                            <input
                                ref={arRef}
                                type="file"
                                accept=".csv"
                                className="hidden"
                                onChange={(e) => handleChange(e, 'ar')}
                            />
                        </div>
                    )}

                    {/* AP Upload */}
                    {showAp && (
                        <div>
                            <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                                AP CSV
                                <span className="text-red-500 ml-1">*</span>
                            </label>
                            <button
                                type="button"
                                onClick={() => apRef.current?.click()}
                                disabled={isUploading}
                                className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasApFile
                                        ? "border-green-400 bg-green-50 text-green-700"
                                        : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                    } ${isUploading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                            >
                                {hasApFile ? (
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
                                        {apFile || "Click to select AP CSV"}
                                    </p>
                                </div>
                            </button>
                            <input
                                ref={apRef}
                                type="file"
                                accept=".csv"
                                className="hidden"
                                onChange={(e) => handleChange(e, 'ap')}
                            />
                        </div>
                    )}
                </div>

                {/* Footer Actions */}
                <div className="px-6 pb-6 flex gap-3">
                    <button
                        onClick={onAutoMatch}
                        disabled={isProcessing || isUploading || !canAutoMatch}
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
