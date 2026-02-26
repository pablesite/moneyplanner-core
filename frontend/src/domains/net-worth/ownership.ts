export type OwnershipLink = {
  target_type: 'asset' | 'liability';
  target_id: number;
  ownership_id: number;
};

type WithId = {
  id: number;
};

export function buildOwnershipMaps(links: OwnershipLink[]) {
  const assetOwnership = new Map(
    links
      .filter((link) => link.target_type === 'asset')
      .map((link) => [link.target_id, link.ownership_id] as const),
  );

  const liabilityOwnership = new Map(
    links
      .filter((link) => link.target_type === 'liability')
      .map((link) => [link.target_id, link.ownership_id] as const),
  );

  return { assetOwnership, liabilityOwnership };
}

export function attachOwnershipRef<T extends WithId>(
  items: T[],
  ownershipMap: Map<number, number>,
) {
  return items.map((item) => ({
    ...item,
    ownership_ref: ownershipMap.get(item.id) ?? null,
  }));
}
