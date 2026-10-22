"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Template } from "@/lib/types";
import { Badge } from "./ui";

export function useFavorites() {
  const [favorites, setFavorites] = useState<number[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get<number[]>("/templates/favorites").then(setFavorites).catch(e => setError(e.message)); }, []);
  const toggle = async (id: number) => {
    const favorite = !favorites.includes(id);
    setBusy(id); setError("");
    try {
      await api.put(`/templates/${id}/favorite`, { favorite });
      setFavorites(ids => favorite ? [...ids.filter(x => x !== id), id] : ids.filter(x => x !== id));
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };
  const sort = (items: Template[]) => [...items].sort((a, b) => Number(favorites.includes(b.id)) - Number(favorites.includes(a.id)));
  return { favorites, busy, error, toggle, sort };
}

export function FavoriteButton({ id, state }: { id: number; state: ReturnType<typeof useFavorites> }) {
  const selected = state.favorites.includes(id);
  return <button type="button" aria-label={selected ? "즐겨찾기 해제" : "즐겨찾기 추가"} aria-pressed={selected} title={selected ? "즐겨찾기 해제" : "즐겨찾기 추가"} disabled={state.busy !== null} onClick={() => state.toggle(id)} className={`rounded p-1 text-xl ${selected ? "text-amber-500" : "text-gray-400"} hover:bg-amber-50 disabled:opacity-50`}>{selected ? "★" : "☆"}</button>;
}

export function PastNoticeBadge({ template }: { template: Template }) {
  if (!template.library.project_code) return null;
  const explicit = (template.library.source_date || template.library.version || "").match(/(?:19|20)\d{2}/);
  const code = template.library.project_code.match(/^R(\d{2})/);
  const year = explicit ? Number(explicit[0]) : code ? 2000 + Number(code[1]) : null;
  return year && year < new Date().getFullYear() ? <Badge tone="amber">과거 공고 · {year}</Badge> : null;
}
