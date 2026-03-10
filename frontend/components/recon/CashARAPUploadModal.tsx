import React from 'react';

interface CashARAPUploadModalProps {
    isOpen: boolean;
    onClose: () => void;
    onCashLedgerUpload: (file: File) => void;
    onARUpload: (file: File) => void;
    onAPUpload: (file: File) => void;
    onAutoMatch: () => void;
    isUploading: boolean;
    isProcessing: boolean;
    hasCashFile?: boolean;
    hasArFile?: boolean;
    hasApFile?: boolean;
    showAr?: boolean;
    showAp?: boolean;
}

export function CashARAPUploadModal({
    isOpen,
    onClose,
    onCashLedgerUpload,
    onARUpload,
    onAPUpload,
    onAutoMatch,
    isUploading,
    isProcessing,
    hasCashFile,
    hasArFile,
    hasApFile,
    showAr = true,
    showAp = true
}: CashARAPUploadModalProps) {

    const cashInputRef = React.useRef<HTMLInputElement>(null);
    const arInputRef = React.useRef<HTMLInputElement>(null);
    const apInputRef = React.useRef<HTMLInputElement>(null);

    const [cashFileName, setCashFileName] = React.useState('');
    const [arFileName, setArFileName] = React.useState('');
    const [apFileName, setApFileName] = React.useState('');
    const [uploadingType, setUploadingType] = React.useState<'cash' | 'ar' | 'ap' | null>(null);

    React.useEffect(() => { if (!hasCashFile) { if (cashInputRef.current) cashInputRef.current.value = ''; setCashFileName(''); } }, [hasCashFile]);
    React.useEffect(() => { if (!hasArFile) { if (arInputRef.current) arInputRef.current.value = ''; setArFileName(''); } }, [hasArFile]);
    React.useEffect(() => { if (!hasApFile) { if (apInputRef.current) apInputRef.current.value = ''; setApFileName(''); } }, [hasApFile]);
    React.useEffect(() => { if (!isOpen) { setCashFileName(''); setArFileName(''); setApFileName(''); setUploadingType(null); } }, [isOpen]);

    if (!isOpen) return null;

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'cash' | 'ar' | 'ap') => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            if (file.name.split('.').pop()?.toLowerCase() !== 'csv') {
                alert("Please upload a .csv file");
                e.target.value = '';
                return;
            }
            setUploadingType(type);
            if (type === 'cash') { setCashFileName(file.name); onCashLedgerUpload(file); }
            else if (type === 'ar') { setArFileName(file.name); onARUpload(file); }
            else { setApFileName(file.name); onAPUpload(file); }
        }
    };

    const isCashLoading = isUploading && uploadingType === 'cash';
    const isArLoading = isUploading && uploadingType === 'ar';
    const isApLoading = isUploading && uploadingType === 'ap';
    const canAutoMatch = hasCashFile && (!showAr || hasArFile) && (!showAp || hasApFile);

    const filesRequired = 1 + (showAr ? 1 : 0) + (showAp ? 1 : 0);
    const filesUploaded = (hasCashFile ? 1 : 0) + (showAr && hasArFile ? 1 : 0) + (showAp && hasApFile ? 1 : 0);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
                {/* Header */}
                <div className="bg-gradient-to-r from-[#172554] to-[#1e3a8a] px-6 py-4 flex items-center justify-between">
                    <div>
                        <h2 className="text-white font-bold text-sm tracking-widest uppercase">Upload Files</h2>
                        <p className="text-blue-200 text-xs mt-0.5">Cash Recon</p>
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
                    {/* Cash Ledger Upload */}
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
                            Cash Ledger CSV
                            <span className="text-red-500 ml-1">*</span>
                        </label>
                        <button
                            type="button"
                            onClick={() => cashInputRef.current?.click()}
                            disabled={isCashLoading}
                            className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasCashFile
                                    ? "border-green-400 bg-green-50 text-green-700"
                                    : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                } ${isCashLoading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                        >
                            {isCashLoading ? (
                                <svg className="w-5 h-5 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                            ) : hasCashFile ? (
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
                                    {isCashLoading ? "Uploading…" : cashFileName || "Click to select Cash Ledger CSV"}
                                </p>
                            </div>
                        </button>
                        <input
                            ref={cashInputRef}
                            type="file"
                            accept=".csv"
                            className="hidden"
                            onChange={(e) => handleFileChange(e, 'cash')}
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
                                onClick={() => arInputRef.current?.click()}
                                disabled={isArLoading}
                                className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasArFile
                                        ? "border-green-400 bg-green-50 text-green-700"
                                        : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                    } ${isArLoading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                            >
                                {isArLoading ? (
                                    <svg className="w-5 h-5 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                ) : hasArFile ? (
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
                                        {isArLoading ? "Uploading…" : arFileName || "Click to select AR CSV"}
                                    </p>
                                </div>
                            </button>
                            <input
                                ref={arInputRef}
                                type="file"
                                accept=".csv"
                                className="hidden"
                                onChange={(e) => handleFileChange(e, 'ar')}
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
                                onClick={() => apInputRef.current?.click()}
                                disabled={isApLoading}
                                className={`w-full flex items-center gap-3 border-2 border-dashed rounded-lg p-4 transition-all text-left
                ${hasApFile
                                        ? "border-green-400 bg-green-50 text-green-700"
                                        : "border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-500"
                                    } ${isApLoading ? "opacity-60 cursor-wait" : "cursor-pointer"}`}
                            >
                                {isApLoading ? (
                                    <svg className="w-5 h-5 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                ) : hasApFile ? (
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
                                        {isApLoading ? "Uploading…" : apFileName || "Click to select AP CSV"}
                                    </p>
                                </div>
                            </button>
                            <input
                                ref={apInputRef}
                                type="file"
                                accept=".csv"
                                className="hidden"
                                onChange={(e) => handleFileChange(e, 'ap')}
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
