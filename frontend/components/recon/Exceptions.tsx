/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import React, { useState, useMemo } from 'react';
import { Pagination } from './Pagination';

interface ExceptionsProps {
    bankRecords?: any[];
    brokerRecords?: any[];
    batchId?: number | null;
    cashRecords?: any[];
    arRecords?: any[];
    cashApRecords?: any[];
    apRecords?: any[];
    stockRows?: any[];
    smaRows?: any[];
    smlRows?: any[];
}

type ReconTab = 'Bank' | 'CashAR' | 'CashAP' | 'StockPosition' | 'StockAcq' | 'StockLiq';

const TAB_LABELS: Record<ReconTab, string> = {
    Bank: 'Bank Recon',
    CashAR: 'Cash / AR',
    CashAP: 'Cash / AP',
    StockPosition: 'Stock Position',
    StockAcq: 'Stock Acquisition',
    StockLiq: 'Stock Liquidation',
};

export function Exceptions({
    bankRecords = [],
    brokerRecords = [],
    cashRecords = [],
    arRecords = [],
    cashApRecords = [],
    apRecords = [],
    stockRows = [],
    smaRows = [],
    smlRows = [],
}: ExceptionsProps) {
    const [activeTab, setActiveTab] = useState<ReconTab>('Bank');
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);

    // Reset page when tab changes
    const handleTabChange = (tab: ReconTab) => {
        setActiveTab(tab);
        setPage(1);
    };

    // ── Build manual match rows per tab ─────────────────────────────────────
    const rows = useMemo(() => {
        switch (activeTab) {
            case 'Bank': {
                // Bank recon: manual matches from bankRecords + brokerRecords
                const allRecords = [...bankRecords, ...brokerRecords];
                return allRecords
                    .filter(r => r.match_kind === 'MANUAL' || r.match_status === 'MANUAL_MATCH')
                    .map(r => ({
                        portfolio: r.PortfolioID || r.portfolio_id || '—',
                        date: r.Date || r.date || '—',
                        reference: r.Reference || r.reference_no || '—',
                        amount: r.Credit ? `+${r.Credit}` : (r.Debit ? `-${r.Debit}` : '0'),
                        reason: r.reason || '—',
                        source: r.PortfolioID ? (bankRecords.includes(r) ? 'Bank' : 'Broker') : '—',
                    }));
            }
            case 'CashAR': {
                const all = [...cashRecords, ...arRecords];
                return all
                    .filter(r => r.match_kind === 'MANUAL' || r.match_status === 'MANUAL_MATCH')
                    .map(r => ({
                        portfolio: r.PortfolioID || r.portfolio_id || '—',
                        date: r.Date || r.date || '—',
                        reference: r.Reference || r.reference_no || '—',
                        amount: r.Credit ? `+${r.Credit}` : (r.Debit ? `-${r.Debit}` : '0'),
                        reason: r.reason || '—',
                        source: cashRecords.includes(r) ? 'Cash' : 'AR',
                    }));
            }
            case 'CashAP': {
                const all = [...cashApRecords, ...apRecords];
                return all
                    .filter(r => r.match_kind === 'MANUAL' || r.match_status === 'MANUAL_MATCH')
                    .map(r => ({
                        portfolio: r.PortfolioID || r.portfolio_id || '—',
                        date: r.Date || r.date || '—',
                        reference: r.Reference || r.reference_no || '—',
                        amount: r.Credit ? `+${r.Credit}` : (r.Debit ? `-${r.Debit}` : '0'),
                        reason: r.reason || '—',
                        source: cashApRecords.includes(r) ? 'Cash' : 'AP',
                    }));
            }
            case 'StockPosition': {
                return stockRows
                    .filter(r => r.status === 'MATCHED' && r.match_kind === 'MANUAL')
                    .map(r => ({
                        portfolio: r.portfolio_id || '—',
                        symbol: r.symbol || '—',
                        scrip: r.scrip || '—',
                        stockName: r.stock_name || '—',
                        ssQty: r.ss_qty,
                        meroBalance: r.th_balance,
                        reason: r.reason || '—',
                        source: 'Stock Position',
                    }));
            }
            case 'StockAcq': {
                return smaRows
                    .filter(r => r.status === 'MATCHED' && r.match_kind === 'MANUAL')
                    .map(r => ({
                        portfolio: r.portfolio_id || '—',
                        scrip: r.scrip || '—',
                        stockName: r.stock_name || '—',
                        acqQty: r.acq_qty_sum,
                        meroQty: r.th_credit_qty_sum,
                        reason: r.reason || '—',
                        source: 'Stock Acquisition',
                    }));
            }
            case 'StockLiq': {
                return smlRows
                    .filter(r => r.status === 'MATCHED' && r.match_kind === 'MANUAL')
                    .map(r => ({
                        portfolio: r.portfolio_id || '—',
                        scrip: r.scrip || '—',
                        stockName: r.stock_name || '—',
                        liqQty: r.liq_qty_sum,
                        meroQty: r.th_debit_qty_sum,
                        reason: r.reason || '—',
                        source: 'Stock Liquidation',
                    }));
            }
            default:
                return [];
        }
    }, [activeTab, bankRecords, brokerRecords, cashRecords, arRecords, cashApRecords, apRecords, stockRows, smaRows, smlRows]);

    const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
    const paged = rows.slice((page - 1) * pageSize, page * pageSize);

    const isStockTab = ['StockPosition', 'StockAcq', 'StockLiq'].includes(activeTab);
    const isCashTab = ['Bank', 'CashAR', 'CashAP'].includes(activeTab);

    return (
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 h-full flex flex-col">
            {/* Header */}
            <div className="mb-4">
                <h2 className="text-gray-800 text-base font-bold tracking-tight">Manual Match</h2>
                <p className="text-gray-400 text-xs mt-0.5">All manually matched records across reconciliation types</p>
            </div>

            {/* Tab Navigation */}
            <div className="flex items-center gap-1 mb-4 border-b border-gray-200 flex-wrap">
                {(Object.keys(TAB_LABELS) as ReconTab[]).map(tab => (
                    <button
                        key={tab}
                        onClick={() => handleTabChange(tab)}
                        className={`px-3 py-2 text-xs font-medium rounded-t-lg transition-colors border-t border-x relative -mb-px ${activeTab === tab
                            ? 'bg-white text-blue-700 border-gray-200 border-b-transparent z-10'
                            : 'bg-gray-50 text-gray-500 border-transparent hover:text-gray-700'
                            }`}
                    >
                        {TAB_LABELS[tab]}
                        <span className="ml-1 text-[10px] opacity-60">
                            ({tab === 'Bank'
                                ? [...bankRecords, ...brokerRecords].filter(r => r.match_kind === 'MANUAL' || r.match_status === 'MANUAL_MATCH').length
                                : tab === 'CashAR'
                                    ? [...cashRecords, ...arRecords].filter(r => r.match_kind === 'MANUAL' || r.match_status === 'MANUAL_MATCH').length
                                    : tab === 'CashAP'
                                        ? [...cashApRecords, ...apRecords].filter(r => r.match_kind === 'MANUAL' || r.match_status === 'MANUAL_MATCH').length
                                        : tab === 'StockPosition'
                                            ? stockRows.filter(r => r.status === 'MATCHED' && r.match_kind === 'MANUAL').length
                                            : tab === 'StockAcq'
                                                ? smaRows.filter(r => r.status === 'MATCHED' && r.match_kind === 'MANUAL').length
                                                : smlRows.filter(r => r.status === 'MATCHED' && r.match_kind === 'MANUAL').length
                            })
                        </span>
                    </button>
                ))}
            </div>

            {/* Table Container */}
            <div className="flex-1 overflow-hidden flex flex-col min-h-0">
                <div className="flex-1 overflow-y-auto">
                    {paged.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                            <svg className="w-10 h-10 mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="text-sm font-medium">No manual matches found</p>
                            <p className="text-xs mt-1">Manual matches will appear here once created</p>
                        </div>
                    ) : isCashTab ? (
                        <table className="w-full text-xs border-collapse">
                            <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 z-10">
                                <tr>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Portfolio ID</th>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Reference</th>
                                    <th className="px-4 py-3 text-right font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Source</th>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Reason</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {paged.map((row: any, idx) => (
                                    <tr key={idx} className="hover:bg-gray-50 transition-colors">
                                        <td className="px-4 py-3 font-mono text-gray-800">{row.portfolio}</td>
                                        <td className="px-4 py-3 text-gray-600">{row.date}</td>
                                        <td className="px-4 py-3 font-mono text-gray-700">{row.reference}</td>
                                        <td className={`px-4 py-3 text-right font-mono font-medium ${row.amount?.startsWith('+') ? 'text-emerald-600' : 'text-red-600'}`}>{row.amount}</td>
                                        <td className="px-4 py-3">
                                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200">
                                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                                                Manual Match
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-gray-500 whitespace-normal leading-snug">{row.reason}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : (
                        <table className="w-full text-xs border-collapse">
                            <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 z-10">
                                <tr>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Portfolio ID</th>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Scrip</th>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Stock Name</th>
                                    {activeTab === 'StockPosition' && <>
                                        <th className="px-4 py-3 text-right font-semibold text-gray-500 uppercase tracking-wide">SS Qty</th>
                                        <th className="px-4 py-3 text-right font-semibold text-gray-500 uppercase tracking-wide">MERO Balance</th>
                                    </>}
                                    {activeTab === 'StockAcq' && <>
                                        <th className="px-4 py-3 text-right font-semibold text-gray-500 uppercase tracking-wide">Acq Qty</th>
                                        <th className="px-4 py-3 text-right font-semibold text-gray-500 uppercase tracking-wide">MERO Credit Qty</th>
                                    </>}
                                    {activeTab === 'StockLiq' && <>
                                        <th className="px-4 py-3 text-right font-semibold text-gray-500 uppercase tracking-wide">Liq Qty</th>
                                        <th className="px-4 py-3 text-right font-semibold text-gray-500 uppercase tracking-wide">MERO Debit Qty Sum</th>
                                    </>}
                                    <th className="px-4 py-3 text-center font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                                    <th className="px-4 py-3 text-left font-semibold text-gray-500 uppercase tracking-wide">Reason</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {paged.map((row: any, idx) => (
                                    <tr key={idx} className="hover:bg-gray-50 transition-colors">
                                        <td className="px-4 py-3 font-mono text-gray-800">{row.portfolio}</td>
                                        <td className="px-4 py-3 font-semibold text-gray-800">{row.scrip || row.symbol || '—'}</td>
                                        <td className="px-4 py-3 text-gray-600 max-w-[160px] truncate" title={row.stockName}>{row.stockName}</td>
                                        {activeTab === 'StockPosition' && <>
                                            <td className="px-4 py-3 text-right font-mono text-gray-700">{row.ssQty?.toLocaleString() ?? '—'}</td>
                                            <td className="px-4 py-3 text-right font-mono text-gray-700">{row.meroBalance?.toLocaleString() ?? '—'}</td>
                                        </>}
                                        {activeTab === 'StockAcq' && <>
                                            <td className="px-4 py-3 text-right font-mono text-gray-700">{row.acqQty?.toLocaleString() ?? '—'}</td>
                                            <td className="px-4 py-3 text-right font-mono text-gray-700">{row.meroQty?.toLocaleString() ?? '—'}</td>
                                        </>}
                                        {activeTab === 'StockLiq' && <>
                                            <td className="px-4 py-3 text-right font-mono text-gray-700">{row.liqQty?.toLocaleString() ?? '—'}</td>
                                            <td className="px-4 py-3 text-right font-mono text-gray-700">{row.meroQty?.toLocaleString() ?? '—'}</td>
                                        </>}
                                        <td className="px-4 py-3 text-center">
                                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200">
                                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                                                Manual Match
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-gray-500 whitespace-normal leading-snug">{row.reason}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {/* Pagination */}
                {rows.length > 0 && (
                    <Pagination
                        currentPage={page}
                        totalPages={totalPages}
                        pageSize={pageSize}
                        totalItems={rows.length}
                        onPageChange={setPage}
                        onPageSizeChange={(size) => { setPageSize(size); setPage(1); }}
                    />
                )}
            </div>
        </div>
    );
}
