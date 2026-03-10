"use client";

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface LinkTransactionModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (note?: string, bankRef?: string, brokerRef?: string) => void;
    data: any;
    toleranceAmount?: number;
    dateWindowDays?: number;
    // Optional label overrides for Cash vs AR recon
    leftLabel?: string;       // default: "Bank Entry"
    rightLabel?: string;      // default: "Broker Entry"
    refFieldLabel?: string;   // default: "Reference (Editable)"
    notePlaceholder?: string; // default: "Required: e.g. Reference mismatch, Manual adjustment..."
}

export function LinkTransactionModal({ isOpen, onClose, onConfirm, data, toleranceAmount = 50, dateWindowDays = 2, leftLabel = 'Bank Entry', rightLabel = 'Broker Entry', refFieldLabel = 'Reference (Editable)', notePlaceholder = 'Required: e.g. Reference mismatch, Manual adjustment...' }: LinkTransactionModalProps) {
    const [note, setNote] = useState('');
    const [bankRef, setBankRef] = useState('');
    const [brokerRef, setBrokerRef] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Reset fields when modal opens/data changes
    useEffect(() => {
        if (isOpen) {
            setNote('');
            setBankRef(data?.bankRef || '');
            setBrokerRef(data?.brokerRef || '');
            setIsSubmitting(false);
        }
    }, [isOpen, data]);

    if (!isOpen) return null;

    // Extract data for validation
    const bankDate = data?.bankDate || '';
    const brokerDate = data?.brokerDate || '';
    const bankPortfolio = data?.bankPortfolio || '';
    const brokerPortfolio = data?.brokerPortfolio || '';
    const bankAmount = data?.bankAmount || '0';
    const brokerNet = data?.brokerNet || '0';

    // Parse amounts (handle +/- prefix)
    const parseBankAmount = Math.abs(parseFloat(bankAmount.replace(/[+\-]/g, '')) || 0);
    const parseBrokerAmount = Math.abs(parseFloat(brokerNet.replace(/[+\-]/g, '')) || 0);

    // Validation checks
    const isReasonProvided = note.trim().length > 0;
    const isReferencesNotEmpty = (bankRef || '').trim().length > 0 && (brokerRef || '').trim().length > 0;

    // Portfolio validation
    const isPortfolioMatching = bankPortfolio === brokerPortfolio && bankPortfolio !== '---';

    // Date validation (with tolerance)
    const dateDiff = Math.abs(
        (new Date(bankDate).getTime() - new Date(brokerDate).getTime()) / (1000 * 60 * 60 * 24)
    );
    const isDateMatching = dateDiff <= dateWindowDays && bankDate !== '---' && brokerDate !== '---';

    // Amount validation (with tolerance)
    const amountDiff = Math.abs(parseBankAmount - parseBrokerAmount);
    const isAmountMatching = amountDiff <= toleranceAmount;

    // Overall validation
    const isValid = isReasonProvided && isReferencesNotEmpty && isPortfolioMatching && isDateMatching && isAmountMatching;

    // Error messages
    let validationMessage = '';
    if (!isReasonProvided) {
        validationMessage = 'Please provide a reason for this manual link.';
    } else if (!isReferencesNotEmpty) {
        validationMessage = 'Reference numbers cannot be empty.';
    } else if (!isPortfolioMatching) {
        validationMessage = `Portfolio IDs must match. Bank: ${bankPortfolio}, Broker: ${brokerPortfolio}`;
    } else if (!isDateMatching) {
        validationMessage = `Value dates must be within ${dateWindowDays} days. Bank: ${bankDate}, Broker: ${brokerDate}`;
    } else if (!isAmountMatching) {
        validationMessage = `Amounts must be within ₹${toleranceAmount} tolerance. Difference: ₹${amountDiff.toFixed(2)}`;
    }

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
            <div className="relative bg-white rounded-lg shadow-xl w-[480px] overflow-hidden font-sans text-sm text-gray-800">
                {/* Close Button (Top Right) */}
                <button
                    onClick={onClose}
                    className="absolute top-3 right-3 bg-red-500 hover:bg-red-600 text-white p-1 rounded shadow-sm transition-colors z-10"
                >
                    <X size={16} />
                </button>
                {/* Header */}
                <div className="px-5 py-3 border-b border-gray-200">
                    <h3 className="font-bold text-base text-gray-800">Link Transactions</h3>
                </div>

                {/* Body */}
                <div className="p-4 space-y-3 relative">

                    {/* Bank Entry Section */}
                    <div>
                        <h4 className="font-bold text-gray-800 mb-1 text-xs px-1">{leftLabel}</h4>
                        <div className="bg-gray-100 p-3 rounded-lg grid grid-cols-2 gap-y-2 gap-x-4 border border-gray-200">
                            <div>
                                <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Date</label>
                                <div className="text-gray-900 font-semibold text-xs px-1">
                                    {data?.bankDate || '---'}
                                </div>
                            </div>
                            <div>
                                <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">{refFieldLabel} (Editable)</label>
                                <input
                                    type="text"
                                    className={`w-full bg-white border rounded px-2 py-1 text-gray-900 font-semibold text-xs focus:outline-blue-500 shadow-sm ${!isReferencesNotEmpty ? 'border-red-300 bg-red-50' : 'border-gray-300'}`}
                                    value={bankRef}
                                    onChange={(e) => setBankRef(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Amount</label>
                                <div className="text-gray-900 font-semibold text-xs px-1 text-blue-700">
                                    {data?.bankAmount || '---'}
                                </div>
                            </div>
                            <div>
                                <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Portfolio ID</label>
                                <div className="text-gray-900 font-semibold text-xs px-1">
                                    {data?.bankPortfolio || '---'}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Broker Entry Section */}
                    <div>
                        <h4 className="font-bold text-gray-800 mb-1 text-xs px-1">{rightLabel}</h4>
                        <div className="bg-gray-100 p-3 rounded-lg grid grid-cols-2 gap-y-2 gap-x-4 border border-gray-200">
                            <div>
                                <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Date</label>
                                <div className="text-gray-900 font-semibold text-xs px-1">
                                    {data?.brokerDate || '---'}
                                </div>
                            </div>
                            <div>
                                <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">{refFieldLabel} (Editable)</label>
                                <input
                                    type="text"
                                    className={`w-full bg-white border rounded px-2 py-1 text-gray-900 font-semibold text-xs focus:outline-blue-500 shadow-sm ${!isReferencesNotEmpty ? 'border-red-300 bg-red-50' : 'border-gray-300'}`}
                                    value={brokerRef}
                                    onChange={(e) => setBrokerRef(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Amount</label>
                                <div className="text-gray-900 font-semibold text-xs px-1 text-blue-700">
                                    {data?.brokerNet || '---'}
                                </div>
                            </div>
                            <div>
                                <label className="block text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Portfolio ID</label>
                                <div className="text-gray-900 font-semibold text-xs px-1">
                                    {data?.brokerPortfolio || '---'}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Note Input */}
                    <div>
                        <label className="block text-gray-500 text-[10px] mb-0.5">Remarks / Reason for Manual Link <span className="text-red-600">*</span></label>
                        <textarea
                            className={`w-full bg-white border rounded px-2 py-1.5 text-gray-700 text-xs focus:outline-none focus:border-blue-500 resize-none ${!isReasonProvided && note.length === 0 ? 'border-gray-300' : !isReasonProvided ? 'border-red-300 bg-red-50' : 'border-gray-300'}`}
                            rows={2}
                            placeholder={notePlaceholder}
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                        />
                    </div>

                    {/* Info Warning */}
                    <div className={`border px-3 py-2 rounded text-[10px] leading-relaxed ${!isValid ? 'bg-red-50 border-red-200 text-red-800' : 'bg-yellow-50 border-yellow-200 text-yellow-800'}`}>
                        {!isValid ? (
                            <div className="flex items-center gap-2 font-bold">
                                <span>⚠️</span>
                                <span>{validationMessage}</span>
                            </div>
                        ) : (
                            <span className="font-bold">Attention: This action will permanently link these two transactions together. {refFieldLabel}s can differ.</span>
                        )}
                    </div>

                </div>

                {/* Footer */}
                <div className="px-5 py-3 bg-gray-50 border-t border-gray-200 flex justify-end gap-2">
                    <button
                        onClick={onClose}
                        className="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 font-medium rounded text-xs hover:bg-gray-50 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={async () => {
                            if (isSubmitting) return;
                            setIsSubmitting(true);
                            try {
                                await onConfirm(note, bankRef, brokerRef);
                            } finally {
                                setIsSubmitting(false);
                            }
                        }}
                        disabled={!isValid || isSubmitting}
                        className={`px-3 py-1.5 font-medium rounded text-xs transition-colors shadow-sm flex items-center gap-1.5 ${!isValid || isSubmitting
                                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                : 'bg-[#1e88e5] text-white hover:bg-[#1976d2]'
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
                        ) : 'Confirm Link'}
                    </button>
                </div>
            </div>
        </div>
    );
}
