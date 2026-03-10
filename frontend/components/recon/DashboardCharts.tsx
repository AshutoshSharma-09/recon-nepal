
import React from 'react';
import {
    PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Sector
} from 'recharts';

interface DashboardChartsProps {
    summary: {
        total_matches: number;
        auto_match_count?: number;
        manual_match_count?: number;
        unmatched_broker: number;
        unmatched_bank: number;
        exceptions: number;
    } | null;
}

export function DashboardCharts({ summary }: DashboardChartsProps) {
    // State for interactive Pie Chart
    const [activeIndex, setActiveIndex] = React.useState(-1);

    const onPieEnter = (_: any, index: number) => {
        setActiveIndex(index);
    };

    // Premium Enterprise Color Palette with Gradients - Rich & Aesthetic
    const colors = {
        matched: 'url(#gradient-matched)',
        unmatched: 'url(#gradient-unmatched)',
        auto: 'url(#gradient-auto)',
        partial: 'url(#gradient-partial)',
        exception: 'url(#gradient-exception)',
        grid: '#e2e8f0', // Light slate
        text: '#64748b', // Slate 500
    };

    // Solid colors for Legend matching the aesthetic palette
    const legendColors = {
        auto: '#3b82f6',       // Blue 500
        exception: '#a855f7',  // Purple 500
        matched: '#10b981',    // Emerald 500 (More soothing than pure green)
        partial: '#f59e0b',    // Amber 500
        unmatched: '#f43f5e',  // Rose 500 (More soothing than pure red)
        grid: '#e2e8f0',
    };

    const totalUnmatched = (summary as any)?.unmatched_count ?? ((summary?.unmatched_broker || 0) + (summary?.unmatched_bank || 0));
    const totalExceptions = (summary as any)?.exception_count ?? (summary?.exceptions || 0);

    // Dynamic Data for Pie Chart
    const autoMatches = (summary as any)?.auto_match_count ?? (summary?.total_matches || 0);
    const manualMatches = (summary as any)?.manual_match_count ?? 0;

    // Fallback logic specific to legacy backend if needed, but backend is updated now.

    const pieData = [
        { name: 'Auto-Matched', value: autoMatches, color: colors.auto, legendColor: legendColors.auto },
        { name: 'Manual Match', value: manualMatches, color: colors.matched, legendColor: legendColors.matched },
        { name: 'Exception', value: totalExceptions, color: colors.exception, legendColor: legendColors.exception },
        { name: 'Unmatched', value: totalUnmatched, color: colors.unmatched, legendColor: legendColors.unmatched },
        { name: 'Partial', value: 0, color: colors.partial, legendColor: legendColors.partial },
    ].filter(d => d.value > 0 || d.name === 'Manual Match' || d.name === 'Partial');

    // Check if we have any data
    const hasData = pieData.some(d => d.value > 0);
    const activePieData = hasData ? pieData.filter(d => d.value > 0) : [];

    // Current Month Index
    const currentMonthIndex = new Date().getMonth();

    // Mock Data for Line Chart (12 Months) - initialized with 0
    const initialLineData = [
        { name: 'Jan', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Feb', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Mar', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Apr', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'May', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Jun', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Jul', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Aug', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Sep', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Oct', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Nov', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
        { name: 'Dec', matched: 0, auto: 0, unmatched: 0, partial: 0, exception: 0 },
    ];

    // Merge Summary Data into Current Month
    const lineData = initialLineData.map((d, index) => {
        if (summary && index === currentMonthIndex) {
            return {
                name: d.name,
                matched: manualMatches,
                auto: autoMatches,
                unmatched: totalUnmatched,
                partial: 0,
                exception: totalExceptions
            };
        }
        return d;
    });

    // Mock Data with gradient fill support in future if needed (currently solid lines)
    return (
        <div className="flex flex-col lg:flex-row gap-4 w-full h-auto lg:h-[340px] mt-4 font-sans">
            {/* Pie Chart Section */}
            <div className="w-full lg:w-[35%] h-[300px] lg:h-full bg-white rounded-xl p-5 border border-gray-200 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.08)] flex flex-col relative overflow-hidden">
                <h3 className="text-[#111827] text-sm font-semibold tracking-wide mb-1">Pass Rate Distribution</h3>
                <p className="text-[#6B7280] text-[10px] mb-4 uppercase tracking-wider">Current Month Overview</p>
                <div className="flex-1 min-h-0 relative flex items-center justify-center">
                    {!hasData ? (
                        <div className="flex flex-col items-center justify-center text-center opacity-70">
                            <div className="w-24 h-24 rounded-full border-4 border-slate-100 flex items-center justify-center mb-3">
                                <span className="text-2xl grayscale opacity-50">📊</span>
                            </div>
                            <p className="text-gray-500 text-sm font-medium">No Reconciliation Data</p>
                            <p className="text-gray-400 text-[10px] uppercase tracking-wide mt-1">Upload files to see analysis</p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                            <PieChart>
                                <defs>
                                    <filter id="pie-glow" x="-20%" y="-20%" width="140%" height="140%">
                                        <feGaussianBlur stdDeviation="2" result="blur" />
                                        <feComposite in="SourceGraphic" in2="blur" operator="over" />
                                    </filter>
                                    {/* Glossy Gradients - Rich & Aesthetic */}
                                    <linearGradient id="gradient-matched" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#10b981" /> {/* Emerald 500 */}
                                        <stop offset="100%" stopColor="#059669" /> {/* Emerald 600 */}
                                    </linearGradient>
                                    <linearGradient id="gradient-unmatched" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#f43f5e" /> {/* Rose 500 */}
                                        <stop offset="100%" stopColor="#e11d48" /> {/* Rose 600 */}
                                    </linearGradient>
                                    <linearGradient id="gradient-auto" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#3b82f6" /> {/* Blue 500 */}
                                        <stop offset="100%" stopColor="#2563eb" /> {/* Blue 600 */}
                                    </linearGradient>
                                    <linearGradient id="gradient-partial" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#f59e0b" /> {/* Amber 500 */}
                                        <stop offset="100%" stopColor="#d97706" /> {/* Amber 600 */}
                                    </linearGradient>
                                    <linearGradient id="gradient-exception" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#a855f7" /> {/* Purple 500 */}
                                        <stop offset="100%" stopColor="#9333ea" /> {/* Purple 600 */}
                                    </linearGradient>
                                </defs>
                                <Pie
                                    data={activePieData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={0}
                                    outerRadius={85}
                                    dataKey="value"
                                    stroke="none"
                                    onMouseEnter={onPieEnter}
                                    // @ts-ignore
                                    activeIndex={activeIndex}
                                    activeShape={(props: any) => {
                                        const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props;
                                        return (
                                            <g>
                                                <Sector
                                                    cx={cx}
                                                    cy={cy}
                                                    innerRadius={innerRadius}
                                                    outerRadius={outerRadius + 8} // Expand effect
                                                    startAngle={startAngle}
                                                    endAngle={endAngle}
                                                    fill={fill}
                                                    style={{ filter: 'drop-shadow(0px 4px 8px rgba(0,0,0,0.1))' }}
                                                />
                                            </g>
                                        );
                                    }}
                                >
                                    {activePieData.map((entry, index) => (
                                        <Cell
                                            key={`cell-${index}`}
                                            fill={entry.color}
                                            style={{ outline: 'none' }}
                                        />
                                    ))}
                                </Pie>
                                <Legend
                                    layout="vertical"
                                    verticalAlign="middle"
                                    align="right"
                                    iconType="circle"
                                    iconSize={8}
                                    wrapperStyle={{ fontSize: '11px', color: '#475569', right: 0 }}
                                    formatter={(value, entry: any) => {
                                        // Use legendColor from payload if available, or fall back
                                        const color = entry.payload.legendColor || entry.color;
                                        return <span style={{ color: '#475569', marginLeft: '4px' }}>{value}</span>;
                                    }}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: '#ffffff',
                                        border: '1px solid #e2e8f0',
                                        borderRadius: '6px',
                                        fontSize: '12px',
                                        color: '#0f172a', // Dark text
                                        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                                    }}
                                    itemStyle={{ padding: '0', color: '#334155' }}
                                    labelStyle={{ display: 'none' }} // Hide label for pie chart usually as it's redundant component name
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            {/* Line Chart Section */}
            <div className="w-full lg:w-[65%] h-[300px] lg:h-full bg-white rounded-xl p-5 border border-gray-200 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.08)] flex flex-col relative overflow-hidden">
                <div className="flex justify-between items-start mb-4">
                    <div>
                        <h3 className="text-[#111827] text-sm font-semibold tracking-wide">Reconciliation Trend</h3>
                        <p className="text-[#6B7280] text-[10px] uppercase tracking-wider">12-Month Performance</p>
                    </div>
                    {/* Optional: Legend could be custom here */}
                </div>

                <div className="flex-1 min-h-0 flex items-center justify-center relative">
                    {!hasData ? (
                        <div className="flex flex-col items-center justify-center text-center opacity-70">
                            <div className="w-24 h-24 rounded-full border-4 border-slate-100 flex items-center justify-center mb-3">
                                <span className="text-2xl grayscale opacity-50">📈</span>
                            </div>
                            <p className="text-gray-500 text-sm font-medium">No Trend Data</p>
                            <p className="text-gray-400 text-[10px] uppercase tracking-wide mt-1">History will appear here</p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                            <LineChart
                                data={lineData}
                                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                            >

                                <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} opacity={0.4} />
                                <XAxis
                                    dataKey="name"
                                    tick={{ fill: colors.text, fontSize: 10, fontWeight: 500 }}
                                    axisLine={false}
                                    tickLine={false}
                                    dy={10}
                                    padding={{ left: 10, right: 10 }}
                                />
                                <YAxis
                                    tick={{ fill: colors.text, fontSize: 10, fontWeight: 500 }}
                                    axisLine={false}
                                    tickLine={false}
                                    dx={-10}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: '#ffffff',
                                        border: '1px solid #e2e8f0',
                                        borderRadius: '8px',
                                        fontSize: '11px',
                                        color: '#0f172a',
                                        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
                                    }}
                                    cursor={{ stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '4 4' }}
                                />
                                <Legend
                                    verticalAlign="top"
                                    align="right"
                                    height={36}
                                    iconType="circle"
                                    iconSize={8}
                                    wrapperStyle={{ fontSize: '11px', color: '#475569', top: -10 }}
                                />

                                <Line
                                    type="monotone"
                                    dataKey="auto" // Auto-Matched
                                    name="Auto-Matched"
                                    stroke={legendColors.auto}
                                    strokeWidth={3}
                                    dot={false}
                                    activeDot={{ r: 6, strokeWidth: 3, fill: '#fff', stroke: legendColors.auto }}
                                    animationDuration={1500}
                                    filter="drop-shadow(0px 2px 4px rgba(59, 130, 246, 0.3))"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="exception"
                                    name="Exception"
                                    stroke={legendColors.exception}
                                    strokeWidth={2}
                                    dot={false}
                                    activeDot={{ r: 5, strokeWidth: 3, fill: '#fff', stroke: legendColors.exception }}
                                    strokeOpacity={0.8}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="matched" // Manual Matched
                                    name="Manual Match"
                                    stroke={legendColors.matched}
                                    strokeWidth={3}
                                    dot={false}
                                    activeDot={{ r: 6, strokeWidth: 3, fill: '#fff', stroke: legendColors.matched }}
                                    animationDuration={1500}
                                    filter="drop-shadow(0px 2px 4px rgba(16, 185, 129, 0.3))"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="partial"
                                    name="Partial"
                                    stroke={legendColors.partial}
                                    strokeWidth={2}
                                    dot={false}
                                    activeDot={{ r: 5, strokeWidth: 3, fill: '#fff', stroke: legendColors.partial }}
                                    strokeOpacity={0.8}
                                    strokeDasharray="5 5"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="unmatched"
                                    name="Unmatched"
                                    stroke={legendColors.unmatched}
                                    strokeWidth={3}
                                    dot={false}
                                    activeDot={{ r: 6, strokeWidth: 3, fill: '#fff', stroke: legendColors.unmatched }}
                                    animationDuration={1500}
                                    filter="drop-shadow(0px 2px 4px rgba(244, 63, 94, 0.3))"
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>
        </div>
    );
}
