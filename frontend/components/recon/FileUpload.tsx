
"use client";

import React, { useState } from 'react';

interface FileUploadProps {
  label: string;
  accept: string;
  onUpload: (file: File) => void;
  isLoading?: boolean;
}

export function FileUpload({ label, accept, onUpload, isLoading }: FileUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file: File) => {
    setFileName(file.name);
    onUpload(file);
  };

  return (
    <div className="w-full mb-4">
      <label className="block text-sm font-medium mb-2 text-foreground">{label}</label>
      <div
        className={`relative flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-lg transition-colors ${dragActive
            ? "border-primary bg-primary/10"
            : "border-border bg-card hover:bg-accent/50"
          }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept={accept}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
          onChange={handleChange}
          disabled={isLoading}
        />
        <div className="text-center pointer-events-none">
          {isLoading ? (
            <div className="text-sm text-muted-foreground animate-pulse">Processing...</div>
          ) : fileName ? (
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-primary">{fileName}</span>
              <span className="text-xs text-muted-foreground">(Click to change)</span>
            </div>
          ) : (
            <>
              <p className="text-sm text-foreground font-medium">Click to upload or drag and drop</p>
              <p className="text-xs text-muted-foreground mt-1 text-center">
                {accept === ".txt" ? "Bank Statement (.txt)" :
                  accept === ".csv" ? "Data File (.csv)" :
                    "Document (.pdf)"}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
