import type { NarrativeIntent } from "./intents";

export type AnalysisCulture = {
  primaryFocus: string[];
  typicalLanguageTone: string;
};

export type IntentFraming = {
  framing: string[];
  explanationBias: string;
};

export type GameProfile = {
  id: "valorant" | "lol";
  temporalModel: "round-based" | "continuous";
  resourceModel: "hard-econ" | "soft-econ";
  analysisCulture: AnalysisCulture;
  intentFraming: Record<NarrativeIntent, IntentFraming>;
};

export const VALORANT_PROFILE: GameProfile = {
  id: "valorant",
  temporalModel: "round-based",
  resourceModel: "hard-econ",
  analysisCulture: {
    primaryFocus: ["round economy", "opening duels", "tempo control", "utility trade", "man-advantage conversion"],
    typicalLanguageTone: "tactical, round-centric, consequence-driven",
  },
  intentFraming: {
    RESOURCE_SNOWBALL: {
      framing: ["经济滚雪球", "回合失败后的连锁反应", "无法进入完整装备回合"],
      explanationBias: "round-to-round consequence",
    },
    OPENING_PHASE_INSTABILITY: {
      framing: ["手枪局丢失", "开局节奏不稳定", "首轮决斗成功率偏低"],
      explanationBias: "early-round leverage",
    },
    MID_GAME_TIMING_PRESSURE: {
      framing: ["中期决策时间偏晚", "进攻启动犹豫", "被迫在低时间窗口强行执行"],
      explanationBias: "clock pressure",
    },
    OBJECTIVE_TRADE_INEFFICIENCY: {
      framing: ["资源交换不理想", "地图控制让渡", "未能形成有效 trade"],
      explanationBias: "map control vs value",
    },
    HIGH_VARIANCE_PATTERN: {
      framing: ["表现波动较大", "boom-or-bust 回合结构", "缺乏稳定转化"],
      explanationBias: "round volatility",
    },
    WEAK_SIGNAL_LOW_CONFIDENCE: {
      framing: ["样本量有限", "信号偏弱", "暂不具备强结论"],
      explanationBias: "analyst caution",
    },
  },
};

export const LOL_PROFILE: GameProfile = {
  id: "lol",
  temporalModel: "continuous",
  resourceModel: "soft-econ",
  analysisCulture: {
    primaryFocus: ["early pathing", "objective control", "gold distribution", "map pressure", "scaling vs tempo"],
    typicalLanguageTone: "macro-oriented, flow-based, pressure-aware",
  },
  intentFraming: {
    RESOURCE_SNOWBALL: {
      framing: ["经济差距逐步放大", "滚雪球效应", "资源倾斜导致节奏失衡"],
      explanationBias: "gold & tempo accumulation",
    },
    OPENING_PHASE_INSTABILITY: {
      framing: ["前期节奏受阻", "早期决策效率偏低", "未能建立优势起点"],
      explanationBias: "early game leverage",
    },
    MID_GAME_TIMING_PRESSURE: {
      framing: ["中期决策窗口把握不足", "资源转换效率偏低", "关键时间点选择保守"],
      explanationBias: "mid-game window",
    },
    OBJECTIVE_TRADE_INEFFICIENCY: {
      framing: ["目标资源控制不理想", "换资源时机不佳", "地图收益转化不足"],
      explanationBias: "objective economy",
    },
    HIGH_VARIANCE_PATTERN: {
      framing: ["状态起伏明显", "依赖个别回合/团战", "稳定性不足"],
      explanationBias: "performance consistency",
    },
    WEAK_SIGNAL_LOW_CONFIDENCE: {
      framing: ["样本有限", "趋势尚不稳定", "需要更多对局验证"],
      explanationBias: "statistical caution",
    },
  },
};

export function getGameProfile(gameId?: string | null): GameProfile {
  if (gameId?.toLowerCase() === "lol" || gameId?.toLowerCase() === "league" || gameId?.toLowerCase() === "leagueoflegends") {
    return LOL_PROFILE;
  }
  return VALORANT_PROFILE;
}