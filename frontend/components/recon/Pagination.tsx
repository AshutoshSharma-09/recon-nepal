"use client";

import React, { useState, useEffect } from 'react';

interface PaginationProps {
    currentPage: number;
    totalPages: number;
    pageSize: number;
    totalItems: number;
    onPageChange: (page: number) => void;
    onPageSizeChange: (size: number) => void;
}

export function Pagination({
    currentPage,
    totalPages,
    pageSize,
    totalItems,
    onPageChange,
    onPageSizeChange
}: PaginationProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [inputValue, setInputValue] = useState(pageSize.toString());

    useEffect(() => {
        if (!isEditing) {
            setInputValue(pageSize.toString());
        }
    }, [pageSize, isEditing]);

    const STANDARD_SIZES = [10, 50, 100];
    const isStandard = STANDARD_SIZES.includes(pageSize);

    // Calculate page range for sliding window (show 5 pages at a time)
    const getPageNumbers = () => {
        const pages: number[] = [];
        const maxPagesToShow = 5;

        if (totalPages <= maxPagesToShow) {
            // Show all pages if total is 5 or less
            for (let i = 1; i <= totalPages; i++) {
                pages.push(i);
            }
        } else {
            // Sliding window logic
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);

            // Adjust if we're near the end
            if (endPage - startPage < maxPagesToShow - 1) {
                startPage = Math.max(1, endPage - maxPagesToShow + 1);
            }

            for (let i = startPage; i <= endPage; i++) {
                pages.push(i);
            }
        }

        return pages;
    };

    const handleSelectChange = (value: string) => {
        if (value === 'custom') {
            setIsEditing(true);
            setInputValue(pageSize.toString());
        } else {
            onPageSizeChange(parseInt(value));
            setIsEditing(false);
        }
    };

    const handleInputCommit = () => {
        const size = parseInt(inputValue);
        if (!isNaN(size) && size > 0 && size <= totalItems) {
            onPageSizeChange(size);
        } else {
            // If invalid, revert to current valid pageSize (visual revert happens on re-render/isEditing check)
            // Or we can just keep the invalid input? Better to reset or alert?
            // User UX preference: just reset if invalid or do nothing.
            // Let's reset to current pageSize representation if invalid
            setInputValue(pageSize.toString());
        }
        setIsEditing(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleInputCommit();
        } else if (e.key === 'Escape') {
            setIsEditing(false);
            setInputValue(pageSize.toString());
        }
    };

    const pageNumbers = getPageNumbers();
    const startItem = (currentPage - 1) * pageSize + 1;
    const endItem = Math.min(currentPage * pageSize, totalItems);

    return (
        <>
            <div className="flex items-center justify-between px-4 py-3 bg-white border-t border-gray-200">
                {/* Left: Page size selector */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-600">Show</span>

                    {!isEditing && isStandard ? (
                        <select
                            value={pageSize}
                            onChange={(e) => handleSelectChange(e.target.value)}
                            className="px-2 py-1 text-xs border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500 outline-none"
                        >
                            {STANDARD_SIZES.map(size => (
                                <option key={size} value={size}>{size}</option>
                            ))}
                            <option value="custom">Custom</option>
                        </select>
                    ) : (
                        <input
                            type="number"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onBlur={handleInputCommit}
                            onKeyDown={handleKeyDown}
                            autoFocus
                            className="w-16 px-2 py-1 text-xs border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500 outline-none text-center"
                            min="1"
                            max={totalItems}
                        />
                    )}

                    <span className="text-xs text-gray-600">entries</span>
                </div>

                {/* Center: Page navigation */}
                <div className="flex items-center gap-1">
                    {/* First */}
                    <button
                        onClick={() => onPageChange(1)}
                        disabled={currentPage === 1}
                        className="px-2 py-1 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        title="First page"
                    >
                        First
                    </button>

                    {/* Previous */}
                    <button
                        onClick={() => onPageChange(Math.max(1, currentPage - 1))}
                        disabled={currentPage === 1}
                        className="px-2 py-1 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        title="Previous page"
                    >
                        Prev
                    </button>

                    {/* Page numbers */}
                    {pageNumbers.map((page) => (
                        <button
                            key={page}
                            onClick={() => onPageChange(page)}
                            className={`px-3 py-1 text-xs font-medium rounded transition-colors ${page === currentPage
                                ? 'bg-blue-600 text-white border border-blue-600'
                                : 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50'
                                }`}
                        >
                            {page}
                        </button>
                    ))}

                    {/* Next */}
                    <button
                        onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
                        disabled={currentPage === totalPages}
                        className="px-2 py-1 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        title="Next page"
                    >
                        Next
                    </button>

                    {/* Last */}
                    <button
                        onClick={() => onPageChange(totalPages)}
                        disabled={currentPage === totalPages}
                        className="px-2 py-1 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        title="Last page"
                    >
                        Last
                    </button>
                </div>

                {/* Right: Item count */}
                <div className="text-xs text-gray-600">
                    Showing {startItem}-{endItem} of {totalItems}
                </div>
            </div>
        </>
    );
}
