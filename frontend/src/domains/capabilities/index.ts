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
    budget: boolean;
    accountingBasic: boolean;
    accountingMovementsManual: boolean;
    investmentPortfolioBasic: boolean;
    statsBasic: boolean;
    dataPortabilityBasic: boolean;
    onboardingAssisted: boolean;
    familyLogicalModel: boolean;
    coachV1: boolean;
    coachPhase5: boolean;
    financialSimulatorBasic: boolean;
    localAutomationHooks: boolean;
  };
  familyCloud: {
    memberLogins: boolean;
    memberPrivacy: boolean;
    sharedFamilyViews: boolean;
  };
  central: {
    communityBenchmarkAnonymous: boolean;
    computeHeavySimulation: boolean;
    llmConversationalAdvanced: boolean;
    astraModules: boolean;
    smartNotifications: boolean;
  };
  // Legacy packaging groups kept as compatibility bridge while UI/backend migrate.
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
    planManagement: boolean;
  };
  compat: AppCapabilitiesCompat;
};

export type AppCapabilities = AppCapabilitiesV2 & AppCapabilitiesCompat;

function buildCompat(capabilities: AppCapabilitiesV2): AppCapabilitiesCompat {
  return {
    isPremium: capabilities.planCode === 'cloud_pro' || capabilities.planCode === 'cloud_premium',
    people:
      capabilities.core.familyLogicalModel ||
      capabilities.familyCloud.sharedFamilyViews ||
      capabilities.premium.familyMode,
    ownership: capabilities.core.familyLogicalModel || capabilities.premium.familyMode,
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
    budget: true,
    accountingBasic: true,
    accountingMovementsManual: false,
    investmentPortfolioBasic: false,
    statsBasic: true,
    dataPortabilityBasic: true,
    onboardingAssisted: false,
    familyLogicalModel: true,
    coachV1: true,
    coachPhase5: false,
    financialSimulatorBasic: false,
    localAutomationHooks: false,
  },
  familyCloud: {
    memberLogins: false,
    memberPrivacy: false,
    sharedFamilyViews: false,
  },
  central: {
    communityBenchmarkAnonymous: false,
    computeHeavySimulation: false,
    llmConversationalAdvanced: false,
    astraModules: false,
    smartNotifications: false,
  },
  pro: {
    guide: true,
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
    planManagement: false,
  },
});

export type CapabilityPath =
  | 'platform.appAuth'
  | 'platform.cloudManagedServices'
  | 'platform.cloudMultiDeviceAccess'
  | 'platform.pwaMinimal'
  | 'platform.mobileAppNative'
  | 'core.netWorth'
  | 'core.budget'
  | 'core.accountingBasic'
  | 'core.accountingMovementsManual'
  | 'core.investmentPortfolioBasic'
  | 'core.statsBasic'
  | 'core.dataPortabilityBasic'
  | 'core.onboardingAssisted'
  | 'core.familyLogicalModel'
  | 'core.coachV1'
  | 'core.coachPhase5'
  | 'core.financialSimulatorBasic'
  | 'core.localAutomationHooks'
  | 'familyCloud.memberLogins'
  | 'familyCloud.memberPrivacy'
  | 'familyCloud.sharedFamilyViews'
  | 'central.communityBenchmarkAnonymous'
  | 'central.computeHeavySimulation'
  | 'central.llmConversationalAdvanced'
  | 'central.astraModules'
  | 'central.smartNotifications'
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
  | 'saas.billingPortal'
  | 'saas.planManagement';

function getByPath(source: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (!acc || typeof acc !== 'object') return undefined;
    return (acc as Record<string, unknown>)[key];
  }, source);
}

export function hasCapability(
  path: CapabilityPath,
  source: AppCapabilities = capabilities,
): boolean {
  return getByPath(source as unknown as Record<string, unknown>, path) === true;
}

export function isCloudDeployment(source: AppCapabilities = capabilities): boolean {
  return source.deploymentMode === 'cloud';
}

export function canUseGuide(source: AppCapabilities = capabilities): boolean {
  return source.core.coachV1 || source.pro.guide;
}

export function canUseFamilyMode(source: AppCapabilities = capabilities): boolean {
  return source.familyCloud.sharedFamilyViews || source.premium.familyMode;
}

export function canUsePeople(source: AppCapabilities = capabilities): boolean {
  return (
    source.core.familyLogicalModel || source.familyCloud.sharedFamilyViews || source.compat.people
  );
}

export function canUseOwnership(source: AppCapabilities = capabilities): boolean {
  return source.core.familyLogicalModel || source.compat.ownership;
}

export function canUseAdminInternal(source: AppCapabilities = capabilities): boolean {
  return source.saas.adminInternal;
}
