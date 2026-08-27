"use client";

import { useState, useRef, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Icons } from "@/lib/types/components";
import { cn } from "@/lib/utils";
import { importLeadsCSV, ImportResult } from "@/lib/api/campaigns";

const FIELD_KEYS = [
  { key: "linkedin_url", label: "LinkedIn URL" },
  { key: "first_name", label: "First Name" },
  { key: "last_name", label: "Last Name" },
  { key: "company", label: "Company" },
  { key: "title", label: "Title" },
  { key: "email", label: "Work Email" },
  { key: "phone", label: "Phone" },
  { key: "company_domain", label: "Company Domain" },
] as const;

type FieldKey = (typeof FIELD_KEYS)[number]["key"];

const AUTO_DETECT: Record<string, FieldKey> = {
  "linkedin url": "linkedin_url",
  "linkedin": "linkedin_url",
  "linkedin profile": "linkedin_url",
  "profile url": "linkedin_url",
  "url": "linkedin_url",
  "first name": "first_name",
  "firstname": "first_name",
  "last name": "last_name",
  "lastname": "last_name",
  "company": "company",
  "company name": "company",
  "organization": "company",
  "title": "title",
  "job title": "title",
  "position": "title",
  "email": "email",
  "work email": "email",
  "email address": "email",
  "phone": "phone",
  "phone number": "phone",
  "mobile": "phone",
  "tel": "phone",
  "domain": "company_domain",
  "company domain": "company_domain",
  "website": "company_domain",
};

function detectMapping(headers: string[]): Record<string, string> {
  const map: Record<string, string> = {};
  const usedKeys = new Set<string>();
  for (const header of headers) {
    const normalized = header.trim().toLowerCase();
    const key = AUTO_DETECT[normalized];
    if (key && !usedKeys.has(key)) {
      map[key] = header;
      usedKeys.add(key);
    }
  }
  return map;
}

interface CsvImportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  campaignId: string;
  onImported?: () => void;
}

