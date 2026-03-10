"use client";

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface BreakMatchModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (reason: string) => void;
    data?: any;
}

export function BreakMatchModal({ isOpen, onClose, onConfirm, data }: BreakMatchModalProps) {
    const [reason, setReason] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (isOpen) {
            setReason('');
            setIsSubmitting(false);
        }
    }, [isOpen]);

    if (!isOpen) return null;

    // Utilize the match_id from the raw data object (bank or broker side)
    const matchId = data?.rawBank?.match_id || data?.rawBroker?.match_id || 'Unknown';
    const amount = data?.bankAmount && data.bankAmount !== '---' ? data.bankAmount : data?.brokerNet;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
            <div className="relative bg-[#e2e8f0] rounded-lg shadow-xl w-[450px] p-4 font-sans text-sm text-gray-800 border border-gray-300">

                {/* Close Button (Top Right) */}
                <button
                    onClick={onClose}
                    className="absolute top-3 right-3 bg-red-500 hover:bg-red-600 text-white p-1 rounded shadow-sm transition-colors z-10"
                >
                    <X size={16} />
                </button>

                {/* Header */}
                <h3 className="font-bold text-lg text-black mb-2">Break Match</h3>

                {/* Form Fields */}
                <div className="space-y-4">
                    <div className="flex flex-col">
                        <label className="text-black text-xs font-semibold mb-1">Match ID</label>
                        <div className="w-full border border-gray-400 rounded px-2 py-1.5 bg-gray-100 text-gray-700 shadow-inner font-mono text-xs">
                            {matchId}
                        </div>
                    </div>

                    <div className="flex flex-col">
                        <label className="text-black text-xs font-semibold mb-1">Matched Amount</label>
                        <div className="w-full border border-gray-400 rounded px-2 py-1.5 bg-gray-100 text-gray-700 shadow-inner font-mono">
                            {amount}
                        </div>
                    </div>

                    <div className="flex flex-col">
                        <label className="text-black text-xs font-semibold mb-1">Reason / Notes <span className="text-red-600">*</span></label>
                        <textarea
                            placeholder="Required: Why are you breaking this match?"
                            className={`w-full border rounded px-2 py-1.5 bg-white focus:outline-blue-500 shadow-inner h-20 resize-none ${reason.trim().length === 0 && reason.length > 0 ? 'border-red-400 bg-red-50' : reason.trim().length === 0 ? 'border-gray-400' : 'border-gray-400'}`}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                        />
                    </div>
                </div>

                {/* Tip */}
                <div className="mt-4 text-[11px] text-gray-600 italic bg-yellow-50 p-2 rounded border border-yellow-200">
                    Warning: Breaking this match will return both transactions to the "Unmatched" pool. A reason is required.
                </div>

                {/* Footer Buttons */}
                <div className="flex gap-3 mt-5 justify-end">
                    <button
                        onClick={onClose}
                        className="bg-white hover:bg-gray-100 text-gray-700 px-4 py-1.5 rounded border border-gray-300 text-xs font-medium shadow-sm transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={async () => {
                            if (isSubmitting) return;
                            setIsSubmitting(true);
                            try {
                                await onConfirm(reason);
                            } finally {
                                setIsSubmitting(false);
                            }
                        }}
                        disabled={reason.trim().length === 0 || isSubmitting}
                        className={`px-4 py-1.5 rounded border text-xs font-medium shadow-sm transition-colors flex items-center gap-1.5 ${reason.trim().length === 0 || isSubmitting
                                ? 'bg-gray-300 text-gray-500 border-gray-400 cursor-not-allowed'
                                : 'bg-red-600 hover:bg-red-700 text-white border-red-700'
                            }`}
                    >
                        {isSubmitting ? (
                            <>
                                <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                </svg>
                                Breaking...
                            </>
                        ) : 'Confirm Break'}
                    </button>
                </div>
            </div>
        </div>
    );
}

