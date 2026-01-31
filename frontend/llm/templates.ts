import type { NarrativeIntent } from "./intents";
import type { GameProfile } from "./profiles";

export type TemplateContext = {
  value?: number;
  baseline?: number | null;
  sampleSize?: number;
  confidence?: number;
  mapName?: string;
  phase?: string;
  round?: number;
  bestAction?: string;
  bestWinProb?: number;
};

const templatePool: Record<string, Record<NarrativeIntent, string[]>> = {
  valorant: {
    RESOURCE_SNOWBALL: [
      "当前回合结构显示经济处于被动，连续失利正放大滚雪球风险，后续回合将更难进入完整装备节奏。",
      "经济差正在累积，若不及时止损，后续回合的资源配置会持续受限。",
    ],
    OPENING_PHASE_INSTABILITY: [
      "开局阶段的稳定性不足，首轮劣势让全局节奏被迫后置。",
      "手枪/开局回合转换率偏低，导致早期节奏难以建立。",
    ],
    MID_GAME_TIMING_PRESSURE: [
      "中期决策触发较晚，执行常落在低时间窗口，成功率因此受压。",
      "在时间余量不足时才发起执行，进攻窗口被压缩，容错率降低。",
    ],
    OBJECTIVE_TRADE_INEFFICIENCY: [
      "资源交换未能形成正向 trade，地图控制价值被让渡。",
      "在资源转换上缺乏效率，当前节奏未能换取等值控制。",
    ],
    HIGH_VARIANCE_PATTERN: [
      "表现波动较大，回合结果高度依赖个别节点，缺乏稳定转化。",
      "回合质量不稳定，呈现 boom-or-bust 结构，需要关注持续性。",
    ],
    WEAK_SIGNAL_LOW_CONFIDENCE: [
      "样本量有限，信号偏弱，当前结论仅供复盘参考。",
      "数据支撑不足，暂不具备强结论，仅提示潜在趋势。",
    ],
  },
  lol: {
    RESOURCE_SNOWBALL: [
      "经济差距正在逐步放大，滚雪球效应可能主导后续节奏。",
      "资源倾斜导致节奏失衡，需警惕经济继续扩大。",
    ],
    OPENING_PHASE_INSTABILITY: [
      "前期节奏受阻，未能建立优势起点，后续运营被动。",
      "早期决策效率偏低，难以在前期抢占主动权。",
    ],
    MID_GAME_TIMING_PRESSURE: [
      "中期窗口把握不足，资源转换效率偏低，节奏被拖慢。",
      "关键时间点选择保守，未能在中期建立节奏优势。",
    ],
    OBJECTIVE_TRADE_INEFFICIENCY: [
      "目标资源控制不理想，换资源时机未能换取等值收益。",
      "在地图目标的博弈中收益不足，资源转换未达预期。",
    ],
    HIGH_VARIANCE_PATTERN: [
      "状态起伏明显，局面高度依赖个别团战/节点，稳定性不足。",
      "表现呈高波动特征，需更多样本验证趋势。",
    ],
    WEAK_SIGNAL_LOW_CONFIDENCE: [
      "样本有限，趋势尚不稳定，需更多对局验证。",
      "信号偏弱，目前仅作为观察点而非结论。",
    ],
  },
};

function formatNumber(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return value.toFixed(2);
}

export function renderTemplate(intent: NarrativeIntent, profile: GameProfile, ctx: TemplateContext): string {
  const pool = templatePool[profile.id]?.[intent] ?? [];
  const chosen = pool[0] ?? "样本量有限，当前信号偏弱，仅供参考。";
  const uncertainty = ctx.confidence !== undefined && ctx.confidence < 0.4 ? "样本支撑有限，请谨慎解读。" : "";
  const baselineText = ctx.baseline !== undefined ? `基线=${formatNumber(ctx.baseline)}` : "";
  const valueText = ctx.value !== undefined ? `观测=${formatNumber(ctx.value)}` : "";
  const deltaText = ctx.value !== undefined && ctx.baseline !== undefined && ctx.baseline !== null
    ? `Δ=${formatNumber(ctx.value - ctx.baseline)}`
    : "";
  const sampleText = ctx.sampleSize !== undefined ? `样本=${ctx.sampleSize}` : "";
  const facts = [valueText, baselineText, deltaText, sampleText].filter(Boolean).join(" · ");
  const bestActionText = ctx.bestAction && ctx.bestWinProb !== undefined
    ? `当前最优可分辨动作：${ctx.bestAction}（胜率=${formatNumber(ctx.bestWinProb)}）`
    : "";
  const contextText = [facts, bestActionText, uncertainty].filter(Boolean).join(" | ");
  return contextText ? `${chosen} ${contextText}` : chosen;
}