
import React from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export interface Transaction {
    Date: string;
    PortfolioID?: string;
    Reference?: string;
    Description: string;
    Debit?: number;
    Credit?: number;
    Balance?: number;
    status: string;
    match_id?: string;
    [key: string]: any;
}

interface TransactionGridProps {
    title: string;
    transactions: Transaction[];
    type: 'bank' | 'broker';
}

export function TransactionGrid({ title, transactions, type }: TransactionGridProps) {
    const isBank = type === 'bank';

    return (
        <div className="flex flex-col h-full border rounded-lg bg-white shadow-sm overflow-hidden">
            <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
                <h3 className="font-semibold text-lg">{title}</h3>
                <span className="text-sm text-gray-500">{transactions.length} records</span>
            </div>

            <div className="flex-1 overflow-auto">
                <table className="w-full text-sm text-left">
                    <thead className="text-xs text-gray-700 uppercase bg-gray-50 sticky top-0 z-10">
                        <tr>
                            <th className="px-4 py-3">Date</th>
                            <th className="px-4 py-3">Portfolio ID</th>
                            <th className="px-4 py-3">Description</th>
                            <th className="px-4 py-3 text-right">Debit</th>
                            <th className="px-4 py-3 text-right">Credit</th>
                            <th className="px-4 py-3 text-center">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {transactions.map((txn, idx) => {
                            const amountClass = "font-medium";
                            const isMatched = txn.status === 'Matched';

                            return (
                                <tr
                                    key={idx}
                                    className={cn(
                                        "border-b hover:bg-gray-50 transition-colors",
                                        isMatched ? "bg-green-50/30" : ""
                                    )}
                                >
                                    <td className="px-4 py-2 whitespace-nowrap text-gray-600">
                                        {new Date(txn.Date).toLocaleDateString()}
                                    </td>
                                    <td className="px-4 py-2 whitespace-nowrap font-medium text-gray-700">
                                        {txn.PortfolioID || txn.portfolio_id || '-'}
                                    </td>
                                    <td className="px-4 py-2 max-w-[200px] truncate" title={txn.Description || txn.Particulars}>
                                        {txn.Description || txn.Particulars}
                                        {txn.Reference && (
                                            <div className="text-xs text-gray-400 mt-0.5">{txn.Reference}</div>
                                        )}
                                    </td>
                                    <td className={cn("px-4 py-2 text-right text-red-600", amountClass)}>
                                        {txn.Debit ? Number(txn.Debit).toLocaleString(undefined, { minimumFractionDigits: 2 }) : '-'}
                                    </td>
                                    <td className={cn("px-4 py-2 text-right text-green-600", amountClass)}>
                                        {txn.Credit ? Number(txn.Credit).toLocaleString(undefined, { minimumFractionDigits: 2 }) : '-'}
                                    </td>
                                    <td className="px-4 py-2 text-center">
                                        <span className={cn(
                                            "px-2 py-1 rounded-full text-xs font-semibold",
                                            isMatched ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                                        )}>
                                            {txn.status}
                                        </span>
                                    </td>
                                </tr>
                            );
                        })}

                        {transactions.length === 0 && (
                            <tr>
                                <td colSpan={6} className="p-8 text-center text-gray-400">No transactions found</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
