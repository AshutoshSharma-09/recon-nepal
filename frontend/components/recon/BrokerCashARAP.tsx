import React, { useState } from 'react';
import { BrokerCashUploadModal } from './BrokerCashUploadModal';
import { Pagination } from './Pagination';

interface BrokerCashARAPProps {
    title?: string;
    onAutoMatch?: () => Promise<boolean>;
    toleranceAmount?: number;
    dateWindowDays?: number;
}

export function BrokerCashARAP({ title = "Broker ↔ Cash/AR/AP", onAutoMatch, toleranceAmount, dateWindowDays }: BrokerCashARAPProps) {
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // Mock handlers
    const handleUpload = (file: File) => console.log('Upload:', file.name);
    const handleAutoMatch = async () => {
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

    // Mock Data based on screenshot
    const mockData = [
        {
            type: 'Purchase',
            brokerRef: 'BRK-NET-DEC20',
            grossComponent: 'Payable',
            ledger: 'AP',
            amount: '-50,000',
            status: 'mapped',
        },
        {
            type: 'Sale',
            brokerRef: 'BRK-SALE-DEC21',
            grossComponent: 'Receivable',
            ledger: 'AR',
            amount: '50,000',
            status: 'mapped',
        },
        {
            type: 'Sale',
            brokerRef: 'BRK-SALE-DEC21',
            grossComponent: 'Charges',
            ledger: 'Charges',
            amount: '-250',
            status: 'mapped',
        }
    ];

    return (
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 h-fit">
            {/* Header / Title Bar */}
            <div className="flex items-center justify-between mb-4">
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
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Type</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Broker Ref</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Gross Component</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-left whitespace-nowrap">Ledger</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-right whitespace-nowrap">Amount</th>
                                <th className="px-4 py-3 font-medium text-gray-500 uppercase tracking-wide text-center whitespace-nowrap">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {mockData.map((row, idx) => (
                                <tr key={idx} className="hover:bg-gray-50 transition-colors group">
                                    <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">{row.type}</td>
                                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{row.brokerRef}</td>
                                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{row.grossComponent}</td>
                                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{row.ledger}</td>
                                    <td className={`px-4 py-3 font-medium text-right whitespace-nowrap ${row.amount.startsWith('-') ? 'text-red-600' : 'text-emerald-600'}`}>₹{row.amount}</td>
                                    <td className="px-4 py-3 text-center">
                                        <span className={`uppercase font-bold tracking-wide text-[10px] inline-flex items-center justify-center h-6 px-3 rounded shadow-sm min-w-[90px] ${row.status === 'mapped' ? 'bg-[#22c55e] text-white border border-green-500/30' : 'bg-gray-200 text-gray-700'
                                            }`}>
                                            {row.status}
                                        </span>
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
            {/* Upload Modal */}
            <BrokerCashUploadModal
                isOpen={isUploadModalOpen}
                onClose={() => setIsUploadModalOpen(false)}
                onBrokerLedgerUpload={handleUpload}
                onCashLedgerUpload={handleUpload}
                onARUpload={handleUpload}
                onAPUpload={handleUpload}
                onAutoMatch={handleAutoMatch}
                isUploading={false}
                isProcessing={isProcessing}
                showAr={false}
                showAp={false}
            />
        </div>
    );
}
