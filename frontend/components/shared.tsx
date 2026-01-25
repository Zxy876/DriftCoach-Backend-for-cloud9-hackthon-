export function formatConfidence(conf: number): string {
  const clamped = Math.max(0, Math.min(conf, 1));
  if (clamped >= 0.75) return `${clamped.toFixed(2)} (strong)`;
  if (clamped >= 0.5) return `${clamped.toFixed(2)} (moderate)`;
  return `${clamped.toFixed(2)} (weak)`;
}
