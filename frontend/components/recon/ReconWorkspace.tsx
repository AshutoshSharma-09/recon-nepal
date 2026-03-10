
import React from 'react';
import { TransactionGrid, Transaction } from './TransactionGrid';

interface ReconWorkspaceProps {
    bankRecords: Transaction[];
    brokerRecords: Transaction[];
    summary: any;
    onReset: () => void;
}

export function ReconWorkspace({ bankRecords, brokerRecords, summary, onReset }: ReconWorkspaceProps) {
    return (
        <div className="flex flex-col h-screen max-h-[calc(100vh-100px)]">
            {/* Header / Toolbar */}
            <div className="flex items-center justify-between p-4 mb-4 bg-white border rounded-lg shadow-sm">
                <div className="flex gap-6">
                    <div>
                        <h2 className="text-xl font-bold">Reconciliation Workspace</h2>
                        <p className="text-sm text-gray-500">
                            Match Status:
                            <span className="ml-2 text-green-600 font-medium">
                                {summary.matched_bank + summary.matched_broker} Matched
                            </span>
                            <span className="mx-2 text-gray-300">|</span>
                            <span className="text-red-600 font-medium">
                                {summary.unmatched_bank + summary.unmatched_broker} Unmatched
                            </span>
                        </p>
                    </div>
                </div>

                <div className="flex gap-3">
                    <button
                        onClick={onReset}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                        Upload New Files
                    </button>
                    <button className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
                        Export Report
                    </button>
                </div>
            </div>

            {/* Dual Pane Grid */}
            <div className="flex-1 grid grid-cols-2 gap-4 min-h-0">
                <TransactionGrid title="Bank Statement" transactions={bankRecords} type="bank" />
                <TransactionGrid title="Broker Ledger" transactions={brokerRecords} type="broker" />
            </div>
        </div>
    );
}
