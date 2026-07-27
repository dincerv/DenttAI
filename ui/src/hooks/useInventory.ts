'use client';
import { useCallback, useEffect, useState } from 'react';
import { inventoryApi } from '@/lib/api-client';
import type { BatchSummary, CycleMaterial, InventoryItem, QRGenerateResponse } from '@/types';

export function useInventory() {
  const [items, setItems]             = useState<InventoryItem[]>([]);
  const [cycles, setCycles]           = useState<CycleMaterial[]>([]);
  const [batchSummaries, setBatches]  = useState<BatchSummary[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const [itemsRes, cyclesRes, batchRes] = await Promise.all([
        inventoryApi.listItems(),
        inventoryApi.listCycles(),
        inventoryApi.batchSummaries(),
      ]);
      setItems(itemsRes.data);
      setCycles(cyclesRes.data);
      setBatches(batchRes.data);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? 'Envanter yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  const createItem = useCallback(async (data: {
    name: string;
    category?: string;
    quantity: number;
    unit: string;
    min_stock_level?: number;
    cost_per_unit?: number;
    shelf_code?: string;
    expiry_date?: string;
    batch_number?: string;
  }): Promise<InventoryItem> => {
    const res = await inventoryApi.createItem(data);
    await fetch();
    return res.data as InventoryItem;
  }, [fetch]);

  const updateItem = useCallback(async (id: string, data: {
    name?: string;
    category?: string;
    quantity?: number;
    unit?: string;
    min_stock_level?: number;
    cost_per_unit?: number;
    shelf_code?: string;
    expiry_date?: string;
    batch_number?: string;
  }): Promise<InventoryItem> => {
    const res = await inventoryApi.updateItem(id, data);
    await fetch();
    return res.data as InventoryItem;
  }, [fetch]);

  const deleteItem = useCallback(async (id: string) => {
    await inventoryApi.deleteItem(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  const generateQr = useCallback(async (data: {
    name: string;
    category?: string;
    expected_lifespan?: number;
  }): Promise<QRGenerateResponse> => {
    const res = await inventoryApi.generateQr(data);
    await fetch();
    return res.data as QRGenerateResponse;
  }, [fetch]);

  const activateQr = useCallback(async (qrId: string) => {
    await inventoryApi.activateQr(qrId);
    await fetch();
  }, [fetch]);

  const endCycle = useCallback(async (data: {
    qr_id: string;
    end_reason?: string;
    waste_note?: string;
  }) => {
    const res = await inventoryApi.endCycle(data);
    await fetch();
    return res.data;
  }, [fetch]);

  const adjustQuantity = useCallback(async (id: string, delta: number, reason?: string) => {
    const res = await inventoryApi.adjustQuantity(id, delta, reason);
    await fetch();
    return res.data;
  }, [fetch]);

  return {
    items,
    cycles,
    batchSummaries,
    loading,
    error,
    refresh: fetch,
    createItem,
    updateItem,
    deleteItem,
    generateQr,
    activateQr,
    endCycle,
    adjustQuantity,
  };
}
