import React from 'react';

interface DashboardStatsProps {
    summary: {
        total_matches: number;
        auto_match_count?: number;
        manual_match_count?: number;
        unmatched_broker: number;
        unmatched_bank: number;
        exceptions: number;
        unmatched_count?: number;
        exception_count?: number;
    } | null;
}

export function DashboardStats({ summary }: DashboardStatsProps) {
    const totalUnmatched = summary?.unmatched_count ?? ((summary?.unmatched_broker || 0) + (summary?.unmatched_bank || 0));
    const totalExceptions = summary?.exception_count ?? (summary?.exceptions || 0);

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs font-medium w-full mt-2 sm:mt-0">
            <div className="bg-[#3b82f6]/20 px-4 py-2 rounded-md text-blue-50 border border-blue-400/20 backdrop-blur-md shadow-sm hover:bg-[#3b82f6]/30 transition-all flex items-center justify-center sm:justify-start">
                Bank Payments: ₹--
            </div>
            <div className="bg-[#3b82f6]/20 px-4 py-2 rounded-md text-blue-50 border border-blue-400/20 backdrop-blur-md shadow-sm hover:bg-[#3b82f6]/30 transition-all flex items-center justify-center sm:justify-start">
                Bank Receipts: ₹--
            </div>
            <div className="bg-[#3b82f6]/20 px-4 py-2 rounded-md text-blue-50 border border-blue-400/20 backdrop-blur-md shadow-sm hover:bg-[#3b82f6]/30 transition-all flex items-center justify-center sm:justify-start">
                Matched: {summary?.total_matches || 0}
            </div>
            <div className="bg-[#3b82f6]/20 px-4 py-2 rounded-md text-blue-50 border border-blue-400/20 backdrop-blur-md shadow-sm hover:bg-[#3b82f6]/30 transition-all flex items-center justify-center sm:justify-start">
                Exceptions: {totalExceptions}
            </div>
            <div className="bg-[#3b82f6]/20 px-4 py-2 rounded-md text-blue-50 border border-blue-400/20 backdrop-blur-md shadow-sm hover:bg-[#3b82f6]/30 transition-all flex items-center justify-center sm:justify-start">
                Unmatched: {totalUnmatched}
            </div>
        </div>
    );
}
