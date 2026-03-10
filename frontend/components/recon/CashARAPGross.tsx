import React, { useState } from 'react';
import { SplitAllocationModal } from './SplitAllocationModal';
import { LinkCashARAPModal } from './LinkCashARAPModal';
import { DissolveMatchGroupModal } from './DissolveMatchGroupModal';
import { BreakMatchModal } from './BreakMatchModal';
import { CashARAPUploadModal } from './CashARAPUploadModal';
import { Pagination } from './Pagination';

interface CashARAPGrossProps {
    title?: string;
    filter?: 'AR' | 'AP';
    onAutoMatch?: () => Promise<boolean>;
    toleranceAmount?: number;
    dateWindowDays?: number;
}

export function CashARAPGross({ title = "Cash ↔ AR/AP (Gross)", filter, onAutoMatch, toleranceAmount, dateWindowDays }: CashARAPGrossProps) {
    const [subTab, setSubTab] = useState<'auto' | 'manual'>('auto');
    const [isSplitModalOpen, setIsSplitModalOpen] = useState(false);
    const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
    const [isDissolveModalOpen, setIsDissolveModalOpen] = useState(false);
    const [isBreakMatchModalOpen, setIsBreakMatchModalOpen] = useState(false);
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // Mock Data based on screenshot
    const allMockData = [
        {
            date: '2025-12-20',
            transactionName: 'Payment',
            cashRef: 'BANK-STAT-REF-1001',
            ledger: 'Cash',
            amount: '-₹1,00,000',
            counterLedger: 'Payable',
            counterRef: 'BILL-1001',
            status: 'matched',
            type: 'AP'
        },
        {
            date: '2025-12-21',
            transactionName: 'Receipt',
            cashRef: 'BANK-STAT-REF-1002',
            ledger: 'Cash',
            amount: '₹50,000',
            counterLedger: 'Receivable',
            counterRef: 'INV-1002',
            status: 'matched',
            type: 'AR'
        },
        {
            date: '2025-12-21',
            transactionName: 'Sales Charge Apply',
            cashRef: 'BANK-STAT-REF-1003',
            ledger: 'Cash',
            amount: '₹50,000',
            counterLedger: 'Broker Charges',
            counterRef: 'BRK-CHG-21',
            status: 'partial',
            type: 'AR'
        }
    ];

    const mockData = filter
        ? allMockData.filter(d => d.type === filter || (filter === 'AP' && d.counterLedger === 'Payable') || (filter === 'AR' && (d.counterLedger === 'Receivable' || d.counterLedger === 'Broker Charges')))
        : allMockData;

    const handleSplitClick = () => setIsSplitModalOpen(true);
    const handleLinkClick = () => setIsLinkModalOpen(true);
    const handleDissolveClick = () => setIsDissolveModalOpen(true);
    const handleBreakMatchClick = () => setIsBreakMatchModalOpen(true);

    const handleCloseModal = () => {
        setIsSplitModalOpen(false);
        setIsLinkModalOpen(false);
        setIsDissolveModalOpen(false);
        setIsBreakMatchModalOpen(false);
        setIsUploadModalOpen(false);
    };

    const handleConfirmSplit = () => { console.log("Split confirmed!"); handleCloseModal(); };
    const handleConfirmLink = () => { console.log("Link confirmed!"); handleCloseModal(); };
    const handleConfirmDissolve = () => { console.log("Dissolve confirmed!"); handleCloseModal(); };
    const handleConfirmBreakMatch = () => { console.log("Break Match confirmed!"); handleCloseModal(); };

    const [isProcessing, setIsProcessing] = useState(false);

    const handleUploadCash = (file: File) => console.log("Cash uploaded", file);
    const handleUploadAR = (file: File) => console.log("AR uploaded", file);
    const handleUploadAP = (file: File) => console.log("AP uploaded", file);
    const handleAutoRecon = async () => {
        if (onAutoMatch) {
            setIsProcessing(true);
            try {
                await onAutoMatch();
            } finally {
                setIsProcessing(false);
            }
        }
        setIsUploadModalOpen(false);
    };

    return (
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 h-fit">
            {/* Top Sub-tabs/Controls */}
            <div className="flex gap-2 mb-4 items-center justify-between">
                <h2 className="text-lg font-bold text-gray-800 uppercase tracking-wide">{title}</h2>
                <div className="flex gap-2">
                    <button
                        onClick={() => setIsUploadModalOpen(true)}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold py-1.5 px-3 rounded shadow-sm transition-colors uppercase tracking-wider"
                    >
                        Upload Files
                    </button>
                </div>
            </div>

            {/* Data Table */}
            <div className="flex-1 overflow-hidden flex flex-col min-h-0">
                <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent">
                    <table className="w-full text-left border-collapse text-[11px]">
                        <thead className="sticky top-0 z-10 bg-gray-50 border-b border-gray-200">
                            <tr>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Date</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Transaction Name</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Cash Ledger Reference</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Ledger</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-right whitespace-nowrap">Amount</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Counter Ledger</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Counter Ledger Ref</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-center whitespace-nowrap">Status</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-center whitespace-nowrap">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {mockData.map((row, idx) => (
                                <tr key={idx} className="hover:bg-gray-50 transition-colors group">
                                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{row.date}</td>
                                    <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">{row.transactionName}</td>
                                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{row.cashRef}</td>
                                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{row.ledger}</td>
                                    <td className={`px-4 py-3 font-mono font-medium text-right whitespace-nowrap ${row.amount.startsWith('-') ? 'text-red-600' : 'text-emerald-600'}`}>{row.amount}</td>
                                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{row.counterLedger}</td>
                                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{row.counterRef}</td>
                                    <td className="px-4 py-3 text-center">
                                        <span className={`uppercase font-bold tracking-wide text-[10px] inline-flex items-center justify-center h-5 px-2 rounded disabled:opacity-50 ${row.status === 'matched'
                                            ? 'bg-green-100 text-green-700'
                                            : 'bg-yellow-100 text-yellow-700'
                                            }`}>
                                            {row.status}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        <div className="flex flex-col gap-1.5">
                                            <div className="flex gap-1.5 justify-center">
                                                <button onClick={handleSplitClick} className="px-2 py-0.5 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 rounded text-[10px] font-semibold border border-indigo-200 transition-colors">Split</button>
                                                <button onClick={handleLinkClick} className="px-2 py-0.5 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded text-[10px] font-semibold border border-blue-200 transition-colors">Link</button>
                                            </div>
                                            <div className="flex gap-1.5 justify-center">
                                                <button onClick={handleDissolveClick} className="px-2 py-0.5 bg-gray-50 text-gray-600 hover:bg-gray-100 rounded text-[10px] font-semibold border border-gray-200 transition-colors">Dissolve</button>
                                                <button onClick={handleBreakMatchClick} className="px-2 py-0.5 bg-red-50 text-red-600 hover:bg-red-100 rounded text-[10px] font-semibold border border-red-200 transition-colors">Break</button>
                                            </div>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                {mockData.length > 0 && (
                    <Pagination
                        currentPage={currentPage}
                        totalPages={Math.ceil(mockData.length / pageSize)}
                        pageSize={pageSize}
                        totalItems={mockData.length}
                        onPageChange={setCurrentPage}
                        onPageSizeChange={(size) => {
                            setPageSize(size);
                            setCurrentPage(1);
                        }}
                    />
                )}
            </div>

            <div className="mt-4 text-[10px] text-gray-400 italic">
                Columns added: Cash Ledger Reference and Counter Ledger Reference. Actions column includes Split, Link, Dissolve, Break Match.
            </div>

            {/* Modals */}
            <SplitAllocationModal isOpen={isSplitModalOpen} onClose={handleCloseModal} onConfirm={handleConfirmSplit} />
            <LinkCashARAPModal isOpen={isLinkModalOpen} onClose={handleCloseModal} onConfirm={handleConfirmLink} />
            <DissolveMatchGroupModal isOpen={isDissolveModalOpen} onClose={handleCloseModal} onConfirm={handleConfirmDissolve} />
            <BreakMatchModal isOpen={isBreakMatchModalOpen} onClose={handleCloseModal} onConfirm={handleConfirmBreakMatch} />
            <CashARAPUploadModal
                isOpen={isUploadModalOpen}
                onClose={() => setIsUploadModalOpen(false)}
                onCashLedgerUpload={handleUploadCash}
                onARUpload={handleUploadAR}
                onAPUpload={handleUploadAP}
                onAutoMatch={handleAutoRecon}
                isUploading={false}
                isProcessing={isProcessing}
                showAr={!filter || filter === 'AR'}
                showAp={!filter || filter === 'AP'}
            />
        </div>
    );
}
