'use client';
import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import {
  QrCode, AlertTriangle, Package, PackagePlus, RefreshCw, X,
  Trash2, Pencil, PlusCircle, MinusCircle, CheckCircle2, Clock, History, TrendingUp, TrendingDown, Bell,
} from 'lucide-react';
import { useInventory } from '@/hooks/useInventory';
import { useWasteReport } from '@/hooks/useDashboard';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { TableRowSkeleton, Skeleton } from '@/components/ui/Skeleton';
import { BatchTooltip } from '@/components/dashboard/BatchTooltip';
import { formatDate } from '@/lib/utils';
import { inventoryApi } from '@/lib/api-client';
import type { InventoryItem, InventoryAdjustment, CycleMaterial, QRGenerateResponse } from '@/types';

// ── QR Generate Modal ─────────────────────────────────────────────────────

function QRModal({
  onClose,
  prefill,
}: {
  onClose: () => void;
  prefill?: { name: string; category: string | null };
}) {
  const { generateQr } = useInventory();
  const [name, setName]                     = useState(prefill?.name ?? '');
  const [category, setCategory]             = useState(prefill?.category ?? '');
  const [expectedLifespan, setLifespan]     = useState('');
  const [loading, setLoading]               = useState(false);
  const [result, setResult]                 = useState<QRGenerateResponse | null>(null);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await generateQr({
        name,
        category: category || undefined,
        expected_lifespan: expectedLifespan ? parseInt(expectedLifespan) : undefined,
      });
      setResult(res);
      toast.success('QR kodu üretildi');
    } catch {
      toast.error('QR üretimi başarısız');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-800">QR Kod Üret</h2>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        {result ? (
          <div className="flex flex-col items-center gap-4 p-6">
            <img
              src={`data:image/png;base64,${result.qr_code_base64}`}
              alt={`QR: ${result.qr_id}`}
              className="h-48 w-48 rounded-lg border border-slate-200"
            />
            {/* Raf Kodu — gözle okunabilir kısa kimlik */}
            <div className="flex flex-col items-center gap-1">
              <p className="text-xs text-slate-400 uppercase tracking-widest">Raf Kodu</p>
              <p className="text-3xl font-bold font-mono tracking-widest text-blue-700 bg-blue-50 border border-blue-200 px-4 py-2 rounded-lg">
                {result.shelf_code}
              </p>
            </div>
            <p className="text-xs font-mono text-slate-400 break-all">{result.qr_id}</p>
            <p className="text-sm text-slate-600 text-center">
              QR kodu yazdırarak malzemeye yapıştırın. Aktivasyon için QR okutunuz.
            </p>
            <Button onClick={onClose} variant="secondary" className="w-full">
              Kapat
            </Button>
          </div>
        ) : (
          <form onSubmit={handleGenerate} className="space-y-4 p-6">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Malzeme Adı *
              </label>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ör: Anguldurva 1:5"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Kategori</label>
              <input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="anguldurva / tur / file"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Beklenen Ömür (gün)
              </label>
              <input
                type="number"
                min={1}
                value={expectedLifespan}
                onChange={(e) => setLifespan(e.target.value)}
                placeholder="Ör: 180"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              />
            </div>
            <div className="flex gap-3 pt-2">
              <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
                İptal
              </Button>
              <Button type="submit" disabled={loading} className="flex-1">
                {loading ? 'Üretiliyor...' : 'QR Üret'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

// ── Add Item Modal ─────────────────────────────────────────────────────────

function AddItemModal({ onClose }: { onClose: () => void }) {
  const { createItem, batchSummaries, items } = useInventory();
  const [name, setName]           = useState('');
  const [category, setCategory]   = useState('');
  const [quantity, setQuantity]   = useState('');
  const [unit, setUnit]           = useState('adet');
  const [minStock, setMinStock]   = useState('');
  const [costPerUnit, setCost]    = useState('');
  const [shelfCode, setShelfCode] = useState('');
  const [expiryDate, setExpiry]   = useState('');
  const [batchNumber, setBatch]   = useState('');
  const [loading, setLoading]     = useState(false);

  // Aynı isimde mevcut ürün var mı kontrol et
  const existingProduct = batchSummaries.find(
    (s) => s.name.toLowerCase().trim() === name.toLowerCase().trim()
  );

  // Mevcut ürün bulunduğunda alanları otomatik doldur
  useEffect(() => {
    if (existingProduct) {
      const firstItem = items.find((i) => i.name.toLowerCase().trim() === name.toLowerCase().trim());
      if (firstItem) {
        if (!category) setCategory(firstItem.category ?? '');
        setUnit(firstItem.unit);
        if (!minStock) setMinStock(String(firstItem.min_stock_level));
        if (!costPerUnit && firstItem.cost_per_unit != null) setCost(String(firstItem.cost_per_unit));
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingProduct?.name]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await createItem({
        name,
        category: category || existingProduct?.category || undefined,
        quantity: parseFloat(quantity),
        unit: existingProduct?.unit || unit,
        min_stock_level: minStock ? parseFloat(minStock) : undefined,
        cost_per_unit: costPerUnit ? parseFloat(costPerUnit) : undefined,
        shelf_code: shelfCode || undefined,
        expiry_date: expiryDate || undefined,
        batch_number: batchNumber || undefined,
      });
      if (existingProduct) {
        toast.success(`"${name}" — yeni parti eklendi (Toplam: ${existingProduct.total_quantity + parseFloat(quantity)} ${existingProduct.unit || unit})`);
      } else {
        toast.success(`"${name}" stoğa eklendi`);
      }
      onClose();
    } catch {
      toast.error('Malzeme eklenemedi');
    } finally {
      setLoading(false);
    }
  }

  const inputCls = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-800">Malzeme Ekle</h2>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Malzeme Adı *</label>
            <input required value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Ör: Lateks Eldiven" className={inputCls} />
          </div>
          {/* Mevcut ürün bilgi banner'ı */}
          {existingProduct && (
            <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-blue-800">
                <Package className="h-4 w-4" />
                &quot;{existingProduct.name}&quot; zaten mevcut — Yeni parti ekleniyor
              </div>
              <div className="mt-1.5 text-xs text-blue-600 space-y-0.5">
                <p>Mevcut toplam: <b>{existingProduct.total_quantity} {existingProduct.unit}</b> ({existingProduct.batches.length} parti)</p>
                {existingProduct.nearest_expiry_date && (
                  <p>En yakın SKT: {formatDate(existingProduct.nearest_expiry_date)} ({existingProduct.days_until_nearest_expiry} gün)</p>
                )}
                <p className="text-blue-500 mt-1">
                  Farklı bir <b>Son Kullanma Tarihi</b> veya <b>Parti No</b> girerek yeni parti oluşturabilirsiniz.
                  Aynı SKT + Parti No girerseniz mevcut partinin miktarına eklenir.
                </p>
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Miktar *</label>
              <input required type="number" min="0" step="any" value={quantity}
                onChange={(e) => setQuantity(e.target.value)} placeholder="100" className={inputCls} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Birim *</label>
              <select value={unit} onChange={(e) => setUnit(e.target.value)} className={inputCls}>
                <option value="adet">adet</option>
                <option value="kg">kg</option>
                <option value="litre">litre</option>
                <option value="kutu">kutu</option>
                <option value="paket">paket</option>
                <option value="ml">ml</option>
                <option value="cift">çift</option>
                <option value="kavanoz">kavanoz</option>
              </select>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Kategori</label>
            <input value={category} onChange={(e) => setCategory(e.target.value)}
              placeholder="Ör: sarf / ilaç / araç" className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Raf Kodu</label>
              <input value={shelfCode} onChange={(e) => setShelfCode(e.target.value)}
                placeholder="Ör: A1" className={inputCls} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">SKT</label>
              <input type="date" value={expiryDate} onChange={(e) => setExpiry(e.target.value)}
                className={inputCls} />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Parti / Lot Numarası</label>
            <input value={batchNumber} onChange={(e) => setBatch(e.target.value)}
              placeholder="Ör: LOT-2026-05A" className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Min. Stok</label>
              <input type="number" min="0" step="any" value={minStock}
                onChange={(e) => setMinStock(e.target.value)} placeholder="10" className={inputCls} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Birim Maliyet (₺)</label>
              <input type="number" min="0" step="any" value={costPerUnit}
                onChange={(e) => setCost(e.target.value)} placeholder="5.50" className={inputCls} />
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={onClose} className="flex-1">İptal</Button>
            <Button type="submit" disabled={loading} className="flex-1">
              {loading ? 'Ekleniyor...' : 'Ekle'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Edit Item Modal ────────────────────────────────────────────────────────

function EditItemModal({ item, onClose }: { item: InventoryItem; onClose: () => void }) {
  const { updateItem } = useInventory();
  const [name, setName]           = useState(item.name);
  const [category, setCategory]   = useState(item.category ?? '');
  const [unit, setUnit]           = useState(item.unit);
  const [minStock, setMinStock]   = useState(String(item.min_stock_level));
  const [costPerUnit, setCost]    = useState(item.cost_per_unit != null ? String(item.cost_per_unit) : '');
  const [shelfCode, setShelfCode] = useState(item.shelf_code ?? '');
  const [expiryDate, setExpiry]   = useState(item.expiry_date ?? '');
  const [loading, setLoading]     = useState(false);

  const inputCls = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await updateItem(item.id, {
        name,
        category: category || undefined,
        unit,
        min_stock_level: minStock ? parseFloat(minStock) : undefined,
        cost_per_unit: costPerUnit ? parseFloat(costPerUnit) : undefined,
        shelf_code: shelfCode || undefined,
        expiry_date: expiryDate || undefined,
      });
      toast.success('Malzeme güncellendi');
      onClose();
    } catch {
      toast.error('Güncelleme başarısız');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-800">Malzeme Düzenle</h2>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Malzeme Adı</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Birim</label>
              <select value={unit} onChange={(e) => setUnit(e.target.value)} className={inputCls}>
                <option value="adet">adet</option>
                <option value="kg">kg</option>
                <option value="litre">litre</option>
                <option value="kutu">kutu</option>
                <option value="paket">paket</option>
                <option value="ml">ml</option>
                <option value="cift">çift</option>
                <option value="kavanoz">kavanoz</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Kategori</label>
              <input value={category} onChange={(e) => setCategory(e.target.value)}
                placeholder="sarf / ilaç / araç" className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Raf Kodu</label>
              <input value={shelfCode} onChange={(e) => setShelfCode(e.target.value)}
                placeholder="A1" className={inputCls} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">SKT</label>
              <input type="date" value={expiryDate} onChange={(e) => setExpiry(e.target.value)}
                className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Min. Stok</label>
              <input type="number" min="0" step="any" value={minStock}
                onChange={(e) => setMinStock(e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Birim Maliyet (₺)</label>
              <input type="number" min="0" step="any" value={costPerUnit}
                onChange={(e) => setCost(e.target.value)} className={inputCls} />
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={onClose} className="flex-1">İptal</Button>
            <Button type="submit" disabled={loading} className="flex-1">
              {loading ? 'Kaydediliyor...' : 'Kaydet'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Adjust Quantity Modal ──────────────────────────────────────────────────

function AdjustModal({ item, onClose }: { item: InventoryItem; onClose: () => void }) {
  const { adjustQuantity } = useInventory();
  const [delta, setDelta]   = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);

  const inputCls = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const d = parseFloat(delta);
    if (!d || d === 0) { toast.error('Geçerli bir miktar girin'); return; }
    setLoading(true);
    try {
      await adjustQuantity(item.id, d, reason || undefined);
      toast.success(`Miktar güncellendi: ${d > 0 ? '+' : ''}${d} ${item.unit}`);
      onClose();
    } catch {
      toast.error('Miktar güncellenemedi');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-800">Miktar Düzenle</h2>
            <p className="text-xs text-slate-500">{item.name} — Mevcut: {item.quantity} {item.unit}</p>
          </div>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Değişim Miktarı *
            </label>
            <input
              required
              type="number"
              step="any"
              value={delta}
              onChange={(e) => setDelta(e.target.value)}
              placeholder="Eklemek için +10, azaltmak için -5"
              className={inputCls}
            />
            <p className="mt-1 text-xs text-slate-400">Pozitif = stok ekle, Negatif = stok düş</p>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Sebep (opsiyonel)</label>
            <input value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="Ör: Teslim alındı" className={inputCls} />
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={onClose} className="flex-1">İptal</Button>
            <Button type="submit" disabled={loading} className="flex-1">
              {loading ? 'Güncelleniyor...' : 'Uygula'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Item Detail + History Modal ────────────────────────────────────────────

function ItemDetailModal({ item, onClose }: { item: InventoryItem; onClose: () => void }) {
  const [history, setHistory] = useState<InventoryAdjustment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    inventoryApi.getHistory(item.id)
      .then((res) => setHistory(res.data as InventoryAdjustment[]))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [item.id]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-4 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-slate-800">{item.name}</h2>
            <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
              {item.category && <span className="bg-slate-100 px-2 py-0.5 rounded">{item.category}</span>}
              {item.shelf_code && (
                <span className="font-mono font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded">
                  {item.shelf_code}
                </span>
              )}
              <span className={item.is_low_stock ? 'text-red-600 font-semibold' : ''}>
                Stok: {item.quantity} {item.unit}
              </span>
              {item.cost_per_unit != null && <span>Birim Maliyet: ₺{item.cost_per_unit.toFixed(2)}</span>}
              {item.expiry_date && <span>SKT: {formatDate(item.expiry_date)}</span>}
            </div>
          </div>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100 shrink-0 ml-4">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        {/* History */}
        <div className="overflow-y-auto flex-1 px-6 py-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
            <History className="h-4 w-4" />
            Hareket Geçmişi
          </h3>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-12 rounded-lg bg-slate-100 animate-pulse" />
              ))}
            </div>
          ) : history.length === 0 ? (
            <div className="rounded-lg border border-slate-200 py-10 text-center text-sm text-slate-400">
              Henüz hareket kaydı yok
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full">
                <thead>
                  <tr className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                    <th className="px-4 py-2.5 text-left">Tarih / Saat</th>
                    <th className="px-4 py-2.5 text-right">Değişim</th>
                    <th className="px-4 py-2.5 text-left">Sebep</th>
                    <th className="px-4 py-2.5 text-left">Yapan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {history.map((h) => {
                    const isAdd = h.delta > 0;
                    return (
                      <tr key={h.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 text-sm text-slate-600 whitespace-nowrap">
                          {new Date(h.created_at).toLocaleString('tr-TR', {
                            day: '2-digit', month: '2-digit', year: 'numeric',
                            hour: '2-digit', minute: '2-digit',
                          })}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className={`inline-flex items-center gap-1 text-sm font-semibold ${isAdd ? 'text-green-600' : 'text-red-600'}`}>
                            {isAdd
                              ? <TrendingUp className="h-3.5 w-3.5" />
                              : <TrendingDown className="h-3.5 w-3.5" />}
                            {isAdd ? '+' : ''}{h.delta} {item.unit}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {h.reason ?? <span className="text-slate-300 italic">—</span>}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {h.performed_by_email ?? <span className="text-slate-300 italic">—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="border-t border-slate-200 px-6 py-4 shrink-0">
          <Button variant="secondary" onClick={onClose} className="w-full">Kapat</Button>
        </div>
      </div>
    </div>
  );
}

// ── End Cycle Modal ────────────────────────────────────────────────────────

function EndCycleModal({ cycle, onClose }: { cycle: CycleMaterial; onClose: () => void }) {
  const { endCycle } = useInventory();
  const [endReason, setEndReason] = useState('');
  const [wasteNote, setWasteNote] = useState('');
  const [loading, setLoading]     = useState(false);

  const inputCls = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await endCycle({
        qr_id: cycle.qr_id,
        end_reason: endReason || undefined,
        waste_note: wasteNote || undefined,
      });
      if ((res as { is_high_waste?: boolean }).is_high_waste) {
        toast.warning('Döngü kapatıldı — Yüksek israf tespit edildi!');
      } else {
        toast.success('Döngü başarıyla kapatıldı');
      }
      onClose();
    } catch {
      toast.error('Döngü kapatılamadı');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-800">Döngüyü Bitir</h2>
            <p className="text-xs text-slate-500">{cycle.name}
              {cycle.shelf_code && ` · ${cycle.shelf_code}`}
            </p>
          </div>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Bitiş Sebebi</label>
            <input value={endReason} onChange={(e) => setEndReason(e.target.value)}
              placeholder="Ör: Ömrünü tamamladı" className={inputCls} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">İsraf Notu</label>
            <textarea value={wasteNote} onChange={(e) => setWasteNote(e.target.value)}
              rows={2} placeholder="Erken bozulma, kırılma vb." className={inputCls} />
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={onClose} className="flex-1">İptal</Button>
            <Button type="submit" disabled={loading} className="flex-1 bg-red-600 hover:bg-red-700">
              {loading ? 'Kapatılıyor...' : 'Döngüyü Kapat'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

const ALARM_KEY = 'dentai_skt_alarm_days';

function AlarmModal({ current, onSave, onClose }: {
  current: number;
  onSave: (days: number) => void;
  onClose: () => void;
}) {
  const [days, setDays] = useState(String(current));
  const inputCls = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200';

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const n = parseInt(days);
    if (!n || n < 1) { toast.error('Geçerli bir gün sayısı girin'); return; }
    onSave(n);
    toast.success(`SKT alarmı ${n} gün öncesine ayarlandı`);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-800">SKT Alarm Ayarı</h2>
            <p className="text-xs text-slate-500">Son kullanma tarihi yaklaşan malzemeler vurgulanır</p>
          </div>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Kaç gün öncesinden uyarsın?
            </label>
            <div className="flex items-center gap-3">
              <input
                required
                type="number"
                min="1"
                max="365"
                value={days}
                onChange={(e) => setDays(e.target.value)}
                className={inputCls}
              />
              <span className="shrink-0 text-sm text-slate-500">gün</span>
            </div>
            <p className="mt-1.5 text-xs text-slate-400">
              Örn: 30 → SKT'ye 30 gün kaldığında turuncu uyarı gösterilir.
            </p>
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={onClose} className="flex-1">İptal</Button>
            <Button type="submit" className="flex-1">Kaydet</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function InventoryPage() {
  const { items, cycles, batchSummaries, loading, error, refresh, deleteItem } = useInventory();
  const { data: wasteData, loading: wasteLoading }  = useWasteReport();
  const [showQR, setShowQR]                         = useState(false);
  const [qrPrefill, setQrPrefill]                   = useState<{ name: string; category: string | null } | undefined>();
  const [showAddItem, setShowAddItem]               = useState(false);
  const [editingItem, setEditingItem]               = useState<InventoryItem | null>(null);
  const [adjustingItem, setAdjustingItem]           = useState<InventoryItem | null>(null);
  const [viewingItem, setViewingItem]               = useState<InventoryItem | null>(null);
  const [endingCycle, setEndingCycle]               = useState<CycleMaterial | null>(null);
  const [activeTab, setActiveTab]                   = useState<'items' | 'cycles'>('items');
  const [viewMode, setViewMode]                     = useState<'summary' | 'detail'>('summary');
  const [expandedProduct, setExpandedProduct]       = useState<string | null>(null);
  const [showAlarm, setShowAlarm]                   = useState(false);
  const [sktAlarmDays, setSktAlarmDays]             = useState<number>(() => {
    if (typeof window === 'undefined') return 30;
    return parseInt(localStorage.getItem(ALARM_KEY) ?? '30') || 30;
  });

  function handleSaveAlarm(days: number) {
    localStorage.setItem(ALARM_KEY, String(days));
    setSktAlarmDays(days);
  }

  const highWasteCount = cycles.filter((c) => c.is_high_waste).length;

  // FEFO: Uyarıları batch summary üzerinden hesapla (en yakın SKT'ye göre)
  const lowStockCount  = batchSummaries.filter((s) => s.is_low_stock).length;
  const sktWarnCount   = batchSummaries.filter((s) =>
    s.nearest_expiry_date && new Date(s.nearest_expiry_date) <= new Date(Date.now() + sktAlarmDays * 86400e3)
  ).length;

  // Batch ID → InventoryItem eşlemesi (detay işlemleri için)
  const itemById = new Map(items.map((i) => [i.id, i]));

  function openQrForItem(item: InventoryItem) {
    setQrPrefill({ name: item.name, category: item.category });
    setShowQR(true);
  }

  async function handleDelete(item: InventoryItem) {
    if (!confirm(`"${item.name}" kalemini silmek istediğinize emin misiniz?`)) return;
    try {
      await deleteItem(item.id);
      toast.success(`"${item.name}" silindi`);
    } catch {
      toast.error('Silme işlemi başarısız');
    }
  }

  function toggleExpand(productName: string) {
    setExpandedProduct(expandedProduct === productName ? null : productName);
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-3">
          {lowStockCount > 0 && (
            <div className="relative flex items-center gap-1.5 rounded-full bg-orange-100 px-3 py-1 text-xs font-medium text-orange-700 animate-pulse">
              <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-orange-500" />
              </span>
              <AlertTriangle className="h-3.5 w-3.5" />
              {lowStockCount} düşük stok uyarısı
            </div>
          )}
          {sktWarnCount > 0 && (
            <div className="relative flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-700 cursor-pointer animate-pulse"
              onClick={() => setActiveTab('items')}>
              <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500" />
              </span>
              <Bell className="h-3.5 w-3.5" />
              {sktWarnCount} malzemenin SKT'si {sktAlarmDays} gün içinde doluyor
            </div>
          )}
          {highWasteCount > 0 && (
            <div className="flex items-center gap-1.5 rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-700">
              <AlertTriangle className="h-3.5 w-3.5" />
              {highWasteCount} yüksek israf malzeme
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" />
            Yenile
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setShowAddItem(true)}>
            <PackagePlus className="h-4 w-4" />
            Malzeme Ekle
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setShowAlarm(true)}>
            <Bell className="h-4 w-4" />
            Alarm ({sktAlarmDays}g)
          </Button>
          <Button size="sm" onClick={() => setShowQR(true)}>
            <QrCode className="h-4 w-4" />
            QR Üret
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-600">
          ⚠ {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 rounded-xl bg-slate-100 p-1 w-fit">
          {(['items', 'cycles'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab === 'items' ? (
                <span className="flex items-center gap-1.5">
                  <Package className="h-4 w-4" /> Sarf Malzemeleri
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <QrCode className="h-4 w-4" /> QR Döngüler
                </span>
              )}
            </button>
          ))}
        </div>
        {/* Görünüm modu: Özet (Batch Summary) vs Detay (Bireysel Parti) */}
        {activeTab === 'items' && (
          <div className="flex gap-1 rounded-xl bg-slate-100 p-1">
            <button
              onClick={() => setViewMode('summary')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                viewMode === 'summary'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Toplam Stok
            </button>
            <button
              onClick={() => setViewMode('detail')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                viewMode === 'detail'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Partiler
            </button>
          </div>
        )}
      </div>

      {/* Items Tab — Batch Summary View (Toplam Stok) */}
      {activeTab === 'items' && viewMode === 'summary' && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3 text-left w-8"></th>
                  <th className="px-4 py-3 text-left">Malzeme</th>
                  <th className="px-4 py-3 text-left">Kategori</th>
                  <th className="px-4 py-3 text-right">Toplam Stok</th>
                  <th className="px-4 py-3 text-right">Parti</th>
                  <th className="px-4 py-3 text-left">En Yakın SKT</th>
                  <th className="px-4 py-3 text-left">Durum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} cols={7} />)
                ) : batchSummaries.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-sm text-slate-400">
                      Stok kalemi bulunamadı
                    </td>
                  </tr>
                ) : (
                  batchSummaries.map((summary) => {
                    const isExpanded = expandedProduct === summary.name;
                    const expiryWarning = summary.nearest_expiry_date
                      ? new Date(summary.nearest_expiry_date) <= new Date(Date.now() + sktAlarmDays * 86400e3)
                      : false;
                    const isExpired = summary.days_until_nearest_expiry != null && summary.days_until_nearest_expiry < 0;

                    return (
                      <>{/* Summary row */}
                      <tr
                        key={summary.name}
                        className={`hover:bg-slate-50 transition-colors cursor-pointer ${isExpanded ? 'bg-blue-50/40' : ''}`}
                        onClick={() => toggleExpand(summary.name)}
                      >
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-block transition-transform duration-200 text-slate-400 ${isExpanded ? 'rotate-90' : ''}`}>
                            ▶
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <p className={`font-medium ${(summary.is_low_stock || expiryWarning) ? 'text-red-600' : 'text-slate-800'}`}>
                            {summary.name}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {summary.category ?? '—'}
                        </td>
                        <td className={`px-4 py-3 text-right text-sm font-semibold ${summary.is_low_stock ? 'text-red-600' : 'text-slate-700'}`}>
                          <span className="inline-flex items-center gap-0.5">
                            {summary.total_quantity} {summary.unit}
                            <BatchTooltip summary={summary} />
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-sm">
                          <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700">
                            {summary.batches.length} parti
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {summary.nearest_expiry_date ? (
                            <span className={
                              isExpired
                                ? 'font-bold text-red-600'
                                : expiryWarning
                                ? 'font-semibold text-orange-600'
                                : 'text-slate-500'
                            }>
                              {formatDate(summary.nearest_expiry_date)}
                              {isExpired && ' ⛔'}
                              {!isExpired && expiryWarning && ' ⚠'}
                              {summary.days_until_nearest_expiry != null && (
                                <span className="ml-1 text-xs opacity-75">
                                  ({isExpired ? `${Math.abs(summary.days_until_nearest_expiry)}g geçmiş` : `${summary.days_until_nearest_expiry}g`})
                                </span>
                              )}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-3">
                          {isExpired ? (
                            <Badge variant="red" className="animate-pulse">
                              <AlertTriangle className="mr-1 h-3 w-3" />
                              SKT Geçmiş
                            </Badge>
                          ) : summary.is_low_stock ? (
                            <Badge variant="red" className="animate-pulse">
                              <AlertTriangle className="mr-1 h-3 w-3" />
                              Düşük Stok
                            </Badge>
                          ) : expiryWarning ? (
                            <Badge variant="orange">
                              <Clock className="mr-1 h-3 w-3" />
                              SKT Yakın
                            </Badge>
                          ) : (
                            <Badge variant="green">Normal</Badge>
                          )}
                        </td>
                      </tr>
                      {/* Expanded batch rows */}
                      {isExpanded && summary.batches.map((batch, bIdx) => {
                        const batchItem = itemById.get(batch.batch_id);
                        const batchExpiryWarn = batch.expiry_date
                          ? new Date(batch.expiry_date) <= new Date(Date.now() + sktAlarmDays * 86400e3)
                          : false;
                        const batchExpired = batch.days_until_expiry != null && batch.days_until_expiry < 0;
                        return (
                          <tr key={batch.batch_id} className="bg-blue-50/20 hover:bg-blue-50/40 transition-colors">
                            <td className="px-4 py-2 text-center">
                              <span className="text-blue-300 text-xs">└</span>
                            </td>
                            <td className="px-4 py-2 text-sm pl-8">
                              <span className="font-mono text-xs font-medium text-blue-600 bg-blue-50 border border-blue-100 px-1.5 py-0.5 rounded">
                                {batch.batch_number ?? `Parti ${bIdx + 1}`}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-sm text-slate-400">—</td>
                            <td className={`px-4 py-2 text-right text-sm font-medium ${batch.is_low_stock ? 'text-red-600' : 'text-slate-600'}`}>
                              {batch.quantity} {summary.unit}
                            </td>
                            <td className="px-4 py-2"></td>
                            <td className="px-4 py-2 text-sm">
                              {batch.expiry_date ? (
                                <span className={
                                  batchExpired ? 'font-bold text-red-600' :
                                  batchExpiryWarn ? 'font-semibold text-orange-600' :
                                  'text-slate-500'
                                }>
                                  {formatDate(batch.expiry_date)}
                                  {batch.days_until_expiry != null && (
                                    <span className="ml-1 text-xs opacity-75">
                                      ({batchExpired ? `${Math.abs(batch.days_until_expiry)}g geçmiş` : `${batch.days_until_expiry}g`})
                                    </span>
                                  )}
                                </span>
                              ) : '—'}
                            </td>
                            <td className="px-4 py-2">
                              {batchItem && (
                                <div className="flex items-center justify-end gap-1">
                                  <button title="Miktar Düzenle" onClick={(e) => { e.stopPropagation(); setAdjustingItem(batchItem); }}
                                    className="rounded p-1 text-slate-400 hover:bg-green-50 hover:text-green-600 transition-colors">
                                    <Pencil className="h-3.5 w-3.5" />
                                  </button>
                                  <button title="Düzenle" onClick={(e) => { e.stopPropagation(); setEditingItem(batchItem); }}
                                    className="rounded p-1 text-slate-400 hover:bg-amber-50 hover:text-amber-600 transition-colors">
                                    <PlusCircle className="h-3.5 w-3.5" />
                                  </button>
                                  <button title="Geçmiş" onClick={(e) => { e.stopPropagation(); setViewingItem(batchItem); }}
                                    className="rounded p-1 text-slate-400 hover:bg-purple-50 hover:text-purple-600 transition-colors">
                                    <History className="h-3.5 w-3.5" />
                                  </button>
                                  <button title="Sil" onClick={(e) => { e.stopPropagation(); handleDelete(batchItem); }}
                                    className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors">
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                      </>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Items Tab — Detail View (Bireysel Partiler) */}
      {activeTab === 'items' && viewMode === 'detail' && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3 text-left">Malzeme</th>
                  <th className="px-4 py-3 text-left">Parti</th>
                  <th className="px-4 py-3 text-left">Kategori</th>
                  <th className="px-4 py-3 text-right">Miktar</th>
                  <th className="px-4 py-3 text-right">Min.</th>
                  <th className="px-4 py-3 text-right">Maliyet</th>
                  <th className="px-4 py-3 text-left">SKT</th>
                  <th className="px-4 py-3 text-left">Durum</th>
                  <th className="px-4 py-3 text-right">İşlem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} cols={9} />)
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-12 text-center text-sm text-slate-400">
                      Stok kalemi bulunamadı
                    </td>
                  </tr>
                ) : (
                  items.map((item) => {
                    const expiryWarning = item.expiry_date
                      ? new Date(item.expiry_date) <= new Date(Date.now() + sktAlarmDays * 86400e3)
                      : false;
                    return (
                      <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3 text-sm">
                          <p className={`font-medium ${(item.is_low_stock || expiryWarning) ? 'animate-pulse text-red-600' : 'text-slate-800'}`}>{item.name}</p>
                          {item.shelf_code && (
                            <span className="font-mono text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded">
                              {item.shelf_code}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {item.batch_number ? (
                            <span className="font-mono text-xs font-medium text-blue-600 bg-blue-50 border border-blue-100 px-1.5 py-0.5 rounded">
                              {item.batch_number}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {item.category ?? '—'}
                        </td>
                        <td className={`px-4 py-3 text-right text-sm font-semibold ${item.is_low_stock ? 'animate-pulse text-red-600' : 'text-slate-700'}`}>
                          <span className="inline-flex items-center gap-0.5">
                            {item.quantity} {item.unit}
                            {(() => {
                              const summary = batchSummaries.find((s) => s.name === item.name);
                              return summary && summary.batches.length > 1 ? (
                                <BatchTooltip summary={summary} />
                              ) : null;
                            })()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-sm text-slate-400">
                          {item.min_stock_level} {item.unit}
                        </td>
                        <td className="px-4 py-3 text-right text-sm text-slate-500">
                          {item.cost_per_unit != null ? `₺${item.cost_per_unit.toFixed(2)}` : '—'}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {item.expiry_date ? (
                            <span className={expiryWarning ? 'animate-pulse font-semibold text-orange-600' : 'text-slate-500'}>
                              {formatDate(item.expiry_date)}
                              {expiryWarning && ' ⚠'}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-3">
                          {item.is_low_stock ? (
                            <Badge variant="red" className="animate-pulse">
                              <AlertTriangle className="mr-1 h-3 w-3" />
                              Düşük Stok
                            </Badge>
                          ) : (
                            <Badge variant="green">Normal</Badge>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              title="QR Üret"
                              onClick={() => openQrForItem(item)}
                              className="rounded p-1.5 text-slate-400 hover:bg-blue-50 hover:text-blue-600 transition-colors"
                            >
                              <QrCode className="h-4 w-4" />
                            </button>
                            <button
                              title="Miktar Düzenle"
                              onClick={() => setAdjustingItem(item)}
                              className="rounded p-1.5 text-slate-400 hover:bg-green-50 hover:text-green-600 transition-colors"
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                            <button
                              title="Düzenle"
                              onClick={() => setEditingItem(item)}
                              className="rounded p-1.5 text-slate-400 hover:bg-amber-50 hover:text-amber-600 transition-colors"
                            >
                              <PlusCircle className="h-4 w-4" />
                            </button>
                            <button
                              title="Hareket Geçmişi"
                              onClick={() => setViewingItem(item)}
                              className="rounded p-1.5 text-slate-400 hover:bg-purple-50 hover:text-purple-600 transition-colors"
                            >
                              <History className="h-4 w-4" />
                            </button>
                            <button
                              title="Sil"
                              onClick={() => handleDelete(item)}
                              className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Cycles Tab */}
      {activeTab === 'cycles' && (
        <div className="space-y-5">
          {/* Waste category summary */}
          {!wasteLoading && wasteData && wasteData.by_category.length > 0 && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-5">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-700">
                <AlertTriangle className="h-4 w-4" />
                İsraf Özeti — Kategori Bazlı
              </h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {wasteData.by_category.map((c) => (
                  <div key={c.category} className="rounded-lg bg-white border border-red-100 p-3">
                    <p className="text-xs font-medium text-slate-700">{c.category}</p>
                    <p className="mt-1 text-lg font-bold text-red-600">
                      %{c.waste_rate_pct?.toFixed(0) ?? '—'}
                    </p>
                    <p className="text-xs text-slate-400">israf oranı</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                    <th className="px-4 py-3 text-left">Malzeme</th>
                    <th className="px-4 py-3 text-left">Raf</th>
                    <th className="px-4 py-3 text-left">Başlangıç</th>
                    <th className="px-4 py-3 text-left">Bitiş</th>
                    <th className="px-4 py-3 text-right">Act. / Bek.</th>
                    <th className="px-4 py-3 text-left">Durum</th>
                    <th className="px-4 py-3 text-right">İşlem</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} cols={7} />)
                  ) : cycles.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-sm text-slate-400">
                        Döngüsel malzeme bulunamadı
                      </td>
                    </tr>
                  ) : (
                    cycles.map((c) => {
                      // Show activated_at (with time) if available, otherwise start_date
                      const startDisplay = c.activated_at
                        ? new Date(c.activated_at).toLocaleString('tr-TR', {
                            day: '2-digit', month: '2-digit', year: 'numeric',
                            hour: '2-digit', minute: '2-digit',
                          })
                        : c.start_date ? formatDate(c.start_date) : '—';

                      return (
                        <tr key={c.id} className={`hover:bg-slate-50 transition-colors ${c.is_high_waste ? 'bg-red-50/50' : ''}`}>
                          <td className="px-4 py-3 text-sm font-medium text-slate-800">
                            {c.name}
                            {c.category && (
                              <span className="ml-1 text-xs text-slate-400">· {c.category}</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            {c.shelf_code ? (
                              <span className="font-mono font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded text-xs tracking-wide">
                                {c.shelf_code}
                              </span>
                            ) : '—'}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600">
                            <div className="flex items-center gap-1">
                              {c.activated_at && <Clock className="h-3 w-3 text-slate-400 shrink-0" />}
                              {startDisplay}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-500">
                            {c.end_date ? formatDate(c.end_date) : '—'}
                          </td>
                          <td className="px-4 py-3 text-right text-sm">
                            <span className={c.is_high_waste ? 'font-semibold text-red-600' : 'text-slate-600'}>
                              {c.actual_lifespan ?? '—'}
                            </span>
                            {c.expected_lifespan && (
                              <span className="text-slate-400"> / {c.expected_lifespan} gün</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {c.is_high_waste ? (
                              <Badge variant="red">
                                <AlertTriangle className="mr-1 h-3 w-3" />
                                Yüksek İsraf
                              </Badge>
                            ) : c.is_active ? (
                              <Badge variant="green">Aktif</Badge>
                            ) : (
                              <Badge variant="slate">Pasif</Badge>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {c.is_active && (
                              <button
                                title="Döngüyü Bitir"
                                onClick={() => setEndingCycle(c)}
                                className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                              >
                                <CheckCircle2 className="h-4 w-4" />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Alarm Modal */}
      {showAlarm && (
        <AlarmModal
          current={sktAlarmDays}
          onSave={handleSaveAlarm}
          onClose={() => setShowAlarm(false)}
        />
      )}

      {/* QR Modal */}
      {showQR && (
        <QRModal
          prefill={qrPrefill}
          onClose={() => { setShowQR(false); setQrPrefill(undefined); }}
        />
      )}

      {/* Add Item Modal */}
      {showAddItem && <AddItemModal onClose={() => { setShowAddItem(false); refresh(); }} />}

      {/* Edit Item Modal */}
      {editingItem && <EditItemModal item={editingItem} onClose={() => { setEditingItem(null); refresh(); }} />}

      {/* Adjust Quantity Modal */}
      {adjustingItem && <AdjustModal item={adjustingItem} onClose={() => { setAdjustingItem(null); refresh(); }} />}

      {/* Item Detail / History Modal */}
      {viewingItem && <ItemDetailModal item={viewingItem} onClose={() => setViewingItem(null)} />}

      {/* End Cycle Modal */}
      {endingCycle && <EndCycleModal cycle={endingCycle} onClose={() => { setEndingCycle(null); refresh(); }} />}
    </div>
  );
}
