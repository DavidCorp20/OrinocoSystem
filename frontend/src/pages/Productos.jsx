import { useCallback, useEffect, useRef, useState } from "react";
import { Download, MoreHorizontal, Package, Pencil, Plus, Search, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadCsv } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { fmtMoney, fmtNum, stockStatus } from "../lib/format";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../components/ui/dropdown-menu";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "../components/ui/alert-dialog";

const EMPTY = { name: "", sku: "", category: "", brand: "", supplier: "", purchase_price: "", sale_price: "", stock: "", min_stock: "5", max_stock: "", unit: "unidad" };

export default function Productos() {
  const { business } = useAuth();
  const currency = business?.currency || "USD";
  const [products, setProducts] = useState(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("todas");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [toDelete, setToDelete] = useState(null);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(() => {
    const params = {};
    if (search) params.search = search;
    if (category !== "todas") params.category = category;
    api.get("/products", { params }).then((r) => setProducts(r.data.products)).catch((e) => toast.error(apiError(e)));
  }, [search, category]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  const categories = [...new Set((products || []).map((p) => p.category).filter(Boolean))];

  const openCreate = () => { setEditing(null); setForm(EMPTY); setDialogOpen(true); };
  const openEdit = (p) => {
    setEditing(p);
    setForm({
      name: p.name, sku: p.sku || "", category: p.category || "", brand: p.brand || "",
      supplier: p.supplier || "", purchase_price: p.purchase_price, sale_price: p.sale_price,
      stock: p.stock, min_stock: p.min_stock, max_stock: p.max_stock ?? "", unit: p.unit || "unidad",
    });
    setDialogOpen(true);
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    const payload = {
      ...form,
      sku: form.sku || null, category: form.category || null, brand: form.brand || null,
      supplier: form.supplier || null, max_stock: form.max_stock === "" ? null : Number(form.max_stock),
      purchase_price: Number(form.purchase_price) || 0, sale_price: Number(form.sale_price) || 0,
      stock: Number(form.stock) || 0, min_stock: Number(form.min_stock) || 0,
    };
    try {
      if (editing) {
        await api.put(`/products/${editing.id}`, payload);
        toast.success("Producto actualizado");
      } else {
        await api.post("/products", payload);
        toast.success("Producto creado");
      }
      setDialogOpen(false);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    try {
      await api.delete(`/products/${toDelete.id}`);
      toast.success(`"${toDelete.name}" eliminado`);
      setToDelete(null);
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const doImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/products/import", fd);
      toast.success(`${data.created} producto(s) importado(s)`);
      load();
    } catch (err) {
      toast.error(apiError(err, "No pudimos importar el archivo."));
    } finally {
      e.target.value = "";
    }
  };

  const field = (key, label, props = {}) => (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input data-testid={`product-form-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} {...props} />
    </div>
  );

  return (
    <div className="space-y-5" data-testid="productos-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Productos</h1>
          <p className="text-sm text-muted-foreground mt-1">Tu catálogo y el stock actual de cada producto.</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input ref={fileRef} type="file" accept=".csv" className="hidden" data-testid="import-csv-file-input" onChange={doImport} />
          <Button variant="outline" data-testid="import-csv-btn" onClick={() => fileRef.current?.click()} className="rounded-xl">
            <Upload className="w-4 h-4 mr-1.5" /> Importar CSV
          </Button>
          <Button variant="outline" data-testid="export-products-csv-btn" onClick={() => downloadCsv("/products/export/csv", "productos.csv")} className="rounded-xl">
            <Download className="w-4 h-4 mr-1.5" /> Exportar CSV
          </Button>
          <Button data-testid="new-product-btn" onClick={openCreate} className="rounded-xl">
            <Plus className="w-4 h-4 mr-1.5" /> Nuevo producto
          </Button>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-56">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            data-testid="input-product-search" className="pl-10 rounded-xl" placeholder="Buscar por nombre, código o SKU…"
            value={search} onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger data-testid="select-category-filter" className="w-52 rounded-xl">
            <SelectValue placeholder="Categoría" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todas">Todas las categorías</SelectItem>
            {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden" data-testid="products-table-card">
        {!products ? (
          <div className="p-6 space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="h-10 bg-secondary rounded-xl animate-pulse" />)}</div>
        ) : products.length === 0 ? (
          <div className="p-12 text-center">
            <Package className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-semibold text-slate-800">Aún no tienes productos</p>
            <p className="text-sm text-muted-foreground mt-1 mb-4">Crea tu primer producto o impórtalos desde un archivo CSV.</p>
            <Button data-testid="empty-new-product-btn" onClick={openCreate} className="rounded-xl"><Plus className="w-4 h-4 mr-1.5" /> Crear producto</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="products-table">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border bg-secondary/50">
                  <th className="px-5 py-3 font-semibold">Producto</th>
                  <th className="px-4 py-3 font-semibold">Categoría</th>
                  <th className="px-4 py-3 font-semibold text-right">Precio venta</th>
                  <th className="px-4 py-3 font-semibold text-right">Costo</th>
                  <th className="px-4 py-3 font-semibold text-right">Stock</th>
                  <th className="px-4 py-3 font-semibold">Estado</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {products.map((p) => {
                  const st = stockStatus(p);
                  return (
                    <tr key={p.id} data-testid={`product-row-${p.id}`} className="hover:bg-secondary/40 transition-colors">
                      <td className="px-5 py-3">
                        <p className="font-medium text-slate-800">{p.name}</p>
                        <p className="text-xs text-muted-foreground font-num">{p.sku}{p.supplier ? ` · ${p.supplier}` : ""}</p>
                      </td>
                      <td className="px-4 py-3"><span className="text-xs bg-secondary px-2 py-0.5 rounded-full">{p.category}</span></td>
                      <td className="px-4 py-3 text-right font-num font-semibold">{fmtMoney(p.sale_price, currency)}</td>
                      <td className="px-4 py-3 text-right font-num text-muted-foreground">{fmtMoney(p.purchase_price, currency)}</td>
                      <td className="px-4 py-3 text-right font-num">{fmtNum(p.stock)} <span className="text-xs text-muted-foreground">/ mín {fmtNum(p.min_stock)}</span></td>
                      <td className="px-4 py-3"><span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${st.cls}`}>{st.label}</span></td>
                      <td className="px-4 py-3 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button data-testid={`product-actions-${p.id}`} className="p-1.5 rounded-lg hover:bg-secondary transition-colors">
                              <MoreHorizontal className="w-4 h-4" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem data-testid={`product-edit-${p.id}`} onClick={() => openEdit(p)}>
                              <Pencil className="w-3.5 h-3.5 mr-2" /> Editar
                            </DropdownMenuItem>
                            <DropdownMenuItem data-testid={`product-delete-${p.id}`} onClick={() => setToDelete(p)} className="text-rose-600">
                              <Trash2 className="w-3.5 h-3.5 mr-2" /> Eliminar
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent aria-describedby={undefined} className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="product-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">{editing ? "Editar producto" : "Nuevo producto"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="grid grid-cols-2 gap-3.5">
            <div className="col-span-2">{field("name", "Nombre *", { required: true, placeholder: "Ej. Martillo 16oz" })}</div>
            {field("sku", "Código / SKU", { placeholder: "Automático si lo dejas vacío" })}
            {field("category", "Categoría", { placeholder: "Ej. Herramientas" })}
            {field("purchase_price", "Costo de compra", { type: "number", min: "0", step: "any", required: true })}
            {field("sale_price", "Precio de venta", { type: "number", min: "0", step: "any", required: true })}
            {!editing && field("stock", "Unidades disponibles", { type: "number", min: "0", step: "any" })}
            {field("min_stock", "Stock mínimo (alerta)", { type: "number", min: "0", step: "any" })}
            {field("brand", "Marca")}
            {field("supplier", "Proveedor")}
            <div className="col-span-2 flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" data-testid="product-form-cancel" onClick={() => setDialogOpen(false)}>Cancelar</Button>
              <Button type="submit" data-testid="product-form-submit" disabled={saving} className="rounded-xl">
                {saving ? "Guardando…" : editing ? "Guardar cambios" : "Crear producto"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!toDelete} onOpenChange={() => setToDelete(null)}>
        <AlertDialogContent data-testid="product-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar "{toDelete?.name}"?</AlertDialogTitle>
            <AlertDialogDescription>El producto se quitará de tu catálogo. El historial de movimientos se conserva.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="product-delete-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction data-testid="product-delete-confirm" onClick={doDelete} className="bg-rose-600 hover:bg-rose-700">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
