import React, { useMemo, useState } from 'react';
import { X, AlertCircle } from 'lucide-react';

interface ManualMatchModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (note?: string) => void;
    selectedBankRows: any[];
    selectedBrokerRows: any[];
}

export function ManualMatchModal({ isOpen, onClose, onConfirm, selectedBankRows, selectedBrokerRows }: ManualMatchModalProps) {
    const [note, setNote] = useState('');

    if (!isOpen) return null;

    // Calculate Totals using absolute values
    const totalBank = useMemo(() =>
        selectedBankRows.reduce((sum, r) => sum + Math.abs(parseFloat(r.rawBank?.amount_signed || 0)), 0),
        [selectedBankRows]
    );

    const totalBroker = useMemo(() =>
        selectedBrokerRows.reduce((sum, r) => sum + Math.abs(parseFloat(r.rawBroker?.amount_signed || 0)), 0),
        [selectedBrokerRows]
    );

    const diff = Math.abs(totalBank - totalBroker);
    const isMatchable = diff < 0.05; // Tolerance

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
            <div className="bg-white rounded-lg shadow-xl w-[700px] overflow-hidden font-sans text-sm text-gray-800 flex flex-col max-h-[90vh]">
                {/* Header */}
                <div className="px-5 py-3 border-b border-gray-200 flex justify-between items-center bg-gray-50">
                    <div>
                        <h3 className="font-bold text-base text-gray-800">Manual Match / Split</h3>
                        <p className="text-[10px] text-gray-500">Select multiple items on one side to perform a split match.</p>
                    </div>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-5 overflow-y-auto">

                    <div className="grid grid-cols-2 gap-4 h-full">
                        {/* Bank Side */}
                        <div className="flex flex-col h-full border rounded-md overflow-hidden">
                            <div className="bg-blue-50 px-3 py-2 border-b font-semibold text-blue-800 flex justify-between text-xs">
                                <span>Bank Selected ({selectedBankRows.length})</span>
                                <span>Total: {totalBank.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}</span>
                            </div>
                            <div className="p-2 space-y-2 overflow-y-auto max-h-[200px] bg-gray-50/50 flex-1">
                                {selectedBankRows.map((row, idx) => (
                                    <div key={idx} className="bg-white p-2 rounded border border-gray-200 text-xs shadow-sm flex flex-col gap-1">
                                        <div className="flex justify-between font-medium">
                                            <span>{row.bankRef}</span>
                                            <span className={parseFloat(row.rawBank.amount_signed) < 0 ? 'text-red-600' : 'text-green-600'}>
                                                {parseFloat(row.rawBank.amount_signed) < 0 ? '-' : '+'}{Math.abs(parseFloat(row.rawBank.amount_signed)).toLocaleString()}
                                            </span>
                                        </div>
                                        <div className="text-[10px] text-gray-400">{row.bankDate} | {row.bankPortfolio}</div>
                                    </div>
                                ))}
                                {selectedBankRows.length === 0 && <div className="text-center text-gray-400 py-4 italic">No Bank items selected</div>}
                            </div>
                        </div>

                        {/* Broker Side */}
                        <div className="flex flex-col h-full border rounded-md overflow-hidden">
                            <div className="bg-indigo-50 px-3 py-2 border-b font-semibold text-indigo-800 flex justify-between text-xs">
                                <span>Broker Selected ({selectedBrokerRows.length})</span>
                                <span>Total: {totalBroker.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}</span>
                            </div>
                            <div className="p-2 space-y-2 overflow-y-auto max-h-[200px] bg-gray-50/50 flex-1">
                                {selectedBrokerRows.map((row, idx) => (
                                    <div key={idx} className="bg-white p-2 rounded border border-gray-200 text-xs shadow-sm flex flex-col gap-1">
                                        <div className="flex justify-between font-medium">
                                            <span>{row.brokerRef}</span>
                                            <span className={parseFloat(row.rawBroker.amount_signed) < 0 ? 'text-red-600' : 'text-green-600'}>
                                                {parseFloat(row.rawBroker.amount_signed) < 0 ? '-' : '+'}{Math.abs(parseFloat(row.rawBroker.amount_signed)).toLocaleString()}
                                            </span>
                                        </div>
                                        <div className="text-[10px] text-gray-400">{row.brokerDate} | {row.brokerPortfolio}</div>
                                    </div>
                                ))}
                                {selectedBrokerRows.length === 0 && <div className="text-center text-gray-400 py-4 italic">No Broker items selected</div>}
                            </div>
                        </div>
                    </div>

                    {/* Summary & Note */}
                    <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
                        <div className={`flex items-center gap-2 p-3 rounded-md border ${isMatchable ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                            {isMatchable ? (
                                <div className="flex-1 flex justify-between items-center text-green-800 font-medium">
                                    <span className="flex items-center gap-2">✅ Amounts Match!</span>
                                    <span>Diff: ₹{diff.toFixed(2)}</span>
                                </div>
                            ) : (
                                <div className="flex-1 flex justify-between items-center text-red-800 font-medium">
                                    <span className="flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Amounts Mismatch</span>
                                    <span>Diff: ₹{diff.toFixed(2)}</span>
                                </div>
                            )}
                        </div>

                        <div>
                            <label className="block text-gray-500 text-[10px] mb-1">Reason / Note (optional)</label>
                            <textarea
                                className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs text-gray-700 h-[60px] resize-none focus:outline-blue-500"
                                placeholder="e.g., Split match for bulk settlement"
                                value={note}
                                onChange={(e) => setNote(e.target.value)}
                            />
                        </div>
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
                        disabled={!isMatchable || (selectedBankRows.length === 0 && selectedBrokerRows.length === 0)}
                        onClick={() => onConfirm(note)}
                        className={`px-4 py-1.5 text-white font-medium rounded text-xs transition-colors shadow-sm ${!isMatchable
                            ? 'bg-gray-400 cursor-not-allowed'
                            : 'bg-[#4f46e5] hover:bg-[#4338ca]'}`}
                    >
                        Confirm Match & Split
                    </button>
                </div>
            </div>
        </div>
    );
}
