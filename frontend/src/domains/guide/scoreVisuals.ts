export type ScoreGrade = 'A' | 'B' | 'C' | 'D' | 'E';

type ScorePalette = {
  color: string;
  badgeText: string;
  badgeBg: string;
  badgeBorder: string;
};

const SCORE_PALETTES: Record<ScoreGrade, ScorePalette> = {
  A: {
    color: 'hsl(138 78% 44%)',
    badgeText: 'hsl(138 78% 62%)',
    badgeBg: 'hsl(138 78% 44% / 0.16)',
    badgeBorder: 'hsl(138 78% 62% / 0.26)',
  },
  B: {
    color: 'hsl(82 90% 52%)',
    badgeText: 'hsl(82 90% 62%)',
    badgeBg: 'hsl(82 90% 52% / 0.16)',
    badgeBorder: 'hsl(82 90% 62% / 0.26)',
  },
  C: {
    color: 'hsl(58 88% 50%)',
    badgeText: 'hsl(58 88% 60%)',
    badgeBg: 'hsl(58 88% 50% / 0.14)',
    badgeBorder: 'hsl(58 88% 60% / 0.24)',
  },
  D: {
    color: 'hsl(30 90% 54%)',
    badgeText: 'hsl(30 90% 64%)',
    badgeBg: 'hsl(30 90% 54% / 0.16)',
    badgeBorder: 'hsl(30 90% 64% / 0.26)',
  },
  E: {
    color: 'hsl(0 86% 58%)',
    badgeText: 'hsl(0 86% 68%)',
    badgeBg: 'hsl(0 86% 58% / 0.16)',
    badgeBorder: 'hsl(0 86% 68% / 0.26)',
  },
};

export function gradeFromScore(score: number): ScoreGrade {
  if (score >= 80) return 'A';
  if (score >= 60) return 'B';
  if (score >= 40) return 'C';
  if (score >= 20) return 'D';
  return 'E';
}

export function scoreColor(score: number): string {
  return SCORE_PALETTES[gradeFromScore(score)].color;
}

export function scoreBadgeStyle(score: number): Record<string, string> {
  const palette = SCORE_PALETTES[gradeFromScore(score)];
  return {
    background: palette.badgeBg,
    color: palette.badgeText,
    borderColor: palette.badgeBorder,
  };
}
