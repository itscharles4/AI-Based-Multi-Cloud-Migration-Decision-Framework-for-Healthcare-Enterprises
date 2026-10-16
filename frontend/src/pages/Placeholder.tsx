// src/pages/Placeholder.tsx — stub for pages being developed
import type { LucideIcon } from 'lucide-react';
import { Construction } from 'lucide-react';

export default function Placeholder({ title, desc }: { title: string; desc?: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <Construction size={40} className="mb-4" style={{ color: 'var(--muted)' }} />
      <h1 className="text-2xl font-bold mb-2" style={{ color: 'var(--text)' }}>{title}</h1>
      <p className="text-sm max-w-sm" style={{ color: 'var(--muted)' }}>
        {desc ?? 'This page is part of Track B and is coming soon.'}
      </p>
    </div>
  );
}
