export type FamilyMember = {
  id: number;
  name: string;
  role: 'adult' | 'child';
  is_active: boolean;
};

export type OwnershipKind = 'individual' | 'shared';

export type OwnershipRead = {
  id: number;
  kind: OwnershipKind;
  member: { id: number; name: string; role: 'adult' | 'child' } | null;
  splits: { member: { id: number; name: string; role: 'adult' | 'child' }; percent: string }[];
  is_in_use: boolean;
};
