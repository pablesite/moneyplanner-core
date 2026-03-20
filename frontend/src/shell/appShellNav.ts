export type NavItem = {
  id: string;
  icon: string;
  label: string;
  hint: string;
  to: string;
};

export const appShellNavItems: NavItem[] = [
  { id: 'home', icon: 'GU', label: 'Guia', hint: 'Plan paso a paso', to: '/' },
  {
    id: 'net-worth',
    icon: 'PT',
    label: 'Patrimonio',
    hint: 'Estado financiero',
    to: '/patrimonio',
  },
  {
    id: 'budget',
    icon: 'PR',
    label: 'Presupuesto',
    hint: 'Plan anual de ingresos y gastos',
    to: '/presupuesto',
  },
  {
    id: 'monthly-close',
    icon: 'CM',
    label: 'Cierre mensual',
    hint: 'Liquidez, ingresos, gastos y residual',
    to: '/cierre-mensual',
  },
  {
    id: 'accounting-movements',
    icon: 'LD',
    label: 'Movimientos',
    hint: 'Libro diario y cuentas contables',
    to: '/movimientos',
  },
];
