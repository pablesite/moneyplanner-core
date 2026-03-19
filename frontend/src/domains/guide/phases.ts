export type GuidePhase = {
  id: number;
  title: string;
  focus: string;
  objective: string;
  progress: number;
};

export const guidePhases: GuidePhase[] = [
  {
    id: 1,
    title: 'Deuda',
    focus: 'Eliminar deuda mala y ordenar pasivos',
    objective: 'Reducir intereses altos y deuda no respaldada.',
    progress: 100,
  },
  {
    id: 2,
    title: 'Flujo de caja',
    focus: 'Consolidar superavit mensual estable',
    objective: 'Mantener ingresos por encima de gastos de forma consistente.',
    progress: 68,
  },
  {
    id: 3,
    title: 'Fondo de emergencia',
    focus: 'Construir colchon de seguridad',
    objective: 'Acumular liquidez para cubrir imprevistos y gastos esenciales.',
    progress: 35,
  },
  {
    id: 4,
    title: 'Salud patrimonial',
    focus: 'Balancear activos y pasivos',
    objective: 'Mejorar apalancamiento, respaldo de deuda, concentracion y liquidez.',
    progress: 18,
  },
  {
    id: 5,
    title: 'Independencia financiera',
    focus: 'Elevar activos productivos',
    objective: 'Construir ingresos de activos que cubran el estilo de vida.',
    progress: 6,
  },
];

export function findGuidePhaseById(id: number): GuidePhase | null {
  return guidePhases.find((phase) => phase.id === id) ?? null;
}

export function getActiveGuidePhase(): GuidePhase {
  return guidePhases.find((phase) => phase.progress < 100) ?? guidePhases[guidePhases.length - 1]!;
}

export function guidePhaseDetailTo(phaseId: number): string {
  return `/guia/fases/${phaseId}`;
}
