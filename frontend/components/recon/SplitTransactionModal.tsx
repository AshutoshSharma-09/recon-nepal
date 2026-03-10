"use client";

import React, { useState, useEffect } from 'react';
import { Plus, X, Trash2 } from 'lucide-react';

interface SplitTransactionModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (parent: any, candidates: any[]) => void;
    parentRow: any;
    candidateRows: any[];
    // Optional label overrides for Cash vs AR recon
    parentTypeName?: string;     // default: derived from rawBank/rawBroker ("Bank" / "Broker")
    candidateTypeName?: string;  // default: derived from rawBank/rawBroker
    refColumnLabel?: string;     // default: "Reference Number"
}

export function SplitTransactionModal({ isOpen, onClose, onConfirm, parentRow, candidateRows, parentTypeName, candidateTypeName, refColumnLabel = 'Reference Number' }: SplitTransactionModalProps) {
    const [selectedCandidates, setSelectedCandidates] = useState<any[]>([]);
    const [removedCandidates, setRemovedCandidates] = useState<any[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (isOpen && candidateRows) {
            setSelectedCandidates([...candidateRows]);
            setRemovedCandidates([]);
            setIsSubmitting(false);
        }
    }, [isOpen, candidateRows]);

    if (!isOpen || !parentRow) return null;

    // Helper to extract ID safely or generate one
    const getRowId = (row: any) => {
        if (row.isManual) return row.id;
        const raw = row.rawBank || row.rawBroker;
        return raw ? raw.id.toString() : row.id || Math.random().toString();
    };

    const handleRemove = (id: string) => {
        const itemToRemove = selectedCandidates.find(c => getRowId(c) === id);
        if (itemToRemove) {
            setSelectedCandidates(selectedCandidates.filter(c => getRowId(c) !== id));
            // Only add to removed if it's NOT a manual entry (manual entries are just deleted)
            if (!itemToRemove.isManual) {
                setRemovedCandidates([...removedCandidates, itemToRemove]);
            }
        }
    };

    const handleRestore = (id: string) => {
        const itemToRestore = removedCandidates.find(c => getRowId(c) === id);
        if (itemToRestore) {
            setRemovedCandidates(removedCandidates.filter(c => getRowId(c) !== id));
            setSelectedCandidates([...selectedCandidates, itemToRestore]);
        }
    };

    const handleAddManual = () => {
        const newManualItem = {
            id: `manual-${Date.now()}`,
            isManual: true,
            description: '',
            amount: ''
        };
        setSelectedCandidates([...selectedCandidates, newManualItem]);
    };

    const handleManualChange = (id: string, field: 'description' | 'amount', value: any) => {
        setSelectedCandidates(selectedCandidates.map(c => {
            if (getRowId(c) === id) {
                return { ...c, [field]: value };
            }
            return c;
        }));
    };

    // Helper to get Amount
    const getAmount = (row: any) => {
        if (row.isManual) return Number(row.amount) || 0;
        const raw = row.rawBank || row.rawBroker;
        if (!raw) return 0;
        // Prioritize Credit/Debit cols
        const credit = Number(raw.Credit || 0);
        const debit = Number(raw.Debit || 0);
        return credit > 0 ? credit : debit;
    };

    // Helper to get Reference
    const getReference = (row: any) => {
        if (row.isManual) return row.description;
        // If parent is Bank, Candidate is Broker. Show Broker Ref.
        const compRef = parentIsBank ? row.brokerRef : row.bankRef;
        return compRef || '---';
    };

    const parentIsBank = !!parentRow.rawBank;
    const parentRef = parentIsBank ? parentRow.bankRef : parentRow.brokerRef;
    const parentDate = parentIsBank ? parentRow.bankDate : parentRow.brokerDate;
    const parentPortfolio = parentIsBank ? parentRow.bankPortfolio : parentRow.brokerPortfolio;
    const parentAmt = getAmount(parentRow);
    // Use override labels if provided, otherwise derive from data
    const parentType = parentTypeName ?? (parentIsBank ? "Bank Statement" : "Broker Ledger");
    const candidateType = candidateTypeName ?? (parentIsBank ? "Broker Ledger" : "Bank Statement");

    const totalSplitAmount = selectedCandidates.reduce((sum, item) => sum + getAmount(item), 0);
    const remaining = parentAmt - totalSplitAmount;
    // Allow small float tolerance
    const isMatched = Math.abs(remaining) < 0.05;

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
            <div className="relative bg-white rounded-xl shadow-2xl w-[700px] overflow-hidden font-sans text-sm text-gray-800 animate-in fade-in zoom-in duration-200 flex flex-col max-h-[90vh]">

                {/* Close Button (Top Right) */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 bg-red-500 hover:bg-red-600 text-white p-1 rounded-md shadow-sm transition-colors z-10"
                >
                    <X className="w-4 h-4" />
                </button>

                {/* Header */}
                <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
                    <h3 className="font-bold text-lg text-[#0f172a]">Split Transaction</h3>
                    <p className="text-[#64748b] text-xs mt-0.5">Match multiple entries against a parent record</p>
                </div>

                {/* Body - Scrollable */}
                <div className="p-6 space-y-6 overflow-y-auto">

                    {/* Parent Entry Section */}
                    <div>
                        <h4 className="font-bold text-[#334155] mb-2 text-xs uppercase tracking-wider flex items-center gap-2">
                            Parent Entry ({parentTypeName ?? (parentIsBank ? 'Bank' : 'Broker')})
                            <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full text-[10px] uppercase">{parentType}</span>
                        </h4>
                        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-[#64748b] text-[10px] uppercase font-bold mb-1">Date</label>
                                <div className="text-gray-900 font-semibold text-sm">
                                    {parentDate}
                                </div>
                            </div>
                            <div>
                                <label className="block text-[#64748b] text-[10px] uppercase font-bold mb-1">{refColumnLabel}</label>
                                <div className="text-gray-900 font-semibold text-sm truncate" title={parentRef}>
                                    {parentRef}
                                </div>
                            </div>
                            <div>
                                <label className="block text-[#64748b] text-[10px] uppercase font-bold mb-1">Total Amount</label>
                                <div className="text-[#0f172a] font-bold text-lg">
                                    {parentAmt.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}
                                </div>
                            </div>
                            <div>
                                <label className="block text-[#64748b] text-[10px] uppercase font-bold mb-1">Portfolio</label>
                                <div className="text-gray-700 font-medium text-sm">
                                    {parentPortfolio}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Split Components Section */}
                    <div>
                        <div className="flex justify-between items-end mb-2">
                            <h4 className="font-bold text-[#334155] text-xs uppercase tracking-wider">
                                Split Components ({candidateType})
                            </h4>
                            <span className="text-[10px] text-gray-500">{selectedCandidates.length} items selected</span>
                        </div>

                        <div className="bg-gray-50/80 p-1 rounded-xl border border-gray-200 min-h-[150px] flex flex-col">
                            {/* Table Header */}
                            <div className="grid grid-cols-[1fr_140px_40px] gap-2 px-4 py-2 border-b border-gray-200 text-[10px] font-bold text-[#64748b] uppercase tracking-wider bg-gray-100/50 rounded-t-lg">
                                <div>{refColumnLabel}</div>
                                <div className="text-right">Amount</div>
                                <div className="text-center">Action</div>
                            </div>

                            {/* Scrollable List */}
                            <div className="flex-1 p-1 space-y-1">
                                {selectedCandidates.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full text-gray-400 py-8">
                                        <span className="text-xs italic">No candidates selected</span>
                                    </div>
                                ) : (
                                    selectedCandidates.map((comp) => {
                                        const compId = getRowId(comp);
                                        const isManual = comp.isManual;

                                        return (
                                            <div key={compId} className="grid grid-cols-[1fr_140px_40px] gap-2 items-center px-3 py-2 bg-white border border-gray-100 rounded-lg shadow-sm hover:shadow-md transition-all group">

                                                {/* Reference Column */}
                                                <div className="text-xs font-semibold text-gray-700 truncate">
                                                    {isManual ? (
                                                        <input
                                                            type="text"
                                                            placeholder="Enter Reference"
                                                            className="w-full border-b border-gray-300 focus:border-blue-500 focus:outline-none bg-transparent px-1 py-0.5"
                                                            value={comp.description}
                                                            onChange={(e) => handleManualChange(compId, 'description', e.target.value)}
                                                        />
                                                    ) : (
                                                        <span title={getReference(comp)}>{getReference(comp)}</span>
                                                    )}
                                                </div>

                                                {/* Amount Column */}
                                                <div className="text-right">
                                                    {isManual ? (
                                                        <input
                                                            type="text"
                                                            inputMode="decimal"
                                                            placeholder="Enter amount"
                                                            className="w-full text-right border-b border-gray-300 focus:border-blue-500 focus:outline-none bg-transparent px-1 py-0.5 font-mono text-xs"
                                                            value={comp.amount === 0 || comp.amount === '' ? '' : comp.amount}
                                                            onChange={(e) => handleManualChange(compId, 'amount', e.target.value)}
                                                        />
                                                    ) : (
                                                        <span className="font-mono font-medium text-gray-900">
                                                            {getAmount(comp).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                        </span>
                                                    )}
                                                </div>

                                                {/* Action Column */}
                                                <div className="flex justify-center">
                                                    <button
                                                        onClick={() => handleRemove(compId)}
                                                        className="text-gray-300 hover:text-red-500 transition-colors p-1 rounded-md hover:bg-red-50"
                                                        title="Remove"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                    </button>
                                                </div>
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </div>

                        {/* Totals */}
                        <div className="flex items-center justify-between mt-3 px-1">
                            <button
                                onClick={handleAddManual}
                                className="flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-700 hover:bg-blue-50 px-3 py-1.5 rounded-lg transition-colors border border-transparent hover:border-blue-100"
                            >
                                <Plus className="w-3.5 h-3.5" />
                                Add Manual Component
                            </button>

                            <div className="text-right space-y-1">
                                <div className="text-xs text-gray-500 flex justify-between gap-8">
                                    <span>Selected Total:</span>
                                    <span className="font-semibold text-gray-800">{totalSplitAmount.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}</span>
                                </div>
                                <div className={`text-xs flex justify-between gap-8 font-bold ${isMatched ? 'text-green-600' : 'text-red-500'}`}>
                                    <span>Difference:</span>
                                    <span>{remaining.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Restore Section (Only visible if there are removed items) */}
                    {removedCandidates.length > 0 && (
                        <div className="border-t border-dashed border-gray-300 pt-4">
                            <h5 className="font-bold text-gray-500 text-[10px] uppercase tracking-wider mb-2">Available to Add (Removed Items)</h5>
                            <div className="grid grid-cols-1 gap-2 max-h-[120px] overflow-y-auto">
                                {removedCandidates.map((comp) => {
                                    const compId = getRowId(comp);
                                    return (
                                        <div key={compId} className="flex items-center justify-between px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs hover:bg-white transition-colors">
                                            <div className="flex items-center gap-3 overflow-hidden">
                                                <span className="font-semibold text-gray-600 truncate max-w-[200px]">{getReference(comp)}</span>
                                                <span className="text-gray-400 text-[10px]">({comp.rawBank ? 'Bank' : 'Broker'})</span>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <span className="font-mono text-gray-600">{getAmount(comp).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                                <button
                                                    onClick={() => handleRestore(compId)}
                                                    className="text-blue-500 hover:text-blue-700 font-medium text-[10px] bg-blue-50 px-2 py-1 rounded border border-blue-100 hover:border-blue-300 transition-all"
                                                >
                                                    Add Back
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end gap-3 rounded-b-xl">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-white border border-gray-300 text-gray-700 font-semibold rounded-lg text-xs hover:bg-gray-50 hover:border-gray-400 transition-all shadow-sm"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={async () => {
                            if (isSubmitting) return;
                            setIsSubmitting(true);
                            try {
                                await onConfirm(parentRow, selectedCandidates);
                            } finally {
                                setIsSubmitting(false);
                            }
                        }}
                        disabled={!isMatched || isSubmitting}
                        className={`px-4 py-2 text-white font-semibold rounded-lg text-xs transition-all shadow-sm flex items-center gap-2 ${!isMatched || isSubmitting
                                ? 'bg-gray-400 cursor-not-allowed'
                                : 'bg-[#1e40ae] hover:bg-[#1e3a8a] shadow-blue-500/20'
                            }`}
                    >
                        {isSubmitting ? (
                            <>
                                <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                </svg>
                                Submitting...
                            </>
                        ) : 'Confirm Split Match'}
                    </button>
                </div>
            </div>
        </div>
    );
}
