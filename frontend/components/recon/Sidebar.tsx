"use client";

import React from 'react';

interface SidebarProps {
    onBankUpload: (file: File) => void;
    onBrokerUpload: (file: File) => void;
    isProcessing: boolean;
    isUploading?: boolean;
    onApply: () => void;
    onReset: () => void;
    isOpen: boolean;
    onClose: () => void;
    onToleranceChange?: (amount: number, dateWindow: number) => void;
}

export function Sidebar({ onBankUpload, onBrokerUpload, isProcessing, isUploading = false, onApply, onReset, isOpen, onClose, onToleranceChange }: SidebarProps) {
    const [toleranceAmount, setToleranceAmount] = React.useState<number>(50);
    const [dateWindowDays, setDateWindowDays] = React.useState<number>(2);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'bank' | 'broker') => {
        if (e.target.files && e.target.files[0]) {
            if (type === 'bank') onBankUpload(e.target.files[0]);
            else onBrokerUpload(e.target.files[0]);
        }
    };

    const handleToleranceAmountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseFloat(e.target.value) || 0;
        setToleranceAmount(value);
        if (onToleranceChange) {
            onToleranceChange(value, dateWindowDays);
        }
    };

    const handleDateWindowChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(e.target.value) || 0;
        setDateWindowDays(value);
        if (onToleranceChange) {
            onToleranceChange(toleranceAmount, value);
        }
    };

    return (
        <>
            {/* Mobile Overlay */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-20 md:hidden backdrop-blur-sm"
                    onClick={onClose}
                />
            )}

            <aside className={`
                fixed md:static inset-y-0 left-0 z-30
                w-48 bg-gradient-to-b from-[#1e40af] to-[#1e3a8a] text-white 
                flex flex-col h-full shrink-0 border-r border-[#1e3a8a] text-xs 
                overflow-y-auto no-scrollbar shadow-xl transition-transform duration-300 ease-in-out
                ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
            `}>
                <div className="flex justify-end p-2 md:hidden">
                    <button onClick={onClose} className="p-1 text-white/70 hover:text-white">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>
                <div className="flex-1 p-4 bg-[#1e40af]/20 backdrop-blur-sm space-y-8">

                    {/* Filters & Settings Section */}
                    <div className="space-y-4">
                        <h2 className="font-bold text-white px-1 tracking-wider text-[11px] opacity-90 border-b border-blue-400/30 pb-2">FILTERS</h2>

                        {/* Date Range */}
                        <div className="space-y-1">
                            <label className="text-blue-100/80 block pb-1 text-[10px] uppercase font-medium">Date range</label>
                            <div className="flex flex-col gap-2">
                                <input type="date" className="w-full bg-[#172554]/60 border border-[#3b82f6]/30 rounded px-2 py-1.5 text-white text-[10px] focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/50 transition-all font-sans" />
                                <input type="date" className="w-full bg-[#172554]/60 border border-[#3b82f6]/30 rounded px-2 py-1.5 text-white text-[10px] focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/50 transition-all font-sans" />
                            </div>
                        </div>

                        {/* Recon Type */}
                        <div className="space-y-1">
                            <label className="text-blue-100/80 block pb-1 text-[10px] uppercase font-medium">Recon Type</label>
                            <div className="relative">
                                <select className="w-full bg-[#172554]/60 border border-[#3b82f6]/30 rounded-md px-2 pr-7 py-1.5 text-white focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/50 transition-all font-sans appearance-none text-[10px] cursor-pointer hover:bg-[#172554]/80">
                                    <option value="">All Recons</option>
                                    <option value="bank">Bank Reconciliation</option>
                                    <option value="car">Broker Recon – Cash/AR</option>
                                    <option value="cap">Broker Recon – Cash/AP</option>
                                    <option value="sr">Stock Position Recon</option>
                                    <option value="sma">Stock Acquisition Recon</option>
                                    <option value="sml">Stock Liquidation Recon</option>
                                </select>
                                {/* chevron icon */}
                                <div className="pointer-events-none absolute inset-y-0 right-1.5 flex items-center">
                                    <svg className="w-3 h-3 text-blue-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                    </svg>
                                </div>
                            </div>
                        </div>

                        {/* Reference Contains */}
                        <div className="space-y-1">
                            <label className="text-blue-100/80 block pb-1 text-[10px] uppercase font-medium">Reference contains</label>
                            <input type="text" className="w-full bg-[#172554]/60 border border-[#3b82f6]/30 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/50 min-h-[30px] transition-all font-sans placeholder-blue-300/30" placeholder="Search..." />
                        </div>

                        {/* Settlement Type */}
                        <div className="space-y-1">
                            <label className="text-blue-100/80 block pb-1 text-[10px] uppercase font-medium">Settlement type</label>
                            <select className="w-full bg-[#172554]/60 border border-[#3b82f6]/30 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/50 transition-all font-sans appearance-none">
                                <option>Any</option>
                                <option>RTGS</option>
                                <option>NEFT</option>
                                <option>IPS</option>
                            </select>
                        </div>

                        {/* Tolerance Mode */}
                        <div className="space-y-1">
                            <div className="flex justify-between items-center text-blue-100/80 pb-1">
                                <label className="text-[10px] uppercase font-medium">Tolerance mode</label>
                                <span className="text-[9px] bg-blue-500/20 px-1.5 py-0.5 rounded text-blue-200">Fixed</span>
                            </div>
                            <div className="flex items-center gap-2 relative">
                                <span className="absolute left-2 text-blue-300/70 text-[10px]">₹</span>
                                <input
                                    type="number"
                                    value={toleranceAmount}
                                    onChange={handleToleranceAmountChange}
                                    className="w-full bg-[#172554]/60 border border-[#3b82f6]/30 rounded pl-5 pr-2 py-1.5 text-white focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/50 transition-all font-sans"
                                />
                            </div>
                        </div>

                        {/* Date Window */}
                        <div className="space-y-1">
                            <label className="text-blue-100/80 block pb-1 text-[10px] uppercase font-medium">Date window (days)</label>
                            <input
                                type="number"
                                value={dateWindowDays}
                                onChange={handleDateWindowChange}
                                className="w-full bg-[#172554]/60 border border-[#3b82f6]/30 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/50 transition-all font-sans"
                            />
                        </div>

                        {/* Posting Mode */}
                        <div className="space-y-1">
                            <label className="text-blue-100/80 block pb-1 text-[10px] uppercase font-medium">Posting mode</label>
                            <select className="w-full bg-[#172554]/60 border border-[#3b82f6]/30 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/50 transition-all font-sans appearance-none">
                                <option>Any</option>
                            </select>
                        </div>

                        {/* Netting */}
                        <div className="space-y-1 pt-2">
                            <label className="flex items-center gap-2 text-blue-100 cursor-pointer group">
                                <div className="relative flex items-center">
                                    <input type="checkbox" className="peer h-3 w-3 cursor-pointer appearance-none rounded border border-blue-400/50 bg-[#172554]/60 checked:bg-blue-500 checked:border-transparent transition-all" />
                                    <svg className="pointer-events-none absolute h-3 w-3 stroke-white opacity-0 peer-checked:opacity-100" viewBox="0 0 14 14" fill="none">
                                        <path d="M3 7L6 10L11 4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                </div>
                                <span className="leading-tight text-[11px] group-hover:text-white transition-colors">Enable broker netting view</span>
                            </label>
                        </div>

                        {/* Main Buttons */}
                        <div className="grid grid-cols-2 gap-3 pt-3">
                            <button onClick={onApply} className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-2 transition-all shadow-lg hover:shadow-blue-500/20 font-semibold text-[11px] uppercase tracking-wide">Apply</button>
                            <button onClick={onReset} className="bg-[#172554]/40 hover:bg-[#1e3a8a]/60 text-blue-200 border border-blue-400/30 rounded px-3 py-2 transition-all hover:text-white font-medium text-[11px] uppercase tracking-wide">Reset</button>
                        </div>
                    </div>

                    {/* Uploads Section */}
                    <div className="space-y-6">
                        {/* Section 1: Bank <-> Broker (Net) - MOVED TO GRID MODAL */}

                        {/* Section 2: Bank <-> Cash/AR/AP */}

                        {/* Section 3: Cash <-> AR/AP (Gross) */}




                        <div className="text-blue-400/60 text-[9px] leading-tight pt-2 italic text-center">
                            Secure Environment • v2.4.0
                        </div>
                    </div>
                </div>
            </aside >
        </>
    );
}
