export type DeploymentMode = 'self_hosted' | 'cloud';
export type PlanCode = 'community_core' | 'cloud_basic' | 'cloud_pro' | 'cloud_premium';

export type AppCapabilitiesCompat = {
  isPremium: boolean;
  people: boolean;
  ownership: boolean;
};

export type AppCapabilitiesV2 = {
  deploymentMode: DeploymentMode;
  planCode: PlanCode;
  capabilitiesVersion: number;
  platform: {
    selfHosted: boolean;
    cloudHosted: boolean;
    appAuth: boolean;
    cloudManagedServices: boolean;
    cloudMultiDeviceAccess: boolean;
    pwaMinimal: boolean;
    mobileAppNative: boolean;
  };
  core: {
    netWorth: boolean;
    dataInput: boolean;
    budget: boolean;
    accountingBasic: boolean;
    accountingMovementsManual: boolean;
    investmentPortfolioBasic: boolean;
    statsBasic: boolean;
    dataPortabilityBasic: boolean;
    onboardingAssisted: boolean;
  };
  pro: {
    guide: boolean;
    guidanceBasic: boolean;
    goals: boolean;
    simulatorBasic: boolean;
    smartNotificationsBasic: boolean;
    assistedMonthlyClose: boolean;
  };
  premium: {
    familyMode: boolean;
    agentAdvanced: boolean;
    simulatorAdvanced: boolean;
    portfolioAnalyticsAdvanced: boolean;
    communityBenchmarkingAnonymous: boolean;
    inputCaptureAdvanced: boolean;
    importBulkAdvanced: boolean;
    astraSignalsInfo: boolean;
  };
  saas: {
    accountPage: boolean;
    adminInternal: boolean;
    billingPortal: boolean;
  };
  compat: AppCapabilitiesCompat;
};

export type AppCapabilities = AppCapabilitiesV2 & AppCapabilitiesCompat;

function buildCompat(capabilities: AppCapabilitiesV2): AppCapabilitiesCompat {
  return {
    isPremium: capabilities.planCode === 'cloud_pro' || capabilities.planCode === 'cloud_premium',
    people: capabilities.premium.familyMode,
    ownership: capabilities.premium.familyMode,
  };
}

function withCompat(base: Omit<AppCapabilitiesV2, 'compat'>): AppCapabilities {
  const compat = buildCompat(base as AppCapabilitiesV2);
  return {
    ...base,
    compat,
    ...compat,
  };
}

export const capabilities: AppCapabilities = withCompat({
  deploymentMode: 'self_hosted',
  planCode: 'community_core',
  capabilitiesVersion: 1,
  platform: {
    selfHosted: true,
    cloudHosted: false,
    appAuth: true,
    cloudManagedServices: false,
    cloudMultiDeviceAccess: false,
    pwaMinimal: false,
    mobileAppNative: false,
  },
  core: {
    netWorth: true,
    dataInput: true,
    budget: true,
    accountingBasic: true,
    accountingMovementsManual: false,
    investmentPortfolioBasic: false,
    statsBasic: true,
    dataPortabilityBasic: true,
    onboardingAssisted: false,
  },
  pro: {
    guide: false,
    guidanceBasic: false,
    goals: false,
    simulatorBasic: false,
    smartNotificationsBasic: false,
    assistedMonthlyClose: false,
  },
  premium: {
    familyMode: false,
    agentAdvanced: false,
    simulatorAdvanced: false,
    portfolioAnalyticsAdvanced: false,
    communityBenchmarkingAnonymous: false,
    inputCaptureAdvanced: false,
    importBulkAdvanced: false,
    astraSignalsInfo: false,
  },
  saas: {
    accountPage: false,
    adminInternal: false,
    billingPortal: false,
  },
});

export type CapabilityPath =
  | 'platform.appAuth'
  | 'platform.pwaMinimal'
  | 'platform.mobileAppNative'
  | 'core.netWorth'
  | 'core.dataInput'
  | 'core.budget'
  | 'core.accountingBasic'
  | 'core.accountingMovementsManual'
  | 'core.investmentPortfolioBasic'
  | 'core.onboardingAssisted'
  | 'pro.guide'
  | 'pro.guidanceBasic'
  | 'pro.goals'
  | 'pro.simulatorBasic'
  | 'pro.smartNotificationsBasic'
  | 'pro.assistedMonthlyClose'
  | 'premium.familyMode'
  | 'premium.agentAdvanced'
  | 'premium.simulatorAdvanced'
  | 'premium.portfolioAnalyticsAdvanced'
  | 'premium.communityBenchmarkingAnonymous'
  | 'premium.inputCaptureAdvanced'
  | 'premium.importBulkAdvanced'
  | 'premium.astraSignalsInfo'
  | 'saas.accountPage'
  | 'saas.adminInternal'
  | 'saas.billingPortal';

function getByPath(source: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (!acc || typeof acc !== 'object') return undefined;
    return (acc as Record<string, unknown>)[key];
  }, source);
}

export function hasCapability(path: CapabilityPath, source: AppCapabilities = capabilities): boolean {
  return getByPath(source as unknown as Record<string, unknown>, path) === true;
}

export function isCloudDeployment(source: AppCapabilities = capabilities): boolean {
  return source.deploymentMode === 'cloud';
}

export function canUseGuide(source: AppCapabilities = capabilities): boolean {
  return source.pro.guide;
}

export function canUseFamilyMode(source: AppCapabilities = capabilities): boolean {
  return source.premium.familyMode;
}

export function canUsePeople(source: AppCapabilities = capabilities): boolean {
  return source.compat.people;
}

export function canUseOwnership(source: AppCapabilities = capabilities): boolean {
  return source.compat.ownership;
}

export function canUseAdminInternal(source: AppCapabilities = capabilities): boolean {
  return source.saas.adminInternal;
}
