// Word-level diff via LCS, designed for the "compare two runs" page.
// O(n*m) - capped at 2000 tokens per side so a huge final answer can't
// freeze the tab; beyond the cap we fall back to a whole-text flag.
export type DiffPart = { type: "same" | "add" | "del"; text: string };

const CAP = 2000;

function wordify(s: string): string[] {
  const w = s.split(/(\s+)/).filter(Boolean);
  return w.length > CAP ? w.slice(0, CAP) : w;
}

export function diffWords(a: string, b: string): DiffPart[] {
  const A = wordify(a);
  const B = wordify(b);
  const n = A.length,
    m = B.length;

  // LCS table (rows = A, cols = B)
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);

  // Walk to emit parts, coalescing consecutive same/add/del runs
  const parts: DiffPart[] = [];
  let i = 0,
    j = 0;
  const push = (type: DiffPart["type"], text: string) => {
    if (!text) return;
    const last = parts[parts.length - 1];
    if (last && last.type === type) last.text += text;
    else parts.push({ type, text });
  };

  while (i < n && j < m) {
    if (A[i] === B[j]) {
      push("same", A[i]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push("del", A[i]);
      i++;
    } else {
      push("add", B[j]);
      j++;
    }
  }
  while (i < n) push("del", A[i++]);
  while (j < m) push("add", B[j++]);
  return parts;
}

// Quick whole-text summary numbers for the diff header
export function diffStats(parts: DiffPart[]) {
  const same = parts.filter((p) => p.type === "same").map((p) => p.text).join("");
  const del = parts.filter((p) => p.type === "del").map((p) => p.text).join("");
  const add = parts.filter((p) => p.type === "add").map((p) => p.text).join("");
  return { same, add, del };
}