export function CsvImportModal({
  open,
  onOpenChange,
  campaignId,
  onImported,
}: CsvImportModalProps) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [preview, setPreview] = useState<Record<string, string>[]>([]);
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setStep(1);
    setFile(null);
    setHeaders([]);
    setPreview([]);
    setColumnMap({});
    setImporting(false);
    setResult(null);
    setDragOver(false);
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onOpenChange(false);
  }, [reset, onOpenChange]);

  const parseFile = useCallback((f: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const lines = text.split(/\r?\n/).filter(Boolean);
      if (lines.length === 0) return;
      const cols = lines[0].split(",").map((c) => c.replace(/^"|"$/g, "").trim());
      setHeaders(cols);
      const rows: Record<string, string>[] = [];
      for (let i = 1; i < Math.min(lines.length, 6); i++) {
        const vals = lines[i].split(",").map((v) => v.replace(/^"|"$/g, "").trim());
        const row: Record<string, string> = {};
        cols.forEach((col, idx) => { row[col] = vals[idx] ?? ""; });
        rows.push(row);
      }
      setPreview(rows);
      setColumnMap(detectMapping(cols));
      setStep(2);
    };
    reader.readAsText(f);
  }, []);

  const handleFileDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f && f.name.endsWith(".csv")) {
        setFile(f);
        parseFile(f);
      }
    },
    [parseFile],
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) {
        setFile(f);
        parseFile(f);
      }
    },
    [parseFile],
  );

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    try {
      const res = await importLeadsCSV(campaignId, file, columnMap);
      if (res.data) {
        setResult(res.data);
        setStep(4);
        onImported?.();
      } else {
        setResult({ imported: 0, updated: 0, skipped: 0, errors: [res.error ?? "Import failed"] });
        setStep(4);
      }
    } finally {
      setImporting(false);
    }
  };

  const mappedFields = Object.keys(columnMap).filter((k) => columnMap[k]);
  const canImport =
    mappedFields.includes("linkedin_url") || mappedFields.includes("email");

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
      <DialogContent className="sm:max-w-[600px] bg-zinc-950 border-zinc-800 text-zinc-100">
        <DialogHeader className="border-b border-zinc-800 pb-4">
          <DialogTitle>Import Leads from CSV</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Step {step} of 4
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="py-4 space-y-4">
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors",
                dragOver
                  ? "border-blue-500 bg-blue-500/10"
                  : "border-zinc-700 hover:border-zinc-500 hover:bg-zinc-900/50",
              )}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <Icons.Upload className="h-10 w-10 mx-auto mb-3 text-zinc-500" />
              <p className="text-sm text-zinc-300 font-medium">
                Drag & drop a CSV file, or click to browse
              </p>
              <p className="text-xs text-zinc-500 mt-1">Max 5,000 rows</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileInput}
              />
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="py-4 space-y-4">
            <p className="text-sm text-zinc-400">
              Map CSV columns to lead fields. At least one of{" "}
              <strong className="text-zinc-200">LinkedIn URL</strong> or{" "}
              <strong className="text-zinc-200">Email</strong> is required.
            </p>
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {FIELD_KEYS.map(({ key, label }) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="w-36 text-sm text-zinc-300 shrink-0">{label}</span>
                  <Select
                    value={columnMap[key] ?? "__none__"}
                    onValueChange={(v) =>
                      setColumnMap((prev) => ({
                        ...prev,
                        [key]: (v === "__none__" || !v) ? "" : v,
                      }))
                    }
                  >
                    <SelectTrigger className="flex-1 bg-zinc-900 border-zinc-700 text-zinc-100 h-8">
                      <SelectValue placeholder="(not mapped)" />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-700">
                      <SelectItem value="__none__" className="text-zinc-400">
                        (not mapped)
                      </SelectItem>
                      {headers.map((h) => (
                        <SelectItem key={h} value={h} className="text-zinc-100">
                          {h}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>
            {preview.length > 0 && (
              <div className="rounded-md border border-zinc-800 overflow-x-auto">
                <table className="text-xs w-full">
                  <thead>
                    <tr className="border-b border-zinc-800 bg-zinc-900/50">
                      {headers.slice(0, 5).map((h) => (
                        <th key={h} className="px-2 py-1.5 text-left text-zinc-400 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((row, i) => (
                      <tr key={i} className="border-b border-zinc-900">
                        {headers.slice(0, 5).map((h) => (
                          <td key={h} className="px-2 py-1.5 text-zinc-300 truncate max-w-[100px]">
                            {row[h]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {step === 3 && file && (
          <div className="py-4 space-y-4">
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">File</span>
                <span className="text-zinc-200 font-medium">{file.name}</span>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {mappedFields.map((k) => (
                  <Badge key={k} variant="secondary" className="text-xs bg-zinc-800 text-zinc-200">
                    {FIELD_KEYS.find((f) => f.key === k)?.label ?? k}
                  </Badge>
                ))}
              </div>
            </div>
            {!canImport && (
              <p className="text-xs text-amber-400">
                Map at least one of LinkedIn URL or Email to proceed.
              </p>
            )}
          </div>
        )}

        {step === 4 && result && (
          <div className="py-4 space-y-4">
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Imported", value: result.imported, color: "text-emerald-400" },
                { label: "Updated", value: result.updated, color: "text-blue-400" },
                { label: "Skipped", value: result.skipped, color: "text-zinc-400" },
              ].map(({ label, value, color }) => (
                <div key={label} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 text-center">
                  <div className={cn("text-3xl font-bold", color)}>{value}</div>
                  <div className="text-xs text-zinc-400 mt-1">{label}</div>
                </div>
              ))}
            </div>
            {result.errors.length > 0 && (
              <details className="rounded-md border border-zinc-800">
                <summary className="px-3 py-2 text-sm text-amber-400 cursor-pointer select-none">
                  {result.errors.length} error{result.errors.length !== 1 ? "s" : ""}
                </summary>
                <ul className="px-3 pb-3 space-y-1 max-h-40 overflow-y-auto">
                  {result.errors.map((e, i) => (
                    <li key={i} className="text-xs text-zinc-400 font-mono">{e}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}

        <DialogFooter className="border-t border-zinc-800 pt-4 gap-2">
          {step === 1 && (
            <Button variant="outline" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800" onClick={handleClose}>
              Cancel
            </Button>
          )}
          {step === 2 && (
            <>
              <Button variant="outline" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button
                disabled={!canImport}
                onClick={() => setStep(3)}
                className="bg-blue-600 hover:bg-blue-700"
              >
                Continue
              </Button>
            </>
          )}
          {step === 3 && (
            <>
              <Button variant="outline" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button
                disabled={!canImport || importing}
                onClick={handleImport}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {importing ? (
                  <>
                    <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    Importing...
                  </>
                ) : (
                  "Import Leads"
                )}
              </Button>
            </>
          )}
          {step === 4 && (
            <Button onClick={handleClose} className="bg-zinc-700 hover:bg-zinc-600">
              Done
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
