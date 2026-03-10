"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '@/components/recon/Sidebar';
import { API_URL, API_KEY } from '@/lib/config';

import { DashboardCards } from '@/components/recon/DashboardCards';
import { DashboardCharts } from '@/components/recon/DashboardCharts';
// import { ReconWorkspace } from '@/components/recon/ReconWorkspace';
import { BankBrokerNet } from '@/components/recon/BankBrokerNet';
import { BrokerCashARAP } from '@/components/recon/BrokerCashARAP';
import { CashARAPGross } from '@/components/recon/CashARAPGross';
import { Exceptions } from '@/components/recon/Exceptions';
import { Transaction } from '@/components/recon/TransactionGrid';
// ... imports
import { CashArNet } from '@/components/recon/CashArNet';
import { CashApNet } from '@/components/recon/CashApNet';
import { StockPositionRecon } from '@/components/recon/StockPositionRecon';
import StockAcquisitionRecon from '@/components/recon/StockAcquisitionRecon';
import StockLiquidationRecon from '@/components/recon/StockLiquidationRecon';

type Tab = 'Dashboard' | 'BankBrokerNet' | 'BrokerCash' | 'Exceptions' | 'Stock Reconciliation';

export default function IngestPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>('Dashboard');
  const [brokerSubTab, setBrokerSubTab] = useState<'BrokerCash' | 'CashAR' | 'CashAP'>('CashAR');
  const [stockSubTab, setStockSubTab] = useState<'Position' | 'Movement'>('Position');
  const [movementSubTab, setMovementSubTab] = useState<'Acquisition' | 'Liquidation'>('Acquisition');
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [brokerFile, setBrokerFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isBankUploading, setIsBankUploading] = useState(false);
  const [isBrokerUploading, setIsBrokerUploading] = useState(false);
  const isUploading = isBankUploading || isBrokerUploading;

  const [bankFileId, setBankFileId] = useState<number | null>(null);
  const [brokerFileId, setBrokerFileId] = useState<number | null>(null);
  const [currentBatchId, setCurrentBatchId] = useState<number | null>(null);

  // Recon Data State
  const [bankRecords, setBankRecords] = useState<Transaction[]>([]);
  const [brokerRecords, setBrokerRecords] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<any>(null);

  // Preview State
  const [bankPreview, setBankPreview] = useState<any[] | null>(null);
  const [brokerPreview, setBrokerPreview] = useState<any[] | null>(null);

  // Cash/AR State
  const [cashFileId, setCashFileId] = useState<number | null>(null);
  const [arFileId, setArFileId] = useState<number | null>(null);
  const [apFileId, setApFileId] = useState<number | null>(null); // NEW
  const [capCashFileId, setCapCashFileId] = useState<number | null>(null); // NEW: Separate Cash ID for AP module
  const [cashRecords, setCashRecords] = useState<any[]>([]);
  const [arRecords, setArRecords] = useState<any[]>([]);
  const [cashApRecords, setCashApRecords] = useState<any[]>([]); // NEW (for AP tab cache of cash)
  const [apRecords, setApRecords] = useState<any[]>([]); // NEW
  const [carSummary, setCarSummary] = useState<any>(null);
  const [capSummary, setCapSummary] = useState<any>(null); // NEW
  const [currentCarBatchId, setCurrentCarBatchId] = useState<number | null>(null);
  const [currentCapBatchId, setCurrentCapBatchId] = useState<number | null>(null); // NEW
  const [isCashUploading, setIsCashUploading] = useState(false);
  const [isArUploading, setIsArUploading] = useState(false);
  const [isApUploading, setIsApUploading] = useState(false); // NEW

  // Stock Position Recon State
  const [stockSummaryFileId, setStockSummaryFileId] = useState<number | null>(null);
  const [transHistoryFileId, setTransHistoryFileId] = useState<number | null>(null);
  const [stockRows, setStockRows] = useState<any[]>([]);
  const [currentSrBatchId, setCurrentSrBatchId] = useState<number | null>(null);
  const [isSummaryUploading, setIsSummaryUploading] = useState(false);
  const [isHistoryUploading, setIsHistoryUploading] = useState(false);

  // Stock Movement Acquisition (SMA) Recon State
  const [smaAcqFileId, setSmaAcqFileId] = useState<number | null>(null);
  const [smaHistFileId, setSmaHistFileId] = useState<number | null>(null);
  const [smaRows, setSmaRows] = useState<any[]>([]);
  const [currentSmaBatchId, setCurrentSmaBatchId] = useState<number | null>(null);
  const [isSmaAcqUploading, setIsSmaAcqUploading] = useState(false);
  const [isSmaHistUploading, setIsSmaHistUploading] = useState(false);

  // Stock Movement Liquidation (SML) Recon State
  const [smlLiqFileId, setSmlLiqFileId] = useState<number | null>(null);
  const [smlHistFileId, setSmlHistFileId] = useState<number | null>(null);
  const [smlRows, setSmlRows] = useState<any[]>([]);
  const [currentSmlBatchId, setCurrentSmlBatchId] = useState<number | null>(null);
  const [isSmlLiqUploading, setIsSmlLiqUploading] = useState(false);
  const [isSmlHistUploading, setIsSmlHistUploading] = useState(false);

  // Tolerance State
  const [toleranceAmount, setToleranceAmount] = useState<number>(50);
  const [dateWindowDays, setDateWindowDays] = useState<number>(2);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // User Profile State
  const [userRole, setUserRole] = useState<string>('');
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const [dashboardView, setDashboardView] = useState<'Bank' | 'Broker' | 'Stock'>('Bank');
  const [dashboardBrokerSubView, setDashboardBrokerSubView] = useState<'BrokerCash' | 'CashAR' | 'CashAP'>('CashAR');
  const [dashboardStockSubView, setDashboardStockSubView] = useState<'Position' | 'Movement'>('Position');
  const [dashboardMovementSubView, setDashboardMovementSubView] = useState<'Acquisition' | 'Liquidation'>('Acquisition');

  // ... existing auth effect ...

  // Auth & User Check
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
    } else {
      // Get role for display
      const savedRole = localStorage.getItem('userRole');
      setUserRole(savedRole || 'User');
    }
  }, [router]);

  const handleLogout = async () => {
    try {
      const token = localStorage.getItem('token');
      if (token) {
        await fetch(`${API_URL}/api/v1/auth/logout`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
      }
    } catch (error) {
      console.error("Logout failed", error);
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('userRole');
      router.push('/login');
    }
  };

  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [resultSummary, setResultSummary] = useState<string>("");

  // Configuration
  // const API_URL = ""; // Moved to lib/config.ts
  // In a real app, this would be retrieved from auth context. Hardcoded for "Uploader" role for now.
  // const API_KEY = "secret-uploader-token"; // Moved to lib/config.ts

  const handleBankUpload = async (file: File) => {
    setBankFile(file);
    setIsBankUploading(true);
    setBankFileId(null); // Reset ID to prevent using stale data if upload fails
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/ingest/bank`, {
        method: "POST",
        headers: {
          "X-API-Key": API_KEY,
          "Authorization": `Bearer ${token}`
        },
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Bank upload failed");
      setBankPreview(data.transactions);
      setBankFileId(data.file_id);
    } catch (err: any) {
      alert(err.message);
      setStatus("idle");
    } finally {
      setIsBankUploading(false);
    }
  };

  const handleBrokerUpload = async (file: File) => {
    setBrokerFile(file);
    setIsBrokerUploading(true);
    setBrokerFileId(null); // Reset ID to prevent using stale data if upload fails
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/ingest/broker`, {
        method: "POST",
        headers: {
          "X-API-Key": API_KEY,
          "Authorization": `Bearer ${token}`
        },
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Broker upload failed");
      setBrokerPreview(data.transactions);
      setBrokerFileId(data.file_id);
    } catch (err: any) {
      alert(err.message);
      setStatus("idle");
    } finally {
      setIsBrokerUploading(false);
    }
  };

  const handleCashUpload = async (file: File) => {
    setIsCashUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/car-recon/ingest?source=CASH`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Cash upload failed");
      setCashFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsCashUploading(false); }
  };

  const handleArUpload = async (file: File) => {
    setIsArUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/car-recon/ingest?source=RECEIVABLE`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "AR upload failed");
      setArFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsArUploading(false); }
  };

  const handleCarRecon = async (): Promise<boolean> => {
    if (!cashFileId || !arFileId) { alert("Upload both Cash and AR files"); return false; }
    setIsProcessing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/v1/car-recon/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          cash_file_id: cashFileId,
          receivable_file_id: arFileId,
          tolerance_amount: toleranceAmount,
          date_window_days: dateWindowDays
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      setCashRecords(data.cash_records);
      setArRecords(data.ar_records);
      setCarSummary(data.summary || null);
      setCurrentCarBatchId(data.batch_id);
      alert("✅ Filters Applied Successfully!");
      return true;
    } catch (e: any) { alert(e.message); return false; }
    finally { setIsProcessing(false); }
  };

  const handleBrokerCashRecon = async (): Promise<boolean> => {
    setIsProcessing(true);
    try {
      // Broker vs Cash backend integration placeholder — filters are applied
      alert("✅ Filters Applied Successfully!");
      return true;
    } catch (e: any) { alert(e.message); return false; }
    finally { setIsProcessing(false); }
  };

  const handleCapRecon = async (): Promise<boolean> => {
    if (!capCashFileId || !apFileId) { alert("Upload both Cash and AP files"); return false; }
    setIsProcessing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/v1/cap-recon/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          cash_file_id: capCashFileId,
          payable_file_id: apFileId,
          tolerance_amount: toleranceAmount,
          date_window_days: dateWindowDays
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      setCashApRecords(data.cash_records);
      setApRecords(data.ap_records);
      setCapSummary(data.summary || null);
      setCurrentCapBatchId(data.batch_id);
      alert("✅ Filters Applied Successfully!");
      return true;
    } catch (e: any) { alert(e.message); return false; }
    finally { setIsProcessing(false); }
  };


  const handleCapCashUpload = async (file: File) => {
    setIsCashUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/cap-recon/ingest?source=CASH`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Cash upload failed");
      setCapCashFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsCashUploading(false); }
  };

  const handleApUpload = async (file: File) => {
    setIsApUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/cap-recon/ingest?source=PAYABLE`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "AP upload failed");
      setApFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsApUploading(false); }
  };

  const handleStockSummaryUpload = async (file: File) => {
    setIsSummaryUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/sr-recon/ingest?source=STOCK_SUMMARY`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Stock Summary upload failed");
      setStockSummaryFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsSummaryUploading(false); }
  };

  const handleTransHistoryUpload = async (file: File) => {
    setIsHistoryUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/sr-recon/ingest?source=TRANSACTION_HISTORY`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Transaction History upload failed");
      setTransHistoryFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsHistoryUploading(false); }
  };

  const handleSrRecon = async (): Promise<boolean> => {
    if (!stockSummaryFileId || !transHistoryFileId) {
      alert("Upload both Stock Summary and Transaction History files first.");
      return false;
    }
    setIsProcessing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/v1/sr-recon/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          summary_file_id: stockSummaryFileId,
          history_file_id: transHistoryFileId,
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "SR Recon failed");
      setStockRows(data.rows || []);
      setCurrentSrBatchId(data.batch_id);
      alert("✅ Stock Position Recon Complete!");
      return true;
    } catch (e: any) { alert(e.message); return false; }
    finally { setIsProcessing(false); }
  };

  const refreshSrData = async () => {
    if (!currentSrBatchId) return;
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/v1/sr-recon/latest`, {
        headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setStockRows(data.rows || []);
        if (data.batch_id) setCurrentSrBatchId(data.batch_id);
      }
    } catch (e) { }
  };

  // --- SMA Recon Handlers ---
  const handleSmaAcqUpload = async (file: File) => {
    setIsSmaAcqUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/sma-recon/ingest?source=STOCK_ACQUISITION`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Stock Acquisition upload failed");
      setSmaAcqFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsSmaAcqUploading(false); }
  };

  const handleSmaHistUpload = async (file: File) => {
    setIsSmaHistUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/sma-recon/ingest?source=TRANSACTION_HISTORY`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Transaction History upload failed");
      setSmaHistFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsSmaHistUploading(false); }
  };

  const handleSmaRecon = async (): Promise<boolean> => {
    if (!smaAcqFileId || !smaHistFileId) {
      alert("Upload both Stock Acquisition and Transaction History files first.");
      return false;
    }
    setIsProcessing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/v1/sma-recon/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          acquisition_file_id: smaAcqFileId,
          history_file_id: smaHistFileId,
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "SMA Recon failed");
      setSmaRows(data.rows || []);
      setCurrentSmaBatchId(data.batch_id);
      alert("✅ Stock Acquisition Recon Complete!");
      return true;
    } catch (e: any) { alert(e.message); return false; }
    finally { setIsProcessing(false); }
  };

  const refreshSmaData = async () => {
    if (!currentSmaBatchId) return;
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/v1/sma-recon/latest`, {
        headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSmaRows(data.rows || []);
        if (data.batch_id) setCurrentSmaBatchId(data.batch_id);
      }
    } catch (e) { }
  };

  // --- SML Recon Handlers ---
  const handleSmlLiqUpload = async (file: File) => {
    setIsSmlLiqUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/sml-recon/ingest?source=STOCK_LIQUIDATION`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Stock Liquidation upload failed");
      setSmlLiqFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsSmlLiqUploading(false); }
  };

  const handleSmlHistUpload = async (file: File) => {
    setIsSmlHistUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/sml-recon/ingest?source=TRANSACTION_HISTORY`, {
        method: "POST", headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }, body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Transaction History upload failed");
      setSmlHistFileId(data.file_id);
    } catch (e: any) { alert(e.message); }
    finally { setIsSmlHistUploading(false); }
  };

  const handleSmlRecon = async (): Promise<boolean> => {
    if (!smlLiqFileId || !smlHistFileId) {
      alert("Upload both Stock Liquidation and Transaction History files first.");
      return false;
    }
    setIsProcessing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/v1/sml-recon/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          liquidation_file_id: smlLiqFileId,
          history_file_id: smlHistFileId,
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "SML Recon failed");
      setSmlRows(data.rows || []);
      setCurrentSmlBatchId(data.batch_id);
      alert("✅ Stock Liquidation Recon Complete!");
      return true;
    } catch (e: any) { alert(e.message); return false; }
    finally { setIsProcessing(false); }
  };

  const refreshSmlData = async () => {
    if (!currentSmlBatchId) return;
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/v1/sml-recon/latest`, {
        headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSmlRows(data.rows || []);
        if (data.batch_id) setCurrentSmlBatchId(data.batch_id);
      }
    } catch (e) { }
  };

  const handleToleranceChange = (amount: number, dateWindow: number) => {
    setToleranceAmount(amount);
    setDateWindowDays(dateWindow);
  };

  const handleApplyFilters = () => {
    alert("✅ Filters Applied Successfully!");
  };

  const handleRecon = async (): Promise<boolean> => {
    if (!bankFileId || !brokerFileId) {
      alert("Please upload both Bank and Broker files first.");
      return false;
    }

    setIsProcessing(true);
    setStatus("idle");

    try {
      const token = localStorage.getItem('token');
      // Trigger Reconciliation
      const res = await fetch(`${API_URL}/api/v1/recon/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          broker_file_id: brokerFileId,
          bank_file_id: bankFileId,
          tolerance_amount: toleranceAmount,
          date_window_days: dateWindowDays
        })
      });
      const reconData = await res.json();

      if (!res.ok) throw new Error(reconData.detail || "Reconciliation failed");

      // Store Data
      setBankRecords(reconData.bank_records);
      setBrokerRecords(reconData.broker_records);
      setSummary(reconData.summary);
      setCurrentBatchId(reconData.batch_id);
      setStatus("success");

      // Show success notification
      alert("✅ Filters Applied Successfully!");

      // Optionally switch to BankBrokerNet tab automatically if desired, staying on Dashboard for now
      return true;

    } catch (err: any) {
      setStatus("idle");
      alert(err.message);
      return false;
    } finally {
      setIsProcessing(false);
    }
  };

  // Fetch latest recon status on mount (Persistence)
  React.useEffect(() => {
    const fetchLatest = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;

        const res = await fetch(`${API_URL}/api/v1/recon/latest`, {
          headers: {
            "X-API-Key": API_KEY,
            "Authorization": `Bearer ${token}`
          }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.summary) {
            // Restore State
            setBankRecords(data.bank_records || []);
            setBrokerRecords(data.broker_records || []);
            setSummary(data.summary);
            setCurrentBatchId(data.batch_id);
            setStatus("success");
            // Restore file IDs to prevent "Please upload files" error on refresh
            if (data.bank_file_id) setBankFileId(data.bank_file_id);
            if (data.broker_file_id) setBrokerFileId(data.broker_file_id);
          }
        }
      } catch (e) {
        console.log("No previous session found");
      }
    };

    const fetchLatestCar = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;
        const res = await fetch(`${API_URL}/api/v1/car-recon/latest`, { headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` } });
        if (res.ok) {
          const data = await res.json();
          if (data.batch_id) {
            setCashRecords(data.cash_records || []);
            setArRecords(data.ar_records || []);
            setCarSummary(data.summary || null);
            setCurrentCarBatchId(data.batch_id);
            if (data.cash_file_id) setCashFileId(data.cash_file_id);
            if (data.receivable_file_id) setArFileId(data.receivable_file_id);
          }
        }
      } catch (e) { }
    };

    const fetchLatestCap = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;
        const res = await fetch(`${API_URL}/api/v1/cap-recon/latest`, { headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` } });
        if (res.ok) {
          const data = await res.json();
          if (data.batch_id) {
            setCashApRecords(data.cash_records || []);
            setApRecords(data.ap_records || []);
            setCapSummary(data.summary || null);
            setCurrentCapBatchId(data.batch_id);
            if (data.cash_file_id) setCapCashFileId(data.cash_file_id);
            if (data.payable_file_id) setApFileId(data.payable_file_id);
          }
        }
      } catch (e) { }
    };

    fetchLatest();
    fetchLatestCar();
    fetchLatestCap();

    // Stock Recon (SR)
    const fetchLatestSr = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;
        const res = await fetch(`${API_URL}/api/v1/sr-recon/latest`, {
          headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.batch_id) {
            setStockRows(data.rows || []);
            setCurrentSrBatchId(data.batch_id);
            if (data.summary_file_id) setStockSummaryFileId(data.summary_file_id);
            if (data.history_file_id) setTransHistoryFileId(data.history_file_id);
          }
        }
      } catch (e) { }
    };
    fetchLatestSr();

    // Stock Movement Acquisition (SMA)
    const fetchLatestSma = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;
        const res = await fetch(`${API_URL}/api/v1/sma-recon/latest`, {
          headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.batch_id) {
            setSmaRows(data.rows || []);
            setCurrentSmaBatchId(data.batch_id);
          }
        }
      } catch (e) { }
    };
    fetchLatestSma();

    // Stock Movement Liquidation (SML)
    const fetchLatestSml = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;
        const res = await fetch(`${API_URL}/api/v1/sml-recon/latest`, {
          headers: { "X-API-Key": API_KEY, "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.batch_id) {
            setSmlRows(data.rows || []);
            setCurrentSmlBatchId(data.batch_id);
          }
        }
      } catch (e) { }
    };
    fetchLatestSml();
  }, []);

  const handleReset = () => {
    setBankFile(null);
    setBrokerFile(null);
    setBankPreview(null);
    setBrokerPreview(null);
    setStatus('idle');
    setBankRecords([]);
    setBrokerRecords([]);
    setSummary(null);
  };

  return (
    <div className="flex flex-col h-screen bg-[#F6F8FB] font-sans text-sm overflow-hidden text-slate-800">
      {/* Header - Full Width */}
      <header className="bg-gradient-to-r from-[#172554] via-[#1e3a8a] to-[#172554] text-white h-14 flex items-center justify-between px-4 sm:px-6 shrink-0 border-b border-white/5 shadow-xl z-20 relative backdrop-blur-md">
        <div className="flex items-center gap-3">
          {/* Hamburger Menu - Mobile Only */}
          <button
            className="md:hidden p-1 hover:bg-white/10 rounded-md transition-colors"
            onClick={() => setIsSidebarOpen(true)}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <img src="/logo.png" alt="NIBLReco360 Logo" className="h-9 w-auto bg-white px-2 py-1 rounded shadow-sm hidden sm:block" />
          <h1 className="font-bold text-base truncate ml-2">NIBLReco360</h1>
        </div>

        <div className="flex items-center gap-4">


          {/* User Profile Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsProfileOpen(!isProfileOpen)}
              className="flex items-center gap-2 pl-3 border-l border-white/10 hover:bg-white/5 py-1 pr-2 rounded transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center border border-white/20">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
            </button>

            {isProfileOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setIsProfileOpen(false)}></div>
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-slate-100 py-1 z-20 text-slate-700 animate-in fade-in zoom-in-95 duration-100">
                  <div className="px-4 py-2 border-b border-slate-100">
                    <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">Signed in as</p>
                    <p className="text-sm font-semibold text-slate-900 truncate">
                      {userRole}
                    </p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    Log out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </header>
      {/* Content Wrapper */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Sidebar — visible on all tabs */}
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          onBankUpload={handleBankUpload}
          onBrokerUpload={handleBrokerUpload}
          isProcessing={isProcessing}
          isUploading={isUploading}
          onApply={handleApplyFilters}
          onReset={handleReset}
          onToleranceChange={handleToleranceChange}
        />

        {/* Main Content */}
        <main className="flex-1 overflow-auto p-4 bg-[#F6F8FB]">
          {/* Tabs */}
          <div className="flex flex-wrap gap-1 mb-4 border-b border-[#1e3b8b]/30">
            <button
              onClick={() => setActiveTab('Dashboard')}
              className={`px-4 py-2 rounded-t-md text-xs font-medium transition-colors ${activeTab === 'Dashboard' ? 'bg-[#1e3b8b] text-white' : 'bg-white text-[#1b398a] hover:bg-blue-50 border-t border-x border-transparent hover:border-blue-100'}`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setActiveTab('BankBrokerNet')}
              className={`px-4 py-2 rounded-t-md text-xs font-medium transition-colors ${activeTab === 'BankBrokerNet' ? 'bg-[#1e3b8b] text-white' : 'bg-white text-[#1b398a] hover:bg-blue-50 border-t border-x border-transparent hover:border-blue-100'}`}
            >
              Bank Reconciliation
            </button>
            <button
              onClick={() => setActiveTab('BrokerCash')}
              className={`px-4 py-2 rounded-t-md text-xs font-medium transition-colors ${activeTab === 'BrokerCash' ? 'bg-[#1e3b8b] text-white' : 'bg-white text-[#1b398a] hover:bg-blue-50 border-t border-x border-transparent hover:border-blue-100'}`}
            >
              Broker Reconciliation
            </button>

            <button
              onClick={() => setActiveTab('Stock Reconciliation')}
              className={`px-4 py-2 rounded-t-md text-xs font-medium transition-colors ${activeTab === 'Stock Reconciliation' ? 'bg-[#1e3b8b] text-white' : 'bg-white text-[#1b398a] hover:bg-blue-50 border-t border-x border-transparent hover:border-blue-100'}`}
            >
              Stock Reconciliation
            </button>
            <button
              onClick={() => setActiveTab('Exceptions')}
              className={`px-4 py-2 rounded-t-md text-xs font-medium transition-colors ${activeTab === 'Exceptions' ? 'bg-[#1e3b8b] text-white' : 'bg-white text-[#1b398a] hover:bg-blue-50 border-t border-x border-transparent hover:border-blue-100'}`}
            >
              Manual Match
            </button>

          </div>

          {/* Dynamic Content */}
          {activeTab === 'Dashboard' && (
            <>
              {/* Dashboard View Dropdown */}
              <div className="flex items-center gap-4 mb-4">
                <div className="relative inline-block text-left">
                  <select
                    value={dashboardView}
                    onChange={(e) => setDashboardView(e.target.value as any)}
                    className="block w-full pl-3 pr-10 py-2 text-xs border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-xs rounded-md shadow-sm"
                  >
                    <option value="Bank">Bank Reconciliation</option>
                    <option value="Broker">Broker Reconciliation</option>
                    <option value="Stock">Stock Reconciliation</option>
                  </select>
                </div>

                {/* Broker Sub-Options */}
                {dashboardView === 'Broker' && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => setDashboardBrokerSubView('CashAR')}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all border ${dashboardBrokerSubView === 'CashAR'
                        ? 'bg-blue-100 text-blue-700 border-blue-300'
                        : 'bg-white text-slate-600 border-slate-300 hover:bg-gray-50'
                        }`}
                    >
                      Cash VS AR
                    </button>
                    <button
                      onClick={() => setDashboardBrokerSubView('CashAP')}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all border ${dashboardBrokerSubView === 'CashAP'
                        ? 'bg-blue-100 text-blue-700 border-blue-300'
                        : 'bg-white text-slate-600 border-slate-300 hover:bg-gray-50'
                        }`}
                    >
                      Cash VS AP
                    </button>
                  </div>
                )}

                {/* Stock Sub-Options */}
                {dashboardView === 'Stock' && (
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Level 1: Position | Movement */}
                    <button
                      onClick={() => setDashboardStockSubView('Position')}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all border ${dashboardStockSubView === 'Position'
                        ? 'bg-blue-100 text-blue-700 border-blue-300'
                        : 'bg-white text-slate-600 border-slate-300 hover:bg-gray-50'
                        }`}
                    >
                      Position Reconciliation
                    </button>
                    <button
                      onClick={() => setDashboardStockSubView('Movement')}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all border ${dashboardStockSubView === 'Movement'
                        ? 'bg-blue-100 text-blue-700 border-blue-300'
                        : 'bg-white text-slate-600 border-slate-300 hover:bg-gray-50'
                        }`}
                    >
                      Movement Reconciliation
                    </button>

                    {/* Level 2 (only when Movement active): Acquisition | Liquidation */}
                    {dashboardStockSubView === 'Movement' && (
                      <>
                        <span className="text-slate-300 text-sm">|</span>
                        <button
                          onClick={() => setDashboardMovementSubView('Acquisition')}
                          className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all border ${dashboardMovementSubView === 'Acquisition'
                            ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
                            : 'bg-white text-slate-600 border-slate-300 hover:bg-gray-50'
                            }`}
                        >
                          Stock Acquisition
                        </button>
                        <button
                          onClick={() => setDashboardMovementSubView('Liquidation')}
                          className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all border ${dashboardMovementSubView === 'Liquidation'
                            ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
                            : 'bg-white text-slate-600 border-slate-300 hover:bg-gray-50'
                            }`}
                        >
                          Stock Liquidation
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Conditional Content based on dashboardView */}
              {dashboardView === 'Bank' && (
                <>
                  <DashboardCards summary={summary} />
                  <DashboardCharts summary={summary} />
                </>
              )}

              {dashboardView === 'Broker' && (
                <>
                  {dashboardBrokerSubView === 'CashAR' ? (
                    <>
                      <DashboardCards summary={carSummary} />
                      <DashboardCharts summary={carSummary} />
                    </>
                  ) : dashboardBrokerSubView === 'CashAP' ? (
                    <>
                      <DashboardCards summary={capSummary} />
                      <DashboardCharts summary={capSummary} />
                    </>
                  ) : (
                    <div className="flex items-center justify-center p-8 text-gray-400 border-2 border-dashed border-gray-300 rounded-lg">
                      <p>Broker Reconciliation Dashboard (Broker vs Cash) coming soon...</p>
                    </div>
                  )}
                </>
              )}

              {dashboardView === 'Stock' && (() => {
                // Determine which rows to use based on the active sub-view
                let activeRows: any[] = [];
                let isLiquidationPlaceholder = false;

                if (dashboardStockSubView === 'Position') {
                  activeRows = stockRows;
                } else if (dashboardMovementSubView === 'Acquisition') {
                  activeRows = smaRows;
                } else {
                  activeRows = smlRows;
                }

                if (isLiquidationPlaceholder) {
                  return (
                    <div className="flex flex-col items-center justify-center p-12 text-slate-400 border-2 border-dashed border-slate-200 rounded-xl bg-white/50">
                      <svg className="w-10 h-10 mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
                      </svg>
                      <p className="text-sm font-semibold">Stock Liquidation</p>
                      <p className="text-xs mt-1">Dashboard coming soon</p>
                    </div>
                  );
                }

                const matched = activeRows.filter((r: any) => r.status === 'MATCHED');
                const unmatched = activeRows.filter((r: any) => r.status === 'UNMATCHED');
                const exceptions = activeRows.filter((r: any) => r.status === 'EXCEPTION');
                const autoMatched = matched.filter((r: any) => !r.match_kind || r.match_kind === 'AUTO').length;
                const manualMatched = matched.filter((r: any) => r.match_kind === 'MANUAL').length;
                const stockSummary = activeRows.length > 0 ? {
                  total_matches: matched.length,
                  auto_match_count: autoMatched,
                  manual_match_count: manualMatched,
                  unmatched_broker: unmatched.length,
                  unmatched_bank: 0,
                  exceptions: exceptions.length,
                  unmatched_count: unmatched.length,
                  exception_count: exceptions.length,
                } : null;

                return (
                  <div className="overflow-auto">
                    <DashboardCards summary={stockSummary} />
                    <DashboardCharts summary={stockSummary} />
                  </div>
                );
              })()}

              {/* If matched, show Recon Workspace or Result Table below */}
              {/* If matched, show Recon Workspace or Result Table below - REMOVED LEGACY COMPONENT */}
              {dashboardView === 'Bank' && status === 'success' && (
                <div className="mt-8 flex flex-col items-center justify-center text-gray-400">
                  <p className="text-sm">Reconciliation Complete. Use the tabs above to view details.</p>
                </div>
              )}
              {dashboardView === 'Bank' && status === 'idle' && (
                <div className="mt-8 flex flex-col items-center justify-center text-gray-400">
                  <p>Upload files and click Apply to start reconciliation.</p>
                  {bankFile && <div className="mt-2 text-xs">Bank File: {bankFile.name} (ID: {bankFileId})</div>}
                  {brokerFile && <div className="mt-1 text-xs">Broker File: {brokerFile.name} (ID: {brokerFileId})</div>}
                </div>
              )}
              {dashboardView === 'Bank' && status === 'error' && (
                <div className="mt-4 p-3 bg-red-100 text-red-700 text-xs rounded border border-red-200">
                  Error: {resultSummary}
                </div>
              )}
            </>
          )}

          {activeTab === 'BankBrokerNet' && (
            <BankBrokerNet
              bankRecords={bankRecords}
              brokerRecords={brokerRecords}
              batchId={currentBatchId}
              onBankUpload={handleBankUpload}
              onBrokerUpload={handleBrokerUpload}
              isUploading={isUploading}
              isBankUploading={isBankUploading}
              isBrokerUploading={isBrokerUploading}
              onAutoMatch={handleRecon}
              isProcessing={isProcessing}
              hasBankFile={!!bankFileId}
              hasBrokerFile={!!brokerFileId}
              toleranceAmount={toleranceAmount}
              dateWindowDays={dateWindowDays}
              onResetFiles={() => {
                setBankFile(null);
                setBrokerFile(null);
                setBankFileId(null);
                setBrokerFileId(null);
              }}
            />
          )}

          {activeTab === 'BrokerCash' && (
            <div className="flex flex-col h-full">
              {/* Sub-Navigation — Broker-Cash hidden */}
              <div className="flex gap-2 mb-4 bg-white/50 p-1 rounded-lg w-fit">
                <button
                  onClick={() => setBrokerSubTab('CashAR')}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${brokerSubTab === 'CashAR'
                    ? 'bg-[#1e3b8b] text-white shadow-sm'
                    : 'text-slate-600 hover:bg-white hover:text-[#1e3b8b]'
                    }`}
                >
                  Cash ↔ AR
                </button>
                <button
                  onClick={() => setBrokerSubTab('CashAP')}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${brokerSubTab === 'CashAP'
                    ? 'bg-[#1e3b8b] text-white shadow-sm'
                    : 'text-slate-600 hover:bg-white hover:text-[#1e3b8b]'
                    }`}
                >
                  Cash ↔ AP
                </button>
              </div>

              {/* Sub-Content */}
              <div className="flex-1 overflow-hidden">
                {brokerSubTab === 'BrokerCash' && <BrokerCashARAP title="Broker ↔ Cash" onAutoMatch={handleBrokerCashRecon} toleranceAmount={toleranceAmount} dateWindowDays={dateWindowDays} />}
                {brokerSubTab === 'CashAR' && (
                  <CashArNet
                    cashRecords={cashRecords}
                    arRecords={arRecords}
                    batchId={currentCarBatchId}
                    onCashUpload={handleCashUpload}
                    onArUpload={handleArUpload}
                    isUploading={isCashUploading || isArUploading}
                    onAutoMatch={handleCarRecon}
                    isProcessing={isProcessing}
                    hasCashFile={!!cashFileId}
                    hasArFile={!!arFileId}
                    toleranceAmount={toleranceAmount}
                    dateWindowDays={dateWindowDays}
                    onResetFiles={() => {
                      setCashFileId(null);
                      setArFileId(null);
                    }}
                  />
                )}
                {brokerSubTab === 'CashAP' && (
                  <CashApNet
                    cashRecords={cashApRecords}
                    apRecords={apRecords}
                    batchId={currentCapBatchId}
                    onCashUpload={handleCapCashUpload}
                    onApUpload={handleApUpload}
                    isUploading={isCashUploading || isApUploading}
                    onAutoMatch={handleCapRecon}
                    isProcessing={isProcessing}
                    hasCashFile={!!capCashFileId}
                    hasApFile={!!apFileId}
                    toleranceAmount={toleranceAmount}
                    dateWindowDays={dateWindowDays}
                    onResetFiles={() => {
                      setCapCashFileId(null);
                      setApFileId(null);
                    }}
                  />
                )}
              </div>
            </div>
          )}

          {activeTab === 'Exceptions' && (
            <Exceptions
              bankRecords={bankRecords}
              brokerRecords={brokerRecords}
              batchId={currentBatchId}
              cashRecords={cashRecords}
              arRecords={arRecords}
              cashApRecords={cashApRecords}
              apRecords={apRecords}
              stockRows={stockRows}
              smaRows={smaRows}
              smlRows={smlRows}
            />
          )}

          {/* Placeholders for other tabs */}
          {activeTab !== 'Dashboard' && activeTab !== 'BankBrokerNet' && activeTab !== 'BrokerCash' && activeTab !== 'Exceptions' && activeTab !== 'Stock Reconciliation' && (
            <div className="flex items-center justify-center h-64 text-gray-400 border-2 border-dashed border-gray-300 rounded-lg">
              Content for {activeTab} coming soon...
            </div>
          )}

          {activeTab === 'Stock Reconciliation' && (
            <div className="flex flex-col h-full">
              {/* Level 1 Sub-Navigation: Position / Movement */}
              <div className="flex gap-2 mb-4 bg-white/50 p-1 rounded-lg w-fit">
                <button
                  onClick={() => setStockSubTab('Position')}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${stockSubTab === 'Position'
                    ? 'bg-[#1e3b8b] text-white shadow-sm'
                    : 'text-slate-600 hover:bg-white hover:text-[#1e3b8b]'
                    }`}
                >
                  Position Reconciliation
                </button>
                <button
                  onClick={() => setStockSubTab('Movement')}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${stockSubTab === 'Movement'
                    ? 'bg-[#1e3b8b] text-white shadow-sm'
                    : 'text-slate-600 hover:bg-white hover:text-[#1e3b8b]'
                    }`}
                >
                  Movement Reconciliation
                </button>
              </div>

              {/* Level 1 Content */}
              <div className="flex-1 overflow-hidden">

                {/* --- POSITION RECONCILIATION --- */}
                {stockSubTab === 'Position' && (
                  <StockPositionRecon
                    rows={stockRows}
                    batchId={currentSrBatchId}
                    onSummaryUpload={handleStockSummaryUpload}
                    onHistoryUpload={handleTransHistoryUpload}
                    onAutoMatch={handleSrRecon}
                    isProcessing={isProcessing}
                    hasSummaryFile={!!stockSummaryFileId}
                    hasHistoryFile={!!transHistoryFileId}
                    isSummaryUploading={isSummaryUploading}
                    isHistoryUploading={isHistoryUploading}
                    onRefresh={refreshSrData}
                    onResetFiles={() => {
                      setStockSummaryFileId(null);
                      setTransHistoryFileId(null);
                    }}
                  />
                )}

                {/* --- MOVEMENT RECONCILIATION --- */}
                {stockSubTab === 'Movement' && (
                  <div className="flex flex-col h-full">
                    {/* Level 2 Sub-Navigation: Acquisition / Liquidation */}
                    <div className="flex gap-2 mb-4 bg-white/50 p-1 rounded-lg w-fit">
                      <button
                        onClick={() => setMovementSubTab('Acquisition')}
                        className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${movementSubTab === 'Acquisition'
                          ? 'bg-[#1e3b8b] text-white shadow-sm'
                          : 'text-slate-600 hover:bg-white hover:text-[#1e3b8b]'
                          }`}
                      >
                        Stock Acquisition
                      </button>
                      <button
                        onClick={() => setMovementSubTab('Liquidation')}
                        className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${movementSubTab === 'Liquidation'
                          ? 'bg-[#1e3b8b] text-white shadow-sm'
                          : 'text-slate-600 hover:bg-white hover:text-[#1e3b8b]'
                          }`}
                      >
                        Stock Liquidation
                      </button>
                    </div>

                    {/* Level 2 Content */}
                    <div className="flex-1 overflow-auto">
                      {movementSubTab === 'Acquisition' && (
                        <StockAcquisitionRecon
                          rows={smaRows}
                          batchId={currentSmaBatchId}
                          onAcquisitionUpload={handleSmaAcqUpload}
                          onHistoryUpload={handleSmaHistUpload}
                          onAutoMatch={handleSmaRecon}
                          isProcessing={isProcessing}
                          hasAcquisitionFile={!!smaAcqFileId}
                          hasHistoryFile={!!smaHistFileId}
                          isAcquisitionUploading={isSmaAcqUploading}
                          isHistoryUploading={isSmaHistUploading}
                          onRefresh={refreshSmaData}
                          onResetFiles={() => {
                            setSmaAcqFileId(null);
                            setSmaHistFileId(null);
                          }}
                        />
                      )}
                      {movementSubTab === 'Liquidation' && (
                        <StockLiquidationRecon
                          rows={smlRows}
                          batchId={currentSmlBatchId}
                          onLiquidationUpload={handleSmlLiqUpload}
                          onHistoryUpload={handleSmlHistUpload}
                          onAutoMatch={handleSmlRecon}
                          isProcessing={isProcessing}
                          hasLiquidationFile={!!smlLiqFileId}
                          hasHistoryFile={!!smlHistFileId}
                          isLiquidationUploading={isSmlLiqUploading}
                          isHistoryUploading={isSmlHistUploading}
                          onRefresh={refreshSmlData}
                          onResetFiles={() => {
                            setSmlLiqFileId(null);
                            setSmlHistFileId(null);
                          }}
                        />
                      )}
                    </div>
                  </div>
                )}

              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}
