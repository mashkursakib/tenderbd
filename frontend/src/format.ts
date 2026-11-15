// Locale helpers. Dates and numbers use bn-BD when Bangla is active,
// en-GB otherwise. Tender DATA itself always stays as published by
// e-GP in English.

import type { Lang } from './i18n';

export function localeFor(lang: Lang): string {
  return lang === 'bn' ? 'bn-BD' : 'en-GB';
}

export function fmtNum(value: number, lang: Lang): string {
  return new Intl.NumberFormat(localeFor(lang)).format(value);
}

export function fmtDate(iso: string | null | undefined, lang: Lang): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(localeFor(lang), {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(d);
}

export function fmtDateTime(iso: string | null | undefined, lang: Lang): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(localeFor(lang), {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d);
}

export function fmtTimeAgo(iso: string | null | undefined, lang: Lang): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return lang === 'bn' ? 'এইমাত্র' : 'just now';
  if (mins < 60) {
    return lang === 'bn'
      ? `${fmtNum(mins, lang)} মিনিট আগে`
      : `${mins} min ago`;
  }
  const hours = Math.floor(mins / 60);
  if (hours < 24) {
    return lang === 'bn'
      ? `${fmtNum(hours, lang)} ঘণ্টা আগে`
      : `${hours} hr ago`;
  }
  const days = Math.floor(hours / 24);
  if (days < 30) {
    return lang === 'bn'
      ? `${fmtNum(days, lang)} দিন আগে`
      : `${days} days ago`;
  }
  return fmtDate(iso, lang);
}

/** Days from now until the closing date (negative when closed). */
export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.ceil((d.getTime() - Date.now()) / 86400000);
}

/**
 * Compact BDT: 1 crore = 10,000,000, 1 lakh = 100,000.
 * e.g. 25000000 -> "2.5 Cr", 450000 -> "4.5 Lakh".
 */
export function compactBdt(value: number, lang: Lang): string {
  const trim = (n: number): string => {
    const rounded = Math.round(n * 100) / 100;
    return new Intl.NumberFormat(localeFor(lang), {
      maximumFractionDigits: 2,
    }).format(rounded);
  };
  if (value >= 10000000) return `${trim(value / 10000000)} Cr`;
  if (value >= 100000) return `${trim(value / 100000)} Lakh`;
  return fmtNum(value, lang);
}

export function fmtBdt(value: number, lang: Lang): string {
  return `BDT ${fmtNum(value, lang)}`;
}

/** "BDT 2.5 Cr tender security" style badge text (compact value). */
export function securityBadge(value: number | null | undefined, lang: Lang): string | null {
  if (value === null || value === undefined) return null;
  return `BDT ${compactBdt(value, lang)}`;
}

export function fmtFileSize(bytes: number | null | undefined, lang: Lang): string {
  if (bytes === null || bytes === undefined) return '';
  if (bytes < 1024) return `${fmtNum(bytes, lang)} B`;
  if (bytes < 1024 * 1024) return `${fmtNum(Math.round(bytes / 1024), lang)} KB`;
  return `${new Intl.NumberFormat(localeFor(lang), {
    maximumFractionDigits: 1,
  }).format(bytes / (1024 * 1024))} MB`;
}
