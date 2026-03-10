import React from 'react';
import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react';

interface DashboardCardProps {
    title: string;
    count?: number | string;
    description: string;
    subtext?: string;
    isActive?: boolean;
    variant?: 'default' | 'success' | 'danger' | 'warning';
}

function DashboardCard({ title, count, description, subtext, isActive, variant = 'default' }: DashboardCardProps) {
    const getBgColor = () => {
        // Updated as per user feedback: variant colors should persist.
        // Using stronger background classes without opacity slash syntax to ensure Tailwind picks them up safely.
        switch (variant) {
            case 'success': return 'bg-emerald-50 border-emerald-100';
            case 'danger': return 'bg-red-50 border-red-100';
            case 'warning': return 'bg-orange-50 border-orange-100';
            default: return 'bg-white border-gray-100';
        }
    };

    const getIcon = () => {
        switch (variant) {
            case 'success': return <ShieldCheck className="w-5 h-5 text-emerald-500 fill-emerald-100" />;
            case 'danger': return <ShieldAlert className="w-5 h-5 text-red-500 fill-red-100" />;
            case 'warning': return <ShieldX className="w-5 h-5 text-orange-500 fill-orange-100" />;
            default: return null;
        }
    };

    const bgColorClasses = getBgColor();
    const icon = getIcon();

    return (
        <div className={`p-5 rounded-xl flex flex-col transition-all duration-200 border ${bgColorClasses} ${isActive
            ? 'shadow-[0_8px_30px_rgba(0,0,0,0.12)] ring-1 ring-blue-100'
            : 'shadow-[0_4px_20px_-4px_rgba(0,0,0,0.08)] hover:shadow-[0_8px_30px_rgba(0,0,0,0.12)]'
            }`}>
            <div className="flex justify-between items-start mb-3">
                <h3 className="text-[#111827] font-medium text-[15px]">{title}</h3>
                {icon && <div>{icon}</div>}
            </div>
            {count !== undefined && <div className="text-[#111827] text-3xl font-bold tracking-tight mb-2">{count}</div>}
            <p className="text-[#6B7280] text-[13px] font-normal leading-relaxed">{description}</p>
            {subtext && <p className="text-gray-400 text-[11px] mt-2 leading-snug">{subtext}</p>}
        </div>
    );
}

interface DashboardCardsProps {
    summary: {
        total_matches: number;
        auto_match_count?: number;
        manual_match_count?: number;
        unmatched_broker: number;
        unmatched_bank: number;
        exceptions: number;
    } | null;
}

export function DashboardCards({ summary }: DashboardCardsProps) {
    const totalUnmatched = (summary as any)?.unmatched_count ?? ((summary?.unmatched_broker || 0) + (summary?.unmatched_bank || 0));
    const exceptions = (summary as any)?.exception_count ?? (summary?.exceptions || 0);
    const totalMatches = summary?.total_matches || 0;

    const totalRecords = totalMatches + totalUnmatched + exceptions;
    const matchPercentage = totalRecords > 0 ? ((totalMatches / totalRecords) * 100).toFixed(1) : "0.0";

    return (
        <div className="grid grid-cols-4 gap-4 mb-6">
            <DashboardCard
                title="Overview"
                count={`${matchPercentage}%`}
                description="Match Success Rate"
                isActive={false}
                variant="default"
            />
            <DashboardCard
                title="Matched"
                count={totalMatches}
                description={`Auto: ${summary?.auto_match_count ?? '-'} | Manual: ${summary?.manual_match_count ?? '-'}`}
                isActive={true}
                variant="success"
            />
            <DashboardCard
                title="Unmatched"
                count={totalUnmatched}
                description="Need review"
                isActive={false}
                variant="danger"
            />
            <DashboardCard
                title="Exceptions"
                count={exceptions}
                description="Invalid Date/Ref/Amt"
                isActive={false}
                variant="warning"
            />
        </div>
    );
}
