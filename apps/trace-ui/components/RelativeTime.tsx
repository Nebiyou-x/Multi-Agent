"use client";

import { useEffect, useState } from "react";
import { formatDistanceToNow, parseISO } from "date-fns";

export function RelativeTime({ iso }: { iso: string }) {
  const [text, setText] = useState<string | null>(null);

  useEffect(() => {
    const update = () => setText(formatDistanceToNow(parseISO(iso), { addSuffix: true }));
    update();
    // Refresh once a minute so "3 minutes ago" doesn't go stale on a long-open tab.
    const id = setInterval(update, 60_000);
    return () => clearInterval(id);
  }, [iso]);

  // Render nothing on the server; the Suspense fallback ("—") covers the gap.
  if (text === null) return null;
  return <>{text}</>;
}