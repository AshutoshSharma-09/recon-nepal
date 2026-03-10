import React from 'react';

interface LinkCashARAPModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
}

export function LinkCashARAPModal({ isOpen, onClose, onConfirm }: LinkCashARAPModalProps) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
            <div className="bg-[#e2e8f0] rounded-lg shadow-xl w-[400px] p-4 font-sans text-sm text-gray-800 border border-gray-300">

                {/* Header */}
                <h3 className="font-bold text-lg text-black mb-2">Link Cash ↔ AR/AP</h3>

                {/* Close Button (Top Left per screenshot) */}
                <button
                    onClick={onClose}
                    className="bg-[#d1d5db] hover:bg-[#9ca3af] text-black px-2 py-0.5 rounded border border-gray-400 text-xs mb-3 shadow-sm transition-colors"
                >
                    Close
                </button>

                {/* Form Fields */}
                <div className="space-y-2">
                    <div className="flex flex-col">
                        <label className="text-black text-xs mb-0.5">Cash Txn</label>
                        <input type="text" className="w-full border border-gray-400 rounded px-2 py-1 bg-white focus:outline-blue-500 shadow-inner" readOnly />
                    </div>

                    <div className="flex flex-col">
                        <label className="text-black text-xs mb-0.5">AR/AP Item</label>
                        <input type="text" className="w-full border border-gray-400 rounded px-2 py-1 bg-white focus:outline-blue-500 shadow-inner" readOnly />
                    </div>

                    <div className="flex flex-col">
                        <label className="text-black text-xs mb-0.5">Match Amount (₹)</label>
                        <input type="text" placeholder="0.00" className="w-full border border-gray-400 rounded px-2 py-1 bg-white focus:outline-blue-500 shadow-inner" />
                    </div>

                    <div className="flex flex-col">
                        <label className="text-black text-xs mb-0.5">Reference (optional)</label>
                        <input type="text" placeholder="e.g.," className="w-full border border-gray-400 rounded px-2 py-1 bg-white focus:outline-blue-500 shadow-inner" />
                    </div>

                    <div className="flex flex-col">
                        <label className="text-black text-xs mb-0.5">Reason / Notes</label>
                        <textarea
                            placeholder="Any"
                            className="w-full border border-gray-400 rounded px-2 py-1 bg-white focus:outline-blue-500 shadow-inner h-16 resize-none"
                        />
                    </div>
                </div>

                {/* Tip */}
                <div className="mt-2 text-[11px] text-gray-800">
                    Tip: Press Enter to confirm or Esc to close.
                </div>

                {/* Footer Buttons */}
                <div className="flex gap-2 mt-3">
                    <button
                        onClick={onClose}
                        className="bg-[#d1d5db] hover:bg-[#9ca3af] text-black px-3 py-1 rounded border border-gray-400 text-xs shadow-sm transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        className="bg-[#d1d5db] hover:bg-[#9ca3af] text-black px-3 py-1 rounded border border-gray-400 text-xs shadow-sm transition-colors"
                    >
                        Confirm Link
                    </button>
                </div>
            </div>
        </div>
    );
}
