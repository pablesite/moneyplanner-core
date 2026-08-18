# Changelog

## [0.42.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.41.0...moneyplanner-core-v0.42.0) (2026-08-17)


### Features

* **portfolio:** carrying value and manual resync from accounting ([e7e012a](https://github.com/pablesite/moneyplanner-core/commit/e7e012ab779895db37fc0cdf20f459895fded7e5))
* **portfolio:** let a position reassign its container and asset class ([c1891c5](https://github.com/pablesite/moneyplanner-core/commit/c1891c526866e0c0eb2165eded5abd7c4b1e60a8))


### Bug Fixes

* **portfolio:** count pre-opening dates as zero, not unknown ([f56677f](https://github.com/pablesite/moneyplanner-core/commit/f56677fbb7157d35eff53b4ac5c8e7b41c31c554))
* **portfolio:** follow accounting revaluations live ([8d6207e](https://github.com/pablesite/moneyplanner-core/commit/8d6207e634f3cf7b3b16c5c3e6d48e22dcdc38b3))
* **portfolio:** make the contributed series cumulative since inception ([d15e63c](https://github.com/pablesite/moneyplanner-core/commit/d15e63ccb3cf328031aa24db3e5ebe8d9f537b91))
* **portfolio:** make the time-weighted return actually time-weighted ([d85e4ad](https://github.com/pablesite/moneyplanner-core/commit/d85e4ad7f983306f7790b94b64e10f39aa95a0e7))
* **portfolio:** post manual valuations to accounting ([e058c53](https://github.com/pablesite/moneyplanner-core/commit/e058c53e36b28d7c9c3bd306921ae8cc14676ccc))
* **portfolio:** read divested positions as zero ([042063f](https://github.com/pablesite/moneyplanner-core/commit/042063f9aa67526d8d6148e83b4a826c83c145b7))
* **portfolio:** report carrying values as at_cost instead of ageing them ([dd350ed](https://github.com/pablesite/moneyplanner-core/commit/dd350eddfcb69a285c92707f5d15051c6b2cc8d4))

## [0.41.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.40.1...moneyplanner-core-v0.41.0) (2026-08-17)


### Features

* **portfolio:** add hybrid valuation layer ([377731c](https://github.com/pablesite/moneyplanner-core/commit/377731c366505ff12976b1e13fdf218b36a9e0a9))
* **portfolio:** add operations and CSV import ([b6c99ff](https://github.com/pablesite/moneyplanner-core/commit/b6c99ff9ff2ce3724ae677d4f2d0638e64fe224d))
* **portfolio:** add performance engine ([c3ca555](https://github.com/pablesite/moneyplanner-core/commit/c3ca555a5476d82e7085ab17cd3174387e50b243))
* **portfolio:** add portfolio domain foundation ([67159c8](https://github.com/pablesite/moneyplanner-core/commit/67159c81184c0b3ce9d5cdc34d0ff63d082ad8d5))


### Bug Fixes

* **budget:** reuse monthly close ledger maps ([dd1d67e](https://github.com/pablesite/moneyplanner-core/commit/dd1d67e3579f4b6b67bc3727a1acbe3383b85669))

## [0.40.1](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.40.0...moneyplanner-core-v0.40.1) (2026-08-15)


### Bug Fixes

* **monthly-close:** classify debt principal as savings ([372668a](https://github.com/pablesite/moneyplanner-core/commit/372668a707679963b9b1caf9afa5d4e4bd3c44b4))

## [0.40.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.39.1...moneyplanner-core-v0.40.0) (2026-08-15)


### Features

* **monthly-close:** expose role-aware financial result ([559ac5e](https://github.com/pablesite/moneyplanner-core/commit/559ac5ea80f9102501580530181381feedd0d9ba))


### Bug Fixes

* **monthly-close:** exclude explained liquidity adjustments from residual ([1a11375](https://github.com/pablesite/moneyplanner-core/commit/1a113758688c8be35d366ae22d995502172e6549))
* **settlement:** check wallets on activation date ([264a732](https://github.com/pablesite/moneyplanner-core/commit/264a7324c107c33da0019c5aff6d79129f124dcb))
* **settlement:** ignore subcent wallet residuals ([4b5d2c4](https://github.com/pablesite/moneyplanner-core/commit/4b5d2c4583ca0a4445a30561421570d53684fada))

## [0.39.1](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.39.0...moneyplanner-core-v0.39.1) (2026-08-15)


### Bug Fixes

* **budget:** isolate accepted monthly close residuals ([8703900](https://github.com/pablesite/moneyplanner-core/commit/870390090db7286f3d791f9b318e9ececa1367f3))
* **plan:** preserve ownership when editing scenarios ([b52a711](https://github.com/pablesite/moneyplanner-core/commit/b52a711d7fedcc582be2aacb0c4a7b2953370cd7))

## [0.39.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.38.2...moneyplanner-core-v0.39.0) (2026-08-14)


### Features

* **core:** refresh current FX quotes ([1b4b167](https://github.com/pablesite/moneyplanner-core/commit/1b4b1670167c72fd470d15b593dc1800a70b9112))


### Bug Fixes

* **frontend:** update nanoid security patch ([72c31ed](https://github.com/pablesite/moneyplanner-core/commit/72c31edf34fbfe761e6b3d0eee7d6cd762c8ee79))
* **plan:** assign ownership to generated budget lines ([f270879](https://github.com/pablesite/moneyplanner-core/commit/f270879da50ddf5b29f9b10912acccdf690a6461))

## [0.38.2](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.38.1...moneyplanner-core-v0.38.2) (2026-08-04)


### Bug Fixes

* **settlement:** decouple reserves from budget ownership ([0f9c5c8](https://github.com/pablesite/moneyplanner-core/commit/0f9c5c8b7578db129f646d41267e1219f495d49a))

## [0.38.1](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.38.0...moneyplanner-core-v0.38.1) (2026-08-04)


### Bug Fixes

* **settlement:** attribute income from movements ([2b15df5](https://github.com/pablesite/moneyplanner-core/commit/2b15df5d7fabcf1a9d41701b5acc7e2088d09106))

## [0.38.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.37.1...moneyplanner-core-v0.38.0) (2026-08-04)


### Features

* **ownership:** expose effective dynamic splits ([07240b5](https://github.com/pablesite/moneyplanner-core/commit/07240b50a824eddb05c040164d6dee149c77e466))

## [0.37.1](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.37.0...moneyplanner-core-v0.37.1) (2026-08-04)


### Bug Fixes

* **plan:** backfill forecast financing rows ([ef57be2](https://github.com/pablesite/moneyplanner-core/commit/ef57be270b8e8e8fb1bfef7f69e4e424b551553e))
* **plan:** expose existing member candidates ([c2df3c6](https://github.com/pablesite/moneyplanner-core/commit/c2df3c6d0c003fc7d022602bc522b8a44380342a))
* **plan:** sync forecast loan payments to budget ([e06321f](https://github.com/pablesite/moneyplanner-core/commit/e06321f3f3e3c49f68477b92e5494f044dad589e))

## [0.37.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.36.0...moneyplanner-core-v0.37.0) (2026-08-04)


### Features

* **monthly-close:** add dynamic ownership allocation ([8b9fba2](https://github.com/pablesite/moneyplanner-core/commit/8b9fba21b5eac15af76cc4a089926ee2b5512d2d))
* **monthly-close:** add ownership settlement preview ([7d402bd](https://github.com/pablesite/moneyplanner-core/commit/7d402bd6e0c8189275ff01857ebfd91ee8f4466c))
* **monthly-close:** add settlement configuration ([c759bb7](https://github.com/pablesite/moneyplanner-core/commit/c759bb7c7cc44f5f9a66571f95a0d9436f44c87e))
* **monthly-close:** execute settlement transfers ([abb1fd6](https://github.com/pablesite/moneyplanner-core/commit/abb1fd6b19de202ad7f126efbf5b42ca8a21e256))
* **monthly-close:** expose member settlement breakdown ([07ec672](https://github.com/pablesite/moneyplanner-core/commit/07ec672628a93e2a5b309653124e1417092c3d09))

## [0.36.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.35.3...moneyplanner-core-v0.36.0) (2026-08-02)


### Features

* **plan:** preview planned decision impact ([56020c9](https://github.com/pablesite/moneyplanner-core/commit/56020c9bcde00ac93c7114385196f0b261593e7f))


### Bug Fixes

* **plan:** allow editing accepted scenario events ([db83ed4](https://github.com/pablesite/moneyplanner-core/commit/db83ed404d9fbe4fcf53a5a0de9057330b703885))


### Performance Improvements

* **plan:** reuse dashboard diagnostics ([6dc826e](https://github.com/pablesite/moneyplanner-core/commit/6dc826e68a000f66cc297120746ff8c2beeb6406))

## [0.35.3](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.35.2...moneyplanner-core-v0.35.3) (2026-08-02)


### Bug Fixes

* **plan:** reconcile budget contributions with free cash ([266e26f](https://github.com/pablesite/moneyplanner-core/commit/266e26fc8c8fa050b2f48cc6b125f24793a50fa0))

## [0.35.2](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.35.1...moneyplanner-core-v0.35.2) (2026-08-02)


### Bug Fixes

* **plan:** compare scenarios on the date the plan headline shows ([efcf0ba](https://github.com/pablesite/moneyplanner-core/commit/efcf0bacd0a25c4282e18d9ba1e725e055e9bab4))
* **plan:** count a decision's instalment and running cost once each ([9f8cf2a](https://github.com/pablesite/moneyplanner-core/commit/9f8cf2a14c73194a473d2aa2a2bfc9541a54ce95))
* **plan:** judge the monthly close on the plan's own date ([36d9e05](https://github.com/pablesite/moneyplanner-core/commit/36d9e05b3595234efb4e450e2758a23df86d199f))
* **plan:** make contribution improvements actionable ([46aa5fc](https://github.com/pablesite/moneyplanner-core/commit/46aa5fccdd1829502f2641381992c1c769ab2d0e))

## [0.35.1](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.35.0...moneyplanner-core-v0.35.1) (2026-07-31)


### Bug Fixes

* **ci:** drop pip from the production image so Trivy can pass ([705ce1e](https://github.com/pablesite/moneyplanner-core/commit/705ce1ebad015f48e29e0af992cc9bea991ef660))

## [0.35.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.34.0...moneyplanner-core-v0.35.0) (2026-07-31)


### Features

* **net-worth:** expose historical asset composition ([e2fd260](https://github.com/pablesite/moneyplanner-core/commit/e2fd2608f19610765ae0e755f8b8aad694748d0c))
* **plan:** allocate free cash to emergency savings ([75e5bf1](https://github.com/pablesite/moneyplanner-core/commit/75e5bf1680581e9b9f464938d7857e14492d115f))
* **plan:** allow editing grouped planned decisions ([32c2d33](https://github.com/pablesite/moneyplanner-core/commit/32c2d338c4af15c5b7b487e045fd5fdfe9c8d1b5))
* **plan:** grade every foundation A-E and publish an overall health note ([6a69a21](https://github.com/pablesite/moneyplanner-core/commit/6a69a21220ba26f601c649624f7d7a7d1870f773))
* **plan:** project reconciled asset categories ([161698e](https://github.com/pablesite/moneyplanner-core/commit/161698e04c3704be8d8f1cb17ecd51a9cf2e3ef1))


### Bug Fixes

* **net-worth:** reconcile accounting mortgage cancellation ([7475a4b](https://github.com/pablesite/moneyplanner-core/commit/7475a4b37b7921c316851f3e5757669dfe23abe5))
* **plan:** allocate positive one-offs to security ([9b7c8b6](https://github.com/pablesite/moneyplanner-core/commit/9b7c8b6e12197e7a914af83c576fcb80ad48597a))
* **plan:** count only liability instalments as debt service, and score it ([38c1e8a](https://github.com/pablesite/moneyplanner-core/commit/38c1e8a98b260e44c83af545fd1bf12e1868d7c7))
* **plan:** ground foundations on effective values and fix two scorings ([1c88c2d](https://github.com/pablesite/moneyplanner-core/commit/1c88c2d320b67b439013a81c2ac28331713fd726))
* **plan:** judge data quality on the plan's adults, not the whole family ([911c40d](https://github.com/pablesite/moneyplanner-core/commit/911c40d73bdaaeb96fa6b1efc3ee417bb95dfb99))
* **plan:** let capital requirements use the horizon of the shown denominator ([0f9576a](https://github.com/pablesite/moneyplanner-core/commit/0f9576a97c2894faffa4641f55442ec5f0daf7a1))
* **plan:** preserve liquidity across linked cash flows ([d70eb01](https://github.com/pablesite/moneyplanner-core/commit/d70eb019babfe9f167dc7bf43e0b781121facf32))
* **plan:** reconcile financed asset sales ([477320a](https://github.com/pablesite/moneyplanner-core/commit/477320a86e392fc88a0415083052f80d3fbfb450))
* **plan:** reconcile monthly decision cash flow ([a830894](https://github.com/pablesite/moneyplanner-core/commit/a8308944a0feaf5f995692e90338e4e7e9a91c9e))
* **plan:** score the emergency fund against its own target ([b355089](https://github.com/pablesite/moneyplanner-core/commit/b355089225d58cd30cdd312ecad616666d9cc35d))

## [0.34.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.33.0...moneyplanner-core-v0.34.0) (2026-07-29)


### Features

* **plan:** incluir movimientos puntuales en la proyección y modelar venta de activos ([0d462f2](https://github.com/pablesite/moneyplanner-core/commit/0d462f2ba3c5f7490c0af9b6e63bf170e10974dd))
* **plan:** reconciliar la aportación con el superávit libre real de caja ([d34fe6a](https://github.com/pablesite/moneyplanner-core/commit/d34fe6a71e30bd69ddc03d04a02fc1534c5959e6))


### Bug Fixes

* **plan:** cancelar una decisión no debe borrar las partidas que solo adoptó ([2a85d45](https://github.com/pablesite/moneyplanner-core/commit/2a85d457f900af25a909f8f9520f2a8c372d4233))
* **plan:** exigir plazo en la deuda nueva de una decisión (o la deuda se evaporaba) ([a3c1151](https://github.com/pablesite/moneyplanner-core/commit/a3c1151352d14ca200ef9a15102cba6be491e39e))

## [0.33.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.32.0...moneyplanner-core-v0.33.0) (2026-07-28)


### Features

* **auth:** validate SaaS sessions before Core access ([#109](https://github.com/pablesite/moneyplanner-core/issues/109)) ([a641fdd](https://github.com/pablesite/moneyplanner-core/commit/a641fdddf20f8d9ab2651ca4081bc7d73b842d0a))

## [0.32.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.31.0...moneyplanner-core-v0.32.0) (2026-07-27)


### Features

* **plan:** distinguir apretón transitorio de déficit estructural ([ac4070e](https://github.com/pablesite/moneyplanner-core/commit/ac4070e1ee9177a8f436fbac4704fa55afec4c36))

## [0.31.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.30.0...moneyplanner-core-v0.31.0) (2026-07-26)


### Features

* **plan:** consolidar contrato de overview y preview ([7f59f03](https://github.com/pablesite/moneyplanner-core/commit/7f59f03decbd425395663f994da1f415f3a551a6))
* **plan:** convertir recomendaciones en acciones trazables ([a1aec0d](https://github.com/pablesite/moneyplanner-core/commit/a1aec0df484e3a011a84a9d118f9ea4a644eb7ba))
* **plan:** el patrimonio a preservar exige capital productivo adicional ([be31b89](https://github.com/pablesite/moneyplanner-core/commit/be31b89d4792d42dc6d4aecd72b2d17a83ab8d6c))
* **plan:** endpoint de capital requerido por necesidad mensual ([b83ea67](https://github.com/pablesite/moneyplanner-core/commit/b83ea6710f12e5e18464860e96001f354e0822e0))
* **plan:** jubilación sostenible más temprana y correcciones del motor ([620262f](https://github.com/pablesite/moneyplanner-core/commit/620262fb983e8c9d2644247e442a9ae67aef3cb9))


### Bug Fixes

* **deps:** actualizar axios y postcss para resolver vulnerabilidades altas (npm audit) ([9eee51e](https://github.com/pablesite/moneyplanner-core/commit/9eee51eca72a8d515ad7360a1750380fc607b58f))
* **plan:** evitar 500 al crear un adulto con nombre ya existente ([40181c9](https://github.com/pablesite/moneyplanner-core/commit/40181c9eb1851cf18bed5b1de8feed47980c0ca1))
* **plan:** fondo de emergencia clásico y calidad de datos real en cimientos ([be699a2](https://github.com/pablesite/moneyplanner-core/commit/be699a2eea1b8d0191ce0780a8a9b15660d42df4))
* **plan:** reutilizar identidades adultas existentes ([a440167](https://github.com/pablesite/moneyplanner-core/commit/a440167a183879b26c6db71d39b952500cd3fad5))

## [0.30.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.29.1...moneyplanner-core-v0.30.0) (2026-07-12)


### Features

* **budget:** support term start month ([a73df42](https://github.com/pablesite/moneyplanner-core/commit/a73df42dc01547bd6bf42cc4bd927e361b61ec88))
* **plan:** add findings recommendations and close impact ([1732fee](https://github.com/pablesite/moneyplanner-core/commit/1732fee5586d3b596bff11426e0f6542dbb7ae32))
* **plan:** add projection engine ([0e5aea4](https://github.com/pablesite/moneyplanner-core/commit/0e5aea47014f4ded403229a5511f1f4963563559))
* **plan:** add scenario lab backend ([2aee7c4](https://github.com/pablesite/moneyplanner-core/commit/2aee7c4146ba37f1459b1c530cd5a670c479e384))
* **plan:** close incorporated events ([a9f843c](https://github.com/pablesite/moneyplanner-core/commit/a9f843c63ccec44faa2e23cdda4132ed09ff6b83))
* **plan:** complete the decision lifecycle and stop double counting forecasts ([10473d8](https://github.com/pablesite/moneyplanner-core/commit/10473d8e934b09ad91ba774e3f0ce4a00596ea20))
* **plan:** derive retirement and itemize one-off costs ([2ed39ba](https://github.com/pablesite/moneyplanner-core/commit/2ed39ba193259e0b90a0ceae620147fbe6fb1c06))
* **plan:** expose product status bands on foundation scores ([0ff2999](https://github.com/pablesite/moneyplanner-core/commit/0ff29994f5c599f467a79f9153c7df99b63c0b0b))
* **plan:** link decisions to the assets and liabilities they brought ([5808767](https://github.com/pablesite/moneyplanner-core/commit/58087671355c540dd2e7be6267b950d2f1fc7c91))
* **plan:** protect managed budget lineage ([39953f7](https://github.com/pablesite/moneyplanner-core/commit/39953f71e540a5e752b0d335d04cce6da8fbc93b))
* **plan:** register decisions already taken and adopt their budget lines ([d096d6a](https://github.com/pablesite/moneyplanner-core/commit/d096d6ab8bf54fed914e869b48edb039edfb8031))


### Bug Fixes

* **deps:** raise Django floor to 5.2.16 to close PYSEC-2026-2090/91/92 ([46c8225](https://github.com/pablesite/moneyplanner-core/commit/46c8225057190d0dac815bc05c329cad7892a0c4))
* **plan:** add missing Spanish accents to user-facing strings ([2c82d6c](https://github.com/pablesite/moneyplanner-core/commit/2c82d6c7d2189ca1ba7d5e2881f4c768fac80e36))
* **plan:** classify assets by effective value, not raw amount ([3b94b1d](https://github.com/pablesite/moneyplanner-core/commit/3b94b1d98434aa29e84930f9e5a12ba405466ad6))
* **plan:** recurring scenario expense without end date is indefinite ([ff22948](https://github.com/pablesite/moneyplanner-core/commit/ff22948d7182f3864e5cf2dc491b74debce9524f))
* **plan:** sanitize projection engine inputs ([3e98067](https://github.com/pablesite/moneyplanner-core/commit/3e980670f217d869fe4144b84403ad0fc5cca064))
* **plan:** scenario budget lines no longer overlap across fiscal years ([1a436b0](https://github.com/pablesite/moneyplanner-core/commit/1a436b05d42ce8f9fa10dbfadf26d38647e957fa))

## [0.29.1](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.29.0...moneyplanner-core-v0.29.1) (2026-07-09)


### Bug Fixes

* **accounting:** compute account balances in bulk on list endpoint ([c5fac0f](https://github.com/pablesite/moneyplanner-core/commit/c5fac0f36ad20dfb56c1287231c8d64cac9228ef))

## [0.29.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.28.0...moneyplanner-core-v0.29.0) (2026-06-28)


### Features

* **core:** endpoint de conversión de divisas con precisión cripto y sync on-demand ([91e373d](https://github.com/pablesite/moneyplanner-core/commit/91e373d018f9549e8282894a7be02b35784326bb))
* **net-worth:** expose timeline comparison baselines ([8692560](https://github.com/pablesite/moneyplanner-core/commit/86925605c85a96b29733592b760fd66b326741fb))

## [0.28.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.27.0...moneyplanner-core-v0.28.0) (2026-06-24)


### Features

* **accounting:** add review queue and account-scoped daily series ([8ad0ef8](https://github.com/pablesite/moneyplanner-core/commit/8ad0ef8049f41b8f463d235fbdfc0b736f5df839))


### Bug Fixes

* **deploy:** avoid market sync migration race ([1cfc6c6](https://github.com/pablesite/moneyplanner-core/commit/1cfc6c6583fd5eb7ce763e38b85f60c4488efadf))
* **frontend:** refresh audited lockfile ([860e5dc](https://github.com/pablesite/moneyplanner-core/commit/860e5dcfb8906d4d7fa384ec8da5dccee1fb62bc))

## [0.27.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.26.0...moneyplanner-core-v0.27.0) (2026-06-14)


### Features

* **brand:** rename core app to the arkenstone ([d7a7d76](https://github.com/pablesite/moneyplanner-core/commit/d7a7d76b5fcb28d9293914fcbff1ae683d6d658a))


### Bug Fixes

* **ci:** avoid release please json template parsing ([ce6141e](https://github.com/pablesite/moneyplanner-core/commit/ce6141ef94f108a47bf3fed480f6d2e1ea4c2265))
* **ci:** parse release please pr output ([484fe88](https://github.com/pablesite/moneyplanner-core/commit/484fe886cb4709042eb8a92e1fb458a29347ea48))
* **ci:** pass repository to release pr commands ([d1e3780](https://github.com/pablesite/moneyplanner-core/commit/d1e378056611a04e4c13862f58f2ee4d69d58e31))

## [0.26.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.25.0...moneyplanner-core-v0.26.0) (2026-06-12)


### Features

* **auth:** expose core users for saas admin bridge ([#62](https://github.com/pablesite/moneyplanner-core/issues/62)) ([24127c8](https://github.com/pablesite/moneyplanner-core/commit/24127c8aecff3d5706e2a9e2f9ce6dc549bced6b))

## [0.25.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.24.1...moneyplanner-core-v0.25.0) (2026-06-04)


### Features

* **deploy:** harden core production settings ([#58](https://github.com/pablesite/moneyplanner-core/issues/58)) ([22a3ef1](https://github.com/pablesite/moneyplanner-core/commit/22a3ef1abf6d5b5afd953539e81cd8ec6962b62f))


### Bug Fixes

* **deploy:** patch core frontend image packages ([#59](https://github.com/pablesite/moneyplanner-core/issues/59)) ([a801733](https://github.com/pablesite/moneyplanner-core/commit/a801733410b9533ab31c1a452781351ccd77820a))

## [0.24.1](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.24.0...moneyplanner-core-v0.24.1) (2026-05-27)


### Bug Fixes

* **release:** add last-release-sha to stop commit backfilling ([#44](https://github.com/pablesite/moneyplanner-core/issues/44)) ([ea2015b](https://github.com/pablesite/moneyplanner-core/commit/ea2015b1f300495aa60220bac6dd8a657d590391))

## [0.24.0](https://github.com/pablesite/moneyplanner-core/compare/moneyplanner-core-v0.23.0...moneyplanner-core-v0.24.0) (2026-05-27)


### ⚠ BREAKING CHANGES

* remove NetWorthSnapshot — legacy feature, fully replaced by dynamic timeline

### Features

* **accounting:** account mapping UI in MoneyWiz import preview ([86150bf](https://github.com/pablesite/moneyplanner-core/commit/86150bfe2b409c55d39503725213892d84e0bed5))
* **accounting:** activate manual net worth positions from movements ([70ce782](https://github.com/pablesite/moneyplanner-core/commit/70ce782cecba9f5d993494f3842d94569d5f24fd))
* **accounting:** add bulk cleanup for imported movements ([e1ac1aa](https://github.com/pablesite/moneyplanner-core/commit/e1ac1aa444dd5647a47b8089a6b8c8ce271b9555))
* **accounting:** add compact transaction list mode ([6962a4f](https://github.com/pablesite/moneyplanner-core/commit/6962a4f7886df5a3cb18b0c171402d6c35416383))
* **accounting:** add daily balance timeline with fx-aware consolidation ([afc2fba](https://github.com/pablesite/moneyplanner-core/commit/afc2fbab3bb60f08f3aa1b0dd0c600f0796feba2))
* **accounting:** add duplicate movement button to movements lists ([0f1e5a3](https://github.com/pablesite/moneyplanner-core/commit/0f1e5a32274888627afee6d84b9927962a9b0fe5))
* **accounting:** add floating filters in cuentas tab ([b33e3a9](https://github.com/pablesite/moneyplanner-core/commit/b33e3a963c522e20e661c445df88529120a8d58d))
* **accounting:** add flow/category metadata to ledger entry payload ([65c0c78](https://github.com/pablesite/moneyplanner-core/commit/65c0c78bee8d6947cfd3f7222ef477f32199d007))
* **accounting:** add functional classification fields to ledger entries ([b572ec3](https://github.com/pablesite/moneyplanner-core/commit/b572ec302a405251fb21f62b8c603627261d48c4))
* **accounting:** add MoneyWiz CSV importer ([997abf2](https://github.com/pablesite/moneyplanner-core/commit/997abf2f9970f8a9d9fbe803003c57054a3d4abe))
* **accounting:** add MoneyWiz import flow ([e7cecb1](https://github.com/pablesite/moneyplanner-core/commit/e7cecb103568284c63453d437b3ac3b7d414e130))
* **accounting:** add opening balance movement type ([bffdba3](https://github.com/pablesite/moneyplanner-core/commit/bffdba33546a397702bc1860fdeba01857144265))
* **accounting:** add ownership field to LedgerTransaction ([acd74f4](https://github.com/pablesite/moneyplanner-core/commit/acd74f42c566a9304d2e3f64c3f7ba89e126eee0))
* **accounting:** add reconciliation adjustment movement ([3d0b95a](https://github.com/pablesite/moneyplanner-core/commit/3d0b95ad909d904136e0a4352e30c232e5f2e4bb))
* **accounting:** add refund and personal-loan repayment taxonomy updates ([acdd626](https://github.com/pablesite/moneyplanner-core/commit/acdd626fb69a47a65cec9fa5eac2457733d0798c))
* **accounting:** add reinvestment flow for investment transfers ([10b0428](https://github.com/pablesite/moneyplanner-core/commit/10b04283eaaf3bfbdef2ed95f747582577324360))
* **accounting:** add value-date toggle styles in quick entry ([ec0a864](https://github.com/pablesite/moneyplanner-core/commit/ec0a864f085850c6d92206c66153e1f0e4ed343c))
* **accounting:** advance quick-entry and monthly close fallback ([fa863e2](https://github.com/pablesite/moneyplanner-core/commit/fa863e2e49b4def77c26435c6e534a10f2053c8e))
* **accounting:** align movements hero with net worth layout ([b84a44f](https://github.com/pablesite/moneyplanner-core/commit/b84a44f0dec1a0624a682ec03029dcad06de0dc2))
* **accounting:** allow archiving user ledger accounts ([ff41950](https://github.com/pablesite/moneyplanner-core/commit/ff41950b24ab9cd0dd9629338b24926508f2d3ef))
* **accounting:** allow non-consumption categories for non-mortgage debt payments ([a54c12e](https://github.com/pablesite/moneyplanner-core/commit/a54c12e2cf43291a2488bc258dfedb11d823661a))
* **accounting:** allow removing linked accounts from accounting tracking ([ae1ec92](https://github.com/pablesite/moneyplanner-core/commit/ae1ec92930ba671d6bd4c1feeda041506b535774))
* **accounting:** allow skipping transaction totals ([f1c046a](https://github.com/pablesite/moneyplanner-core/commit/f1c046a3c42043a8cd1b235afb65a1e922573db0))
* **accounting:** backfill legacy ledger classification ([347edab](https://github.com/pablesite/moneyplanner-core/commit/347edabb22d2ad1a57ce2fb3abba0da72db41844))
* **accounting:** close phase 2 liquidity workspace ([fb9ba59](https://github.com/pablesite/moneyplanner-core/commit/fb9ba5917e0fcf49247a52bba1067112d184dc2a))
* **accounting:** close phase 3 backend monthly close integration ([fc15fde](https://github.com/pablesite/moneyplanner-core/commit/fc15fde810f4f0bfe770d3e1e437fff39f3bc426))
* **accounting:** completar fase 4 con compras de inversion y pagos de deuda ([ade6596](https://github.com/pablesite/moneyplanner-core/commit/ade659694110c0d5271eb7aefa5e751bd0e34d18))
* **accounting:** converge accounting movements view to unified design ([468eb2b](https://github.com/pablesite/moneyplanner-core/commit/468eb2b535e4a9805f0d7f6a478f53b9446933b2))
* **accounting:** dedupe moneywiz transfer mirrors and polish mapping ui ([0db31ab](https://github.com/pablesite/moneyplanner-core/commit/0db31ab3c53017b56927b9e63bce7e304903f6df))
* **accounting:** hard-delete user accounts with impact warning ([01ee62c](https://github.com/pablesite/moneyplanner-core/commit/01ee62cf9d2b847d23b0f20bc446d1a6d22147de))
* **accounting:** implement phase 2 category-first quick entry ([6e1f104](https://github.com/pablesite/moneyplanner-core/commit/6e1f1048d46975d212958afb44f3699f5bee5fa7))
* **accounting:** implement phase 5 budget-derived suggestions ([7542747](https://github.com/pablesite/moneyplanner-core/commit/7542747033b5331aad6bfc5e5777e32e71592f5e))
* **accounting:** improve crypto sync and net-worth integration ([25eda4c](https://github.com/pablesite/moneyplanner-core/commit/25eda4c3e4d01fb6d1f12806ba76e9da3b8b8269))
* **accounting:** improve debt payment breakdown handling in forms ([6ffe395](https://github.com/pablesite/moneyplanner-core/commit/6ffe395db7ca9be59d9fe25513a99ff600573efb))
* **accounting:** improve multi-currency investment flows and btc cleanup tooling ([5d212ad](https://github.com/pablesite/moneyplanner-core/commit/5d212ad3d2b159c0a578b46a0e7c11458f7c4d62))
* **accounting:** mapeo de categorías MoneyWiz en español + preview de no mapeadas ([be3cee2](https://github.com/pablesite/moneyplanner-core/commit/be3cee2f14bafb2e00a0a9c610eb5e8887709df6))
* **accounting:** member_tag, investment mirrors and MoneyWiz import improvements ([e8a4bf3](https://github.com/pablesite/moneyplanner-core/commit/e8a4bf3fd41cdad875175a35838298a723871d2d))
* **accounting:** paginate transactions list server-side ([3f8e7ac](https://github.com/pablesite/moneyplanner-core/commit/3f8e7acd06e6185b97547caedd3ef9c3232221c7))
* **accounting:** redesign AccountingMovementsView UX + fix background errors ([e4c6768](https://github.com/pablesite/moneyplanner-core/commit/e4c6768a0a04e35d765c49e941201f702e8c5f42))
* **accounting:** redesign debt-payment modal UX for edit and quick-entry ([0e244fd](https://github.com/pablesite/moneyplanner-core/commit/0e244fdcd706886630fd58097ef03cfed22737af))
* **accounting:** redesign investment flow in quick entry modal ([9755deb](https://github.com/pablesite/moneyplanner-core/commit/9755deb95ac2e0c34caee23a2fd9bdb574f51105))
* **accounting:** redesign transaction filter bar with category, subcategory, and date presets ([72391b7](https://github.com/pablesite/moneyplanner-core/commit/72391b7cfa584926b92a904938302384eecbbb53))
* **accounting:** refine movements tab bar UI ([4def88d](https://github.com/pablesite/moneyplanner-core/commit/4def88d8ffc4d6c416f4216b58637ad6beab856a))
* **accounting:** remove MoneyWiz import, relocate actions, replace ledger text ([81f546c](https://github.com/pablesite/moneyplanner-core/commit/81f546c01eb309b62abfdd99c0cfaca7a924cdde))
* **accounting:** retire legacy account semantics from core ux ([23a74fc](https://github.com/pablesite/moneyplanner-core/commit/23a74fc2cbce1eeb87d4d27ff718ad03befeee6f))
* **accounting:** show category subtotal in accounts catalog header ([322e57a](https://github.com/pablesite/moneyplanner-core/commit/322e57a0657efa5731a10c1354d32b73a2ce3790))
* **accounting:** show post-transaction balance and close Spot Binance review ([bc02a45](https://github.com/pablesite/moneyplanner-core/commit/bc02a45189ad99dc54913717d1eb9f746fc72292))
* **accounting:** simplify movement edit UX and icon actions ([b47736f](https://github.com/pablesite/moneyplanner-core/commit/b47736facfd0b82b99447ccd8d27ab9ee03f7c18))
* **accounting:** support bidirectional investment flow and outflow import dedupe ([fd3e318](https://github.com/pablesite/moneyplanner-core/commit/fd3e31813addd81a14e2a8d7b5051afafb2f5cd2))
* **accounting:** unify tab/content card, collapse groups by default, add asset/liability color coding ([04759ab](https://github.com/pablesite/moneyplanner-core/commit/04759abf52f727191e827482107c2af7df840dab))
* add ownership filter to net worth view ([153bf1a](https://github.com/pablesite/moneyplanner-core/commit/153bf1a7bb9c1fe9638c5ebcdd1b1c66fd090163))
* **auth:** add logout endpoint and cross-user isolation test suite ([ca0f41f](https://github.com/pablesite/moneyplanner-core/commit/ca0f41f05a4e8b3a796b26543538d96c49fff4c7))
* **auth:** add user registration from UI ([4199c6a](https://github.com/pablesite/moneyplanner-core/commit/4199c6af48c6eda79dac802743fdec2e8216a718))
* **auth:** wire frontend logout to backend blacklist endpoint ([6f43b40](https://github.com/pablesite/moneyplanner-core/commit/6f43b40a75f84469d96f385d7c7a67c2cf0f7279))
* budget taxonomy normalization, deposit routing, and tangible asset expenses ([2b17cfd](https://github.com/pablesite/moneyplanner-core/commit/2b17cfde82f36c2db4a5eb0d51548c474831580d))
* **budget:** accordion categories and improved visual hierarchy ([cc4f766](https://github.com/pablesite/moneyplanner-core/commit/cc4f7669512fe1a1a84035b2f624b0b49ae96ffe))
* **budget:** activate expense evolution bars using monthly close checkins ([5011d62](https://github.com/pablesite/moneyplanner-core/commit/5011d62afa5d8657936a698e1a8bc8ce83408322))
* **budget:** activate expense YTD execution bars for category/subcategory ([f6e9cb6](https://github.com/pablesite/moneyplanner-core/commit/f6e9cb6ca427bc600d679d54cf645be99f8556cf))
* **budget:** add month selector to YTD detail bars ([b2b4f2a](https://github.com/pablesite/moneyplanner-core/commit/b2b4f2ac0ba5588020aa7d31c47c1928ba46a267))
* **budget:** align hero section design with net-worth hero ([eaadf6d](https://github.com/pablesite/moneyplanner-core/commit/eaadf6d72237f1f0e79d2b693605a0f6fe81eb0e))
* **budget:** consume categorized ledger execution ([d96b382](https://github.com/pablesite/moneyplanner-core/commit/d96b382a40384b24fbb4253fe1a45f7b7e5a2098))
* **budget:** enhance monthly close result section layout and styles ([8f6ba99](https://github.com/pablesite/moneyplanner-core/commit/8f6ba99920f2c2d648f3b52862d45af26b45ea39))
* **budget:** expose unbudgeted execution coverage and stabilize test migrations ([bf73336](https://github.com/pablesite/moneyplanner-core/commit/bf733364f23c29fb9f2fd1aaf97450517cd64142))
* **budget:** group monthly liquidity close rows ([a1662fa](https://github.com/pablesite/moneyplanner-core/commit/a1662fa984c35efb1e3cbb847924c88f7813a95a))
* **budget:** improve annual income planning and execution consistency ([22a5161](https://github.com/pablesite/moneyplanner-core/commit/22a51610337369d74b4b0a16a7a84e37ebd9142b))
* **budget:** improve monthly close income adjustments ([390f485](https://github.com/pablesite/moneyplanner-core/commit/390f485fcea385ca18fffd16a7f39865bb65b17d))
* **budget:** migrate annual entry management into budget view ([4925e92](https://github.com/pablesite/moneyplanner-core/commit/4925e92858fdd24cb177a71d2ad57179388e186a))
* **budget:** monthly close dual-mode backend ([e359b8f](https://github.com/pablesite/moneyplanner-core/commit/e359b8f04fc365e9a4f8c0310a5dd1b09e431424))
* **budget:** monthly close sections redesign and dashboard enhancements ([e8cbaad](https://github.com/pablesite/moneyplanner-core/commit/e8cbaad7d93793605640f3752c95804a654406a4))
* **budget:** move type filter to global hero header ([a87ba7f](https://github.com/pablesite/moneyplanner-core/commit/a87ba7f8653db758119dbf2fd332dac2692bd59f))
* **budget:** redesign annual section bars and category cards ([34acb5d](https://github.com/pablesite/moneyplanner-core/commit/34acb5d7864074f97a519b6de80a116b6a620273))
* **budget:** redesign annual section layout and execution coloring ([a377947](https://github.com/pablesite/moneyplanner-core/commit/a37794778e1c14c5ab1e16b94e17d6b9cacd0cfe))
* **budget:** redesign subcategory detail panel and row actions ([76ed05d](https://github.com/pablesite/moneyplanner-core/commit/76ed05d6af34442709c5bab59c74a799c58dbcc9))
* **budget:** rediseña hero y simplifica sugerencias ([a2777b1](https://github.com/pablesite/moneyplanner-core/commit/a2777b1e3c8c92142064426f9e99b0c8e9766761))
* **budget:** restyle evolution chart bars to match progress bar visual language ([8f91ea3](https://github.com/pablesite/moneyplanner-core/commit/8f91ea3345066db46fb73806e14a47c60c307065))
* **budget:** simplify annual entries and fix generated commitments by year ([cb07341](https://github.com/pablesite/moneyplanner-core/commit/cb07341e32aa4a9327825d7a6570e6307798af65))
* **budget:** simplify monthly close result view ([eca882c](https://github.com/pablesite/moneyplanner-core/commit/eca882c791d71835c61e2e1a63192a358018b198))
* **budget:** sticky month selector and compact category/subcategory view ([a616575](https://github.com/pablesite/moneyplanner-core/commit/a61657552ec9845a6eafe1aaf50acd14efc0bfbd))
* **core-accounting:** add account balance summaries ([395092d](https://github.com/pablesite/moneyplanner-core/commit/395092ddd724503a5220b3fede932e666bfa7724))
* **core-accounting:** add quick ledger entry flows for liquidity ([acdd8bf](https://github.com/pablesite/moneyplanner-core/commit/acdd8bf24df28f96693afaa519dd9f4215be0cc2))
* **core-accounting:** derive net worth accounting balances from ledger ([8f15e06](https://github.com/pablesite/moneyplanner-core/commit/8f15e061db93bf368fd732c4f47cf95f8f505c0f))
* **core-backend:** add accounting ledger foundation ([6f24a11](https://github.com/pablesite/moneyplanner-core/commit/6f24a11e9a380aac1011a4105a11f44e1b42b1d2))
* **core:** add manual market-data sync and inflation-region handling ([39be0da](https://github.com/pablesite/moneyplanner-core/commit/39be0da8a81e43143debf718b4606cfd5af9fb52))
* **core:** expose income budget coverage split and unbudgeted visibility ([491a0fd](https://github.com/pablesite/moneyplanner-core/commit/491a0fd6769631807b928a4056be593b8862d388))
* **core:** replace portable data export/import with pg_dump backup/restore ([14bcc39](https://github.com/pablesite/moneyplanner-core/commit/14bcc39ff5066d22201aad011751950dfbf63030))
* **data-input:** relocate portable and liability-review flows ([4195344](https://github.com/pablesite/moneyplanner-core/commit/4195344c17f98a2179351d4e777d73d6c05de86f))
* **data-input:** unify global ownership and visibility filters ([057b33e](https://github.com/pablesite/moneyplanner-core/commit/057b33ee1f9c11efe43d61190305c89755242642))
* define core accounting movements roadmap ([72442fd](https://github.com/pablesite/moneyplanner-core/commit/72442fd1cb48d07008b777154f7b74720b5cefff))
* **duplicate:** default booking and value date to today when duplicating ([ee48645](https://github.com/pablesite/moneyplanner-core/commit/ee48645cbd885ae38ab58c47e4f216a735353671))
* **frontend:** add accounting movements workspace ([1f79144](https://github.com/pablesite/moneyplanner-core/commit/1f79144282bce052bb80462bde6e3dae7457adcd))
* **frontend:** add design system foundation ([a8b4606](https://github.com/pablesite/moneyplanner-core/commit/a8b4606087d5175e03f530783c5edf7081aa5189))
* **frontend:** add manual liquidity override flow ([b7a0b21](https://github.com/pablesite/moneyplanner-core/commit/b7a0b21f5d04f2e0212dd632c6a715a6dac2f58e))
* **frontend:** add shared visual contract primitives ([e046563](https://github.com/pablesite/moneyplanner-core/commit/e046563dca60150a39641d16e1bf1f4143958a51))
* **frontend:** align edit movement modal structure with create modal ([54fd074](https://github.com/pablesite/moneyplanner-core/commit/54fd074404445bf772cab8dbacd47c70b0d625d9))
* **frontend:** fix settings view formatting and add infinite scroll for market data tables ([5046ea3](https://github.com/pablesite/moneyplanner-core/commit/5046ea37ec9c2f7b24cc8afb66844a9eda23b668))
* **frontend:** integrar presupuesto por categorias y retirar modulo data-input ([2112afe](https://github.com/pablesite/moneyplanner-core/commit/2112afe8ae79f1b816b342eb7d51782b78f7fc20))
* **frontend:** integrate monthly-close dual-mode API — lifecycle, distribution, lock ([f6cb70e](https://github.com/pablesite/moneyplanner-core/commit/f6cb70e0ec499a1cdd83245fa6b05b5eec84129a))
* **frontend:** move accounting quick entry into modal ([a5ca7c8](https://github.com/pablesite/moneyplanner-core/commit/a5ca7c8a07c218f35f7952e01c39ccb9a5edcaa7))
* **frontend:** refine monthly-close coverage messaging ([5404e62](https://github.com/pablesite/moneyplanner-core/commit/5404e62db07d03c04ff7604c9c1ad85faa1a7c3e))
* **frontend:** refine net worth timeline workspace ([ec5d3e9](https://github.com/pablesite/moneyplanner-core/commit/ec5d3e9631ca39c93107bd97697d539e82584411))
* **frontend:** streamline net worth analysis workspace ([3ffff65](https://github.com/pablesite/moneyplanner-core/commit/3ffff6566f72fb720773cb82b00bbf650a3d1528))
* improve investment contribution currency and form layout ([cefb1bf](https://github.com/pablesite/moneyplanner-core/commit/cefb1bf97eb0725665f14e9878fd3256c608c7c5))
* **liquidity:** include liquid liabilities and perimeter-internal expenses in summary ([e5e4ca2](https://github.com/pablesite/moneyplanner-core/commit/e5e4ca23eb54fd38867f672997b3c97a7d998f17))
* make net worth composition operational ([1d6a4e2](https://github.com/pablesite/moneyplanner-core/commit/1d6a4e2650058dea932be6c63f80a44bb28e52c3))
* make portable data imports atomic ([f3f7126](https://github.com/pablesite/moneyplanner-core/commit/f3f7126daa36052e842cca272c71a6a4bcca1e7e))
* manual market-data sync + inflation-region-aware net worth ([3e75bdb](https://github.com/pablesite/moneyplanner-core/commit/3e75bdbdc20d896ec996afd685e383c1778f4d4b))
* manual market-data sync, inflation region, CI hardening and code quality fixes ([b67e50a](https://github.com/pablesite/moneyplanner-core/commit/b67e50ab66591129ebd39efa2032d60764c18c75))
* manual market-data sync, inflation region, CI pipeline and production Dockerfiles ([bfef0eb](https://github.com/pablesite/moneyplanner-core/commit/bfef0ebbeaa108721e7d0e9ed03864cfc900a3ba))
* **market-data:** add scheduled sync and net worth integration ([6d6d5af](https://github.com/pablesite/moneyplanner-core/commit/6d6d5affebfa122f8db3e6063ee7080f77417338))
* **net-worth:** add 5y default preset, current-month gray point, and MoM delta in timeline ([368d3e1](https://github.com/pablesite/moneyplanner-core/commit/368d3e1cea5ece85b48fab4d9882ef11b19228a3))
* **net-worth:** add auto home valuation model and profile presets ([a650060](https://github.com/pablesite/moneyplanner-core/commit/a650060d5cc15654fb548b832d3440358ca7c7ae))
* **net-worth:** add home improvements valuation and improve reform UX ([d3542bb](https://github.com/pablesite/moneyplanner-core/commit/d3542bbfaf85e637f83fa3682f8c0aa42ba4b8c4))
* **net-worth:** add mortgage cancellation forecast flow ([6519149](https://github.com/pablesite/moneyplanner-core/commit/6519149a87716adb9b9c7a6acac8791b28f5ba65))
* **net-worth:** add temporal history and automate fx sync ([0394e7e](https://github.com/pablesite/moneyplanner-core/commit/0394e7e127a10c41569af0f078fc83d97302b27a))
* **net-worth:** archive/unarchive assets with accounting cascade ([adf2e28](https://github.com/pablesite/moneyplanner-core/commit/adf2e282b61e7432d42c3f3b14bdd9bf62a6fa02))
* **net-worth:** bar chart de variación mensual debajo del timeline ([fbf48ca](https://github.com/pablesite/moneyplanner-core/commit/fbf48caeb8be575494bdb49c1d6ccf84ffd4b148))
* **net-worth:** close accounting movements 4b integration ([73d09aa](https://github.com/pablesite/moneyplanner-core/commit/73d09aa5bba5e64693572a323691c5b8b0b81e5d))
* **net-worth:** compare monthly delta against same day previous month ([1e6fe1a](https://github.com/pablesite/moneyplanner-core/commit/1e6fe1a329596eed9a2e53c54812181538811839))
* **net-worth:** expose tracking mode in item form ([4a965b1](https://github.com/pablesite/moneyplanner-core/commit/4a965b12702f3d1393838bcb0f1a0a4adbd237fb))
* **net-worth:** hero summary reorganizado — título en cabecera + bottom row unificado ([6dad235](https://github.com/pablesite/moneyplanner-core/commit/6dad235c29ba55bcafd8675e1a2d3e5ec4696e1c))
* **net-worth:** improve timeline chart interactions ([2fe3269](https://github.com/pablesite/moneyplanner-core/commit/2fe32693e402f17c4b0affa3124cfcb23544fcfc))
* **net-worth:** indicador de variación mensual en el hero ([21a450d](https://github.com/pablesite/moneyplanner-core/commit/21a450d99414e48da8636ea2a2efa755489d9329))
* **net-worth:** interval-based investment contribution form ([483ad0d](https://github.com/pablesite/moneyplanner-core/commit/483ad0d8dd0cf61e370a1daa3e08dad5d23b5a74))
* **net-worth:** mejorar UX del hero y loading del timeline ([73a4771](https://github.com/pablesite/moneyplanner-core/commit/73a4771349ae0e8f44528c62bec5d0267d6e4d1c))
* **net-worth:** multi-interval investment contribution schedule ([698993c](https://github.com/pablesite/moneyplanner-core/commit/698993c03a6de3d930edb3e264bfba2d03c2a589))
* **net-worth:** optimize timeline and summary loading paths ([dc4bdd5](https://github.com/pablesite/moneyplanner-core/commit/dc4bdd54347f790588c93e87a8a0e49c2cc36b70))
* **net-worth:** persist average balance for remunerated liquidity ([bad0b87](https://github.com/pablesite/moneyplanner-core/commit/bad0b87e414f9f65274cecf33da2332b7afe6006))
* **net-worth:** reemplazar donut con vista por categorias + rediseno hero ([fa1bbc9](https://github.com/pablesite/moneyplanner-core/commit/fa1bbc95e93fa5037ec2f73a0204e6fb29e2577b))
* **net-worth:** refine furnishings amortization profiles and form UX ([1f3afcb](https://github.com/pablesite/moneyplanner-core/commit/1f3afcbb2626c1d5d7b238e66dded4cf7bee2e51))
* **net-worth:** support indefinite and weekly ETF contributions with correct generated expense mapping ([9712d25](https://github.com/pablesite/moneyplanner-core/commit/9712d25f4e05a01943c48eeab8f5fdae8e2ba531))
* **net-worth:** support loan grace period and stabilize timeline layout ([71730ce](https://github.com/pablesite/moneyplanner-core/commit/71730ce150689d841993fc7c6a3ebeff466925c3))
* **net-worth:** support periodic investment contributions and generated commitments ([cb2d23c](https://github.com/pablesite/moneyplanner-core/commit/cb2d23cdf5c488deac63b0af77b7ff5832681f91))
* **net-worth:** support short-term deposit term and taxed interest income ([f6738ea](https://github.com/pablesite/moneyplanner-core/commit/f6738eaf2cb3348d5d910d6ab77a8b42480df051))
* **oss:** prepare core for open-source community release ([6162c03](https://github.com/pablesite/moneyplanner-core/commit/6162c03e61af60366ab65383580505e085534225))
* **portable-data:** include accounting accounts and movements in transfer bundle ([6e8739b](https://github.com/pablesite/moneyplanner-core/commit/6e8739b8af2054d919cdd10e0945795028fb6d69))
* refine budget and guide workflows ([402aced](https://github.com/pablesite/moneyplanner-core/commit/402aceddf76339371c7c39667518dc5de264d0f1))
* remove NetWorthSnapshot — legacy feature, fully replaced by dynamic timeline ([c20c7ec](https://github.com/pablesite/moneyplanner-core/commit/c20c7ec145b70cc76b8b5970ccfedc44f0b75ffc))
* **seed:** add seed_demo command + fix seed overwrite loop ([3a13f48](https://github.com/pablesite/moneyplanner-core/commit/3a13f486817fd4fbf18eec18a56740fd239217f7))
* **shell:** presupuesto como vista de inicio; guía en /guia; eliminar fase 5 ([e5899d3](https://github.com/pablesite/moneyplanner-core/commit/e5899d3242d86aa34e8e682617c7eb66509ae6a4))
* **styles:** add shared ui-kpi-strip, ui-type-badge and ui-cashflow-strip patterns ([ad8a677](https://github.com/pablesite/moneyplanner-core/commit/ad8a67701cfe4a60a2fe15904160a0bc7610062e))
* **taxonomy:** add sports equipment subcategory and update ING review status ([bbe4c20](https://github.com/pablesite/moneyplanner-core/commit/bbe4c209ceb3ab7fbc32d71981eebd5870c0f62c))


### Bug Fixes

* **accounting:** add labels to description and ownership fields ([0d19f61](https://github.com/pablesite/moneyplanner-core/commit/0d19f6179ea1b5be266b1b3c13567d5022f03de8))
* **accounting:** aggregate account balance summaries ([ed27234](https://github.com/pablesite/moneyplanner-core/commit/ed272349e15a231483feb5bbce12d0436ec6e68e))
* **accounting:** aggregate daily balance summaries ([e69d957](https://github.com/pablesite/moneyplanner-core/commit/e69d957adf9e2a1dd18907bfcfd5708c351a83dd))
* **accounting:** ajustar mapeos de categorías en importer MoneyWiz ([5f61c74](https://github.com/pablesite/moneyplanner-core/commit/5f61c74653a4cf3bc1550711fb5c3777416e0e54))
* **accounting:** align edit modal UX and fix multicurrency investment edits ([db4f7dc](https://github.com/pablesite/moneyplanner-core/commit/db4f7dcbf46fdba76a3ed215151108edfaa32a42))
* **accounting:** align investment grid columns and label category selects ([0572d59](https://github.com/pablesite/moneyplanner-core/commit/0572d5983f89616020d1cfd2f3b415658b0a28dc))
* **accounting:** allow income quick entry on investment assets ([bba2c7f](https://github.com/pablesite/moneyplanner-core/commit/bba2c7f8fb2dfce0169a2b92dc98026d8c60b2e5))
* **accounting:** allow liability cards in quick entry and transfers ([8e5c74e](https://github.com/pablesite/moneyplanner-core/commit/8e5c74e01c7a1cb6b3dd38cdb68f850760f40ed8))
* **accounting:** añadir counterparts de income para Inversiones Gastos en importer MoneyWiz ([f772a6a](https://github.com/pablesite/moneyplanner-core/commit/f772a6adacad58892b70d49ee80b53725478ef34))
* **accounting:** apply filters sequentially after navigation from budget ([b5cfc86](https://github.com/pablesite/moneyplanner-core/commit/b5cfc8630e30fe27de711cde6b224ecd3d1de860))
* **accounting:** apply ownership by ledger account with shared splits ([8d5e1af](https://github.com/pablesite/moneyplanner-core/commit/8d5e1afacc323b6961cd50ab593d86e2a8667441))
* **accounting:** clasificar compras de activos financieros como investment_purchase en importer MoneyWiz ([276a6cd](https://github.com/pablesite/moneyplanner-core/commit/276a6cd10e4a40e60b37a25e7c0e27a78eb63c60))
* **accounting:** clasificar Liquidación Crédito como debt_payment en importer MoneyWiz ([518b681](https://github.com/pablesite/moneyplanner-core/commit/518b6815dbba81bf548bd8899416a0f5d6006eb5))
* **accounting:** clasificar todas las Inversiones Gastos como investment_purchase en importer MoneyWiz ([bec9e7f](https://github.com/pablesite/moneyplanner-core/commit/bec9e7f3882b17d2fe2bf4708b1b2b110f654665))
* **accounting:** copy pass — accents, plain language, remove redundant header ([c427679](https://github.com/pablesite/moneyplanner-core/commit/c427679868cfe54236b52e8f159a08aa009544d5))
* **accounting:** correct revaluation amount tone for positive entries ([0b77cfe](https://github.com/pablesite/moneyplanner-core/commit/0b77cfea20ea5022edf79ab828e4efe1e5cc61ca))
* **accounting:** corregir importador MoneyWiz v1 con CSV en español ([ee56884](https://github.com/pablesite/moneyplanner-core/commit/ee568847307850cb7e4b70a38f58cdd5bafcfaae))
* **accounting:** corregir mapeo Inversiones Gastos en importer MoneyWiz ([a2ba771](https://github.com/pablesite/moneyplanner-core/commit/a2ba7719657922a87d3043d7bd062089aa9bc100))
* **accounting:** count only operational active accounts ([89c1995](https://github.com/pablesite/moneyplanner-core/commit/89c19953f4ae460e070ed0a356937cdc85c10c7a))
* **accounting:** differentiate tab bar buttons and fix symbol centering ([9d4a1de](https://github.com/pablesite/moneyplanner-core/commit/9d4a1dec22b124fce67d53c700c572b42a37b4ec))
* **accounting:** enforce ledger user boundary and update movements tracker ([4c78f21](https://github.com/pablesite/moneyplanner-core/commit/4c78f21c0b0a9b3042dfc72372e6f76e0faf7931))
* **accounting:** fix revaluation flow and activity_kind classification ([9b46695](https://github.com/pablesite/moneyplanner-core/commit/9b4669510c12bd2cf70bc56c71e7dc030d4aa3c2))
* **accounting:** Ganancias de Capital &gt; Ventas Activos → capital_gains/sale_personal_asset ([db87529](https://github.com/pablesite/moneyplanner-core/commit/db87529d6a8f1158048f7964629c25f306f8d30f))
* **accounting:** harden movement type classification and filters ([e383723](https://github.com/pablesite/moneyplanner-core/commit/e383723ba2b29bbe41eb2ff4774c052577aed9ca))
* **accounting:** improve investment edit flow and close ING review batch ([09f59cd](https://github.com/pablesite/moneyplanner-core/commit/09f59cdce10b5f30d9a1aeb2e2fae75918865fc8))
* **accounting:** improve movement filters and timeline/account UX ([65ecab1](https://github.com/pablesite/moneyplanner-core/commit/65ecab16cc65aedb3ce6225c86770ba8169dd54f))
* **accounting:** Inversiones Ingresos siempre income independientemente del signo en importer MoneyWiz ([1f66c6d](https://github.com/pablesite/moneyplanner-core/commit/1f66c6db28632a8e9c9d453fe682aee7931284e2))
* **accounting:** minor backend improvements — member tag migration, moneywiz, serializers ([5e285fd](https://github.com/pablesite/moneyplanner-core/commit/5e285fdecdb6f81f5ecc740687869b21e6c39a78))
* **accounting:** move validation hint above submit, hide empty plan link ([b666f4a](https://github.com/pablesite/moneyplanner-core/commit/b666f4a9c88310408d7717a9df22211ed17e5796))
* **accounting:** optimize transaction search filters ([0ae9ee9](https://github.com/pablesite/moneyplanner-core/commit/0ae9ee926058b559dc365bbebce65e7cf2c4895e))
* **accounting:** permitir seleccionar pasivos al editar gastos ([8623860](https://github.com/pablesite/moneyplanner-core/commit/8623860112cd95e89389e976bb664972b8eaabd1))
* **accounting:** persist investment edit classification and close bitcoin review ([6261d70](https://github.com/pablesite/moneyplanner-core/commit/6261d7012391e420be91b6875ce413c33803a5f7))
* **accounting:** prevent deleted linked accounts from auto-recreating ([efef3a7](https://github.com/pablesite/moneyplanner-core/commit/efef3a715d61c371eb1db270060cba390f9041e3))
* **accounting:** remove imported cleanup endpoint ([6e173c3](https://github.com/pablesite/moneyplanner-core/commit/6e173c392527b3084a56642f58ad36426b44647d))
* **accounting:** remove legacy budget ledger links ([9d02266](https://github.com/pablesite/moneyplanner-core/commit/9d02266d4e0cde15ae26cb82d64b607ba69bb2e6))
* **accounting:** remove retired MoneyWiz import flow ([756f6b0](https://github.com/pablesite/moneyplanner-core/commit/756f6b0a8f52fe63e62e235f5745359c8050140c))
* **accounting:** replace wrapping filter bar with compact grid layout ([0eb6aad](https://github.com/pablesite/moneyplanner-core/commit/0eb6aadd94795fc59176a0eed122ac1fc3620f70))
* **accounting:** scope related serializer querysets ([a5abfeb](https://github.com/pablesite/moneyplanner-core/commit/a5abfebb583989b981d6c79f2d2c7a5bee3b9856))
* **accounting:** show 8 decimals for ETH/BTC in movements list ([ed78720](https://github.com/pablesite/moneyplanner-core/commit/ed787202df2749c992f74fc212db66863dcf19f0))
* **accounting:** show investment_purchase as neutral (not red/green) ([267baa2](https://github.com/pablesite/moneyplanner-core/commit/267baa25c56d762d27328a372168fd593463f013))
* **accounting:** show revaluation amount tone correctly when no linked entry ([3b5ff39](https://github.com/pablesite/moneyplanner-core/commit/3b5ff392c1e1a79a049659bb68b895d09f83b0c0))
* **accounting:** speed up account transaction balances ([f4fec68](https://github.com/pablesite/moneyplanner-core/commit/f4fec68090bd55d5a45d46381c9d6b99ff90402c))
* **accounting:** speed up transfer kind filtering ([9d27e3d](https://github.com/pablesite/moneyplanner-core/commit/9d27e3d9c20c63e544ff942ba7fe12d0e4faf9d7))
* **accounting:** split type selector into common and advanced groups ([61ed892](https://github.com/pablesite/moneyplanner-core/commit/61ed8922d61dc9f0985afffef4b420d02468da7a))
* **accounting:** sync opening balances and plan bidirectional investment flow ([b409f4d](https://github.com/pablesite/moneyplanner-core/commit/b409f4d3a2bcd146170c0004f01403cc511d1a02))
* **accounting:** tolerate duplicated system equity accounts ([c6911a4](https://github.com/pablesite/moneyplanner-core/commit/c6911a4fee9c1c54016fd1f78d786a02a70b5c03))
* **accounting:** type-safe page prop in QuickEntryModal and fix hasCompatibleAnnualPlanOptions ([9027021](https://github.com/pablesite/moneyplanner-core/commit/9027021ae1ecca8596b8f4c939f6c9e3bc771b08))
* **accounting:** unify debt-payment quick entry and close personal-loan review ([ada6506](https://github.com/pablesite/moneyplanner-core/commit/ada6506fdc7152613b5924aa38d567b5c93cd424))
* **accounting:** visually elevate balance feedback in adjustment and revaluation ([61c50ea](https://github.com/pablesite/moneyplanner-core/commit/61c50eaeacd41e9bf0157480b907c381eaf08dd3))
* **accounting:** wrap LedgerTransaction create/update and account destroy in atomic transactions ([071eb6e](https://github.com/pablesite/moneyplanner-core/commit/071eb6e255e4aca86138e9073216002015e8514f))
* align general net worth highlight with summary ([1dea499](https://github.com/pablesite/moneyplanner-core/commit/1dea49910fc995d5e8bfc04d8a88f07108ba2aa7))
* align net worth ownership filter with budget behavior ([3ea2fdb](https://github.com/pablesite/moneyplanner-core/commit/3ea2fdbfcee8ccfebfdbe3647475ab9dc3a72c94))
* align net worth totals and integrated timeline ([5d6f9c4](https://github.com/pablesite/moneyplanner-core/commit/5d6f9c4fea6e3840a3470dea19055980d8d66264))
* **auth:** avoid logout on transient session validation failures ([03e6598](https://github.com/pablesite/moneyplanner-core/commit/03e65980ed28cc58d43bae806009519473ab3944))
* **auth:** restore core /api/auth/me compatibility endpoint ([95fe049](https://github.com/pablesite/moneyplanner-core/commit/95fe049e10dafaddb9c4c2f138ff62e93f6f777e))
* **auth:** use core backend port in frontend fallback ([e60ed64](https://github.com/pablesite/moneyplanner-core/commit/e60ed64c6966d60b9ef034665c8d55a60268827d))
* **budget:** align ytd execution and one-off forecast behavior ([e003d24](https://github.com/pablesite/moneyplanner-core/commit/e003d241ea5c5aa6ac4c557fd543f4dacde22acb))
* **budget:** classify remunerated liquidity by interest ([9387662](https://github.com/pablesite/moneyplanner-core/commit/9387662a212069a36d78dce1053e2ff3cca5e5f0))
* **budget:** classify yield cash accounts ([7a9aac9](https://github.com/pablesite/moneyplanner-core/commit/7a9aac919642d73552fb4b7b8130a466905fc03d))
* **budget:** close v1 consistency and modal UX ([3056f7c](https://github.com/pablesite/moneyplanner-core/commit/3056f7c927b6df0c9534c39935b6a585c846b5ab))
* **budget:** evolution planned bar reacts to recurrent/one_off filter ([ad6c5a6](https://github.com/pablesite/moneyplanner-core/commit/ad6c5a68d2cda7c0b992871ea1023de255e9b285))
* **budget:** filter expense execution by entry type ([df75317](https://github.com/pablesite/moneyplanner-core/commit/df753175fb37a20d7f0893632e3be629fcfb9b1f))
* **budget:** filter expense execution by entry type ([df79711](https://github.com/pablesite/moneyplanner-core/commit/df79711bb8d1213e4b8fbda7b1f0abf5b63b3e4e))
* **budget:** fix monthly close execution override and ledger attribution ([2d3f707](https://github.com/pablesite/moneyplanner-core/commit/2d3f707e89da32b85df0f37fee8e3db869265340))
* **budget:** include interest investments in close perimeter ([3dc6be0](https://github.com/pablesite/moneyplanner-core/commit/3dc6be08722016fde1e07fa964cfcdbed8dd0781))
* **budget:** normalize uncovered expense taxonomy ([7e02eb3](https://github.com/pablesite/moneyplanner-core/commit/7e02eb3e371baaa71f9b29287920e3aa259d68dc))
* **budget:** prevent stale data race in useAccountingExecutionData ([19327d2](https://github.com/pablesite/moneyplanner-core/commit/19327d27675f368b3c391cbb4c4f84a4ab9a6e86))
* **budget:** replace curly quotes with straight quotes in liquidity section ([2630994](https://github.com/pablesite/moneyplanner-core/commit/2630994702371a83bfcf20cf0ef39efeccab7db7))
* **budget:** stabilize dashboard validation ([b78b16b](https://github.com/pablesite/moneyplanner-core/commit/b78b16b477a188838ef7dc738c7a2b87f657ad9b))
* **budget:** stabilize ordering and net investment rotation in budget execution ([fa309e4](https://github.com/pablesite/moneyplanner-core/commit/fa309e435e6ad3d9e767eda8b392d09215754d7a))
* **ci:** add DJANGO_SECRET_KEY env var and raise frontend coverage to 80% ([88277ba](https://github.com/pablesite/moneyplanner-core/commit/88277bac463710a47ad03762ddaf31d22d18e50f))
* **ci:** add ignore-unfixed to Trivy, bump axios to 1.16.1 ([45b0499](https://github.com/pablesite/moneyplanner-core/commit/45b0499b9896d89c2c73b6863a041eb9edc39e94))
* **ci:** remove invalid --error flag from semgrep ci; fix prettier ([ac060f5](https://github.com/pablesite/moneyplanner-core/commit/ac060f572b7e9beeb0a82548db20bcfd078060c4))
* clarify monthly close coverage copy ([6708e71](https://github.com/pablesite/moneyplanner-core/commit/6708e7122e513c6febf1b379283f5fdc082a6bd3))
* clarify monthly income section title ([6f5d709](https://github.com/pablesite/moneyplanner-core/commit/6f5d709edb1a8b97d9c30254759bb55a9c52c403))
* **core-backend:** resolve services_assets typing errors ([e81c6bb](https://github.com/pablesite/moneyplanner-core/commit/e81c6bbebac2e6afd75f99e8b1bca274522700eb))
* **core:** avoid circular rendering in annual data input options ([461ba1c](https://github.com/pablesite/moneyplanner-core/commit/461ba1cfae4c4d8967fd5dec8a805253af219d8e))
* **core:** guard annual data input collections ([ec7049c](https://github.com/pablesite/moneyplanner-core/commit/ec7049c7e667f7ac89cb48fcfb46f59ceaa58c55))
* **core:** guard data input patrimony collections ([59e4192](https://github.com/pablesite/moneyplanner-core/commit/59e4192ad6d22034401f64cf4cd328ab6b5b333d))
* **core:** support manual liquidity overrides ([fadaa68](https://github.com/pablesite/moneyplanner-core/commit/fadaa68fd866b9b7b6624d9ae5ff01c5700b9536))
* **core:** unwrap annual data input loading props ([afd477c](https://github.com/pablesite/moneyplanner-core/commit/afd477c371653592656bdee05282f87f9fc9506a))
* **core:** unwrap data input modal props ([a7ff233](https://github.com/pablesite/moneyplanner-core/commit/a7ff2331e297f11f83525ca2e494ab4d9009cf8d))
* **data-import:** harden portable import flow ([1e02615](https://github.com/pablesite/moneyplanner-core/commit/1e026158af31be416fca0e3067eaa931b3acb208))
* **deps:** bump axios to 1.16.1 — fix HIGH CVEs (SSRF, prototype pollution, header injection) ([4d60bd6](https://github.com/pablesite/moneyplanner-core/commit/4d60bd6bef20ced20330bdab4a6642b2d38960f9))
* **deps:** patch all frontend CVEs and upgrade pip in backend Dockerfile ([0be4bc3](https://github.com/pablesite/moneyplanner-core/commit/0be4bc352892781fa70a5349cd0f40e686e74ceb))
* **design-system:** avoid cssVar() in defineProps default — resolve in chartData computed ([254a94a](https://github.com/pablesite/moneyplanner-core/commit/254a94ae3bc13baa09221c6647e9a2988693a025))
* **dev:** make core compose cross-platform and add missing migrations ([96192ae](https://github.com/pablesite/moneyplanner-core/commit/96192ae8c7ca464c7ec867ab999d189958a5601a))
* **dev:** make frontend polling configurable ([5d39fb4](https://github.com/pablesite/moneyplanner-core/commit/5d39fb453f853b2bc99918c0024f83aa22101409))
* exclude revaluations from budget execution ([9fd35e5](https://github.com/pablesite/moneyplanner-core/commit/9fd35e51d52fb6748dbe2a7f1d04be53929d5d6d))
* **frontend:** align core frontend env ports ([6c0bfe9](https://github.com/pablesite/moneyplanner-core/commit/6c0bfe983c0781c87806e7776ae4ab9c0b67cc44))
* **frontend:** align liquidity subtotals and accounting net balance ([8e1b3f9](https://github.com/pablesite/moneyplanner-core/commit/8e1b3f9fe2c8a1ca5a04eba3eb048e3c04420087))
* **frontend:** align modal consistency ([a00ab19](https://github.com/pablesite/moneyplanner-core/commit/a00ab198f2a4ae871c9f31349e02203478fdc1b8))
* **frontend:** corregir edicion y visualizacion de movimientos en todos/cuentas ([032641a](https://github.com/pablesite/moneyplanner-core/commit/032641ada4e65dc2feaabe894fddf3ddd7518921))
* **frontend:** corregir tildes y ortografia en textos UI ([f844d9d](https://github.com/pablesite/moneyplanner-core/commit/f844d9d5d4c2b463d8504e7481b30970f87aed1f))
* **frontend:** prevent modal close on backdrop click ([f763ac1](https://github.com/pablesite/moneyplanner-core/commit/f763ac1003487ec3697781148cbba9b8b2b650f4))
* **frontend:** refresh budget rows and clarify YTD KPIs ([7d01b55](https://github.com/pablesite/moneyplanner-core/commit/7d01b559974b7ffaa0c0c82844a0d0105833a3c4))
* **frontend:** resolve net worth spec typing for accounting readiness ([362211a](https://github.com/pablesite/moneyplanner-core/commit/362211a1004aaa3e971fb8699c77614cb2d7d701))
* **frontend:** restore frontend quality checks ([5baa513](https://github.com/pablesite/moneyplanner-core/commit/5baa513fd5d12c53be362884d55b1481972638e7))
* **frontend:** sort net-worth positions alphabetically by name ([077ba74](https://github.com/pablesite/moneyplanner-core/commit/077ba74fb46ece2f42b7ed5ef15fdb7cb145681a))
* **frontend:** unwrap data input refs in intro and annual sections ([fd6b523](https://github.com/pablesite/moneyplanner-core/commit/fd6b523c139b25d038366ccd774a25ee1fc72b38))
* **guide:** restore missing guide detail styles lost in component decomposition ([e3f2878](https://github.com/pablesite/moneyplanner-core/commit/e3f2878af23cb40d33b17881eb5be9777a9ffe81))
* hide duplicate income movement totals ([5541c36](https://github.com/pablesite/moneyplanner-core/commit/5541c36b5e00f602083bfb0200b1d2a62910f299))
* **i18n:** corregir tildes en etiquetas de categorías y subcategorías en español ([4d5f6d7](https://github.com/pablesite/moneyplanner-core/commit/4d5f6d756aabb17cfaba160542d57f89095aff62))
* **i18n:** corregir tildes y acentos en textos del frontend ([c2670f7](https://github.com/pablesite/moneyplanner-core/commit/c2670f7cfc8ef29edd8795c4ac97501bcf1a19b1))
* improve budget mortgage planning and cancellation handling ([46ea8e1](https://github.com/pablesite/moneyplanner-core/commit/46ea8e129fb25eea3db1ced04d4687f141bd7f29))
* **market-data:** improve sync coverage and fix reconcile gap detection ([b6dc4c9](https://github.com/pablesite/moneyplanner-core/commit/b6dc4c91644d223669edaf189aa5ea421e8d9173))
* **monthly-close:** cache liquidity summary calculations ([6fdcc10](https://github.com/pablesite/moneyplanner-core/commit/6fdcc10f7c155abdf6eacb091169ac748ebca2cd))
* **monthly-close:** clarify ledger liquidity editing ([4229a0e](https://github.com/pablesite/moneyplanner-core/commit/4229a0edc5270eeb78dd57d44a323f58518c6126))
* **monthly-close:** clear grouped income adjustments ([be45377](https://github.com/pablesite/moneyplanner-core/commit/be453778112490d9ecc68808ef2163c942907a4b))
* **monthly-close:** compact ledger liquidity editor ([f09a868](https://github.com/pablesite/moneyplanner-core/commit/f09a86875c2a8d8692ce2fc6983680880c139cbc))
* **monthly-close:** corregir alineación bridge y referencia de liquidez ([c0e812c](https://github.com/pablesite/moneyplanner-core/commit/c0e812ca7e602d28c52e3200ee611b6a8171833b))
* **monthly-close:** improve ledger liquidity row clarity ([dde9b2c](https://github.com/pablesite/moneyplanner-core/commit/dde9b2c2f12cbc2d3b7bf702d13fb868ea2d0b1e))
* **monthly-close:** prevent duplicate liquidity checkins ([8dcb481](https://github.com/pablesite/moneyplanner-core/commit/8dcb481ded6e0a7d9f755df6e87c8e15ee998003))
* **monthly-close:** use previous liquidity balance ([a3c957c](https://github.com/pablesite/moneyplanner-core/commit/a3c957cc3e898a8287754e945a75c7c21d47fb61))
* **net-worth:** accept legacy opening descriptions for cash anchors ([0f9e506](https://github.com/pablesite/moneyplanner-core/commit/0f9e50677dd0ec1345dd43576447eea03b594191))
* **net-worth:** anchor accounting asset balances to opening transactions ([3c65b21](https://github.com/pablesite/moneyplanner-core/commit/3c65b21a06f04275b74c3975a89178b954c7014d))
* **net-worth:** cache summary position data ([d532092](https://github.com/pablesite/moneyplanner-core/commit/d5320927423be7473112f0a2cd1e6dde5398f385))
* **net-worth:** cache timeline account lookups ([96ffd0f](https://github.com/pablesite/moneyplanner-core/commit/96ffd0fb5d6aebc856143f44d11b05b05f54aad6))
* **net-worth:** cache timeline position data ([bf14841](https://github.com/pablesite/moneyplanner-core/commit/bf1484175edfc64d3df7c987eb74e83441d2edc2))
* **net-worth:** clamp liability accounting balance to 0 and fix category composition visibility ([3f737e6](https://github.com/pablesite/moneyplanner-core/commit/3f737e60de908aad25aaadfb40334cad5e9b437d))
* **net-worth:** correct asset card value for accounting-tracked cash positions ([f2c606c](https://github.com/pablesite/moneyplanner-core/commit/f2c606c7aef3008d26c4bbd1714fcc3f33b026e9))
* **net-worth:** correctly distinguish ledger_available from ledger_covered ([99c3a59](https://github.com/pablesite/moneyplanner-core/commit/99c3a59b78040c74567306a1b387b851af5027ec))
* **net-worth:** delta chart justo debajo del timeline + solidario en modal expandido ([08186ba](https://github.com/pablesite/moneyplanner-core/commit/08186ba9370af0a6e12da79e985273b1d0ccca96))
* **net-worth:** delta chart sincronizado con ventana de los sliders ([38cab33](https://github.com/pablesite/moneyplanner-core/commit/38cab33ad68539ec95f4805acea17b6a3f577668))
* **net-worth:** delta mensual visible también con categoría seleccionada ([62e7f7d](https://github.com/pablesite/moneyplanner-core/commit/62e7f7d96e295c89f715ee1a98e56c3dd824eb05))
* **net-worth:** detect legacy system opening balances for cash accounts ([bcfc4e3](https://github.com/pablesite/moneyplanner-core/commit/bcfc4e3e17e2a77ebca8ae22a99cadf5697b5378))
* **net-worth:** don't re-activate accounting account for archived assets ([83cd273](https://github.com/pablesite/moneyplanner-core/commit/83cd27317bde00885e9ad13ad31381b79355e12a))
* **net-worth:** gear sin caja + composición sin recuadros + charts en shell unificado + puntos con unidad ([51d4db3](https://github.com/pablesite/moneyplanner-core/commit/51d4db38a3f1d8216dd8ce3e4725cc609b291f08))
* **net-worth:** harden legacy opening-balance fallback detection ([51ea366](https://github.com/pablesite/moneyplanner-core/commit/51ea3660605ac024f957c84444f9b26143c50020))
* **net-worth:** include archived positions in global timeline ([62deabe](https://github.com/pablesite/moneyplanner-core/commit/62deabef0724bad314f12ed3b794ca160bf4f7f2))
* **net-worth:** include zero-value liability categories in by-category chart ([6a7c9fc](https://github.com/pablesite/moneyplanner-core/commit/6a7c9fc61dd3b2ff5a75a9c65363fa0fdf84f391))
* **net-worth:** limit accounting opening anchor to cash assets ([6c2d65c](https://github.com/pablesite/moneyplanner-core/commit/6c2d65c1070dbe4bbc4dc194be81bdf33096833d))
* **net-worth:** mostrar rango de fechas en el badge de delta mensual ([bdaf123](https://github.com/pablesite/moneyplanner-core/commit/bdaf1230051603c7fa7899850cd5f6286245baf7))
* **net-worth:** move timelineAbortController declaration out of import block ([e9cae0b](https://github.com/pablesite/moneyplanner-core/commit/e9cae0bfa597189b7425343958e34083a84e630f))
* **net-worth:** pasar datos de categoria al donut del hero + compactar topbar ([e49500f](https://github.com/pablesite/moneyplanner-core/commit/e49500fdb6a24a67366551109c6939a386a9cc81))
* **net-worth:** pass position_cache for prev-month balance in liquidity summary ([706c6e3](https://github.com/pablesite/moneyplanner-core/commit/706c6e3ed9f5fb0c59a095c711c8cf8b979cb1a9))
* **net-worth:** preserve global prev_month_same_day when category is selected ([8c10159](https://github.com/pablesite/moneyplanner-core/commit/8c10159bf9160056bb71366476192281b4146660))
* **net-worth:** reduce dashboard list queries ([b90739e](https://github.com/pablesite/moneyplanner-core/commit/b90739e0dd0e9d3a4a713df0a4fd1f746a0b42a7))
* **net-worth:** robust opening-balance anchor for accounting cash ([6977a52](https://github.com/pablesite/moneyplanner-core/commit/6977a52cb84881c685e35ebdba02ca65b6669b6d))
* **net-worth:** stable category order on ownership filter ([dc3cccb](https://github.com/pablesite/moneyplanner-core/commit/dc3cccb333c895b2e5ac2639bae15ea0068c4102))
* **net-worth:** sync auto real-estate purchase value with amount ([53ecbb2](https://github.com/pablesite/moneyplanner-core/commit/53ecbb20523f6da6669d9e0ca9fcf3311e655743))
* **net-worth:** sync selected card value with timeline ([f8b8210](https://github.com/pablesite/moneyplanner-core/commit/f8b8210d68289c53a117513b1e88531933570a24))
* **net-worth:** update opening balance on asset edit and add save UX feedback ([79dbc2e](https://github.com/pablesite/moneyplanner-core/commit/79dbc2edf6e46810d0e2e369763af80350b04aa5))
* **ownership:** sync generated asset commitments on ownership link updates ([0285c53](https://github.com/pablesite/moneyplanner-core/commit/0285c53cd16fc73494658055e8579654450c68e6))
* **portable-data:** accept legacy multicurrency transfers without quick kind ([24061f8](https://github.com/pablesite/moneyplanner-core/commit/24061f8a4b53ce11eba7f0e4aca7737f17b7f25f))
* **portable-data:** allow multicurrency investment and transfer entries on import ([7bd3005](https://github.com/pablesite/moneyplanner-core/commit/7bd30052baea5b51a7d95841d53ea5b46e0b9dee))
* **portable-data:** auto-balance single-entry legacy transactions on import ([56925e7](https://github.com/pablesite/moneyplanner-core/commit/56925e745d116a3283855d8f621f2e0d6eb2a0bb))
* **portable-data:** defer accounting linkage until mapped accounts exist ([4daac71](https://github.com/pablesite/moneyplanner-core/commit/4daac714c22191a539980d8256b21419c1ff4d18))
* **portable-data:** include net worth detail blocks in legacy data-input export ([9361721](https://github.com/pablesite/moneyplanner-core/commit/9361721509f12e06e9f7c496898c4388386a52df))
* **portable-data:** include net worth events and advanced asset fields in bundle ([17bf333](https://github.com/pablesite/moneyplanner-core/commit/17bf3332e12fa64c3906aacb7696811a75c32704))
* **portable-import:** include liquidity checkins in transfer ([86d0ff3](https://github.com/pablesite/moneyplanner-core/commit/86d0ff3e5f9782d5ef43e5865ed29e4175edc724))
* **portable-import:** normalize legacy entry payloads ([b203dc8](https://github.com/pablesite/moneyplanner-core/commit/b203dc806920703494af081b6cafacfdc9ebe1ec))
* **portable-import:** remap opening-balance note ids for accounting liabilities ([b95bdf0](https://github.com/pablesite/moneyplanner-core/commit/b95bdf09e1e195cbddb12d9230497621e12526af))
* remove duplicate income group totals ([303436a](https://github.com/pablesite/moneyplanner-core/commit/303436ad874967444ab4e58b8d02ccc0cff08df7))
* remove redundant income list header ([dc47cf7](https://github.com/pablesite/moneyplanner-core/commit/dc47cf7a551073a1f8d51da7a6517e36f5cc3f7a))
* remove saas references from core ([0652b65](https://github.com/pablesite/moneyplanner-core/commit/0652b65f2422a9844855c5c01a7518111af63c86))
* remove SaaS references from Core ([5295d2b](https://github.com/pablesite/moneyplanner-core/commit/5295d2b8937acc837561a6fa33990aecedf8ab1e))
* **security:** restrict FxRate and InflationIndex writes to admin only ([17fb12c](https://github.com/pablesite/moneyplanner-core/commit/17fb12ce808ba9d14dce561fc5a36d8911ee97f5))
* **services:** add logging to silent except Exception fallbacks ([7624534](https://github.com/pablesite/moneyplanner-core/commit/76245345d2f799af4b1643db874c1ed0193bf993))
* **shell:** landing a /patrimonio; guide phase cards en grid equiespaciado 4col ([8b41485](https://github.com/pablesite/moneyplanner-core/commit/8b4148597e1119e5f3cd93a18f6af00b469e2001))
* simplify monthly income close labels ([d769ec5](https://github.com/pablesite/moneyplanner-core/commit/d769ec54c99563eaa3c450f009522139754795e9))
* **test:** add optional chain to avoid TS2532 on array access in spec ([6473d1b](https://github.com/pablesite/moneyplanner-core/commit/6473d1b1cba1b46a9d88f5744b0f4320a7961bba))
* **test:** replace \$nextTick with flushPromises in accounting composables spec ([a1481bc](https://github.com/pablesite/moneyplanner-core/commit/a1481bc907c5bc0e75063c7db734bf860db77144))
* **tests:** correct type errors in portableBundle and budgetDashboardUtils specs ([153ed0b](https://github.com/pablesite/moneyplanner-core/commit/153ed0bb7fb6de190f30142b35b3a4e7fc626472))
* **tests:** corregir tildes, formatos de mock y conteos de botones en tests de net-worth ([effa1e5](https://github.com/pablesite/moneyplanner-core/commit/effa1e5ab276a3b98cf44d316a43e8fbbce82a72))
* **tests:** fix accent mismatches and reactive store in NetWorthView ([1f1ebbf](https://github.com/pablesite/moneyplanner-core/commit/1f1ebbf14e1cea66a6e15ed5a38c8c4de4c6e903))
* **tests:** fix backend test failures in core module ([5d244f8](https://github.com/pablesite/moneyplanner-core/commit/5d244f8d1a35ac2ce333a6b0f623ec90ea50759e))
* **tests:** fix pre-existing frontend test failures ([786985e](https://github.com/pablesite/moneyplanner-core/commit/786985ea4e146025461225d5af283b2f97327d67))
* tighten monthly close descriptions ([1d2e057](https://github.com/pablesite/moneyplanner-core/commit/1d2e05791271b4dbd88de52218b19090ed3930e8))
* **transfer:** hide destination amount field for same-currency transfers ([10752c7](https://github.com/pablesite/moneyplanner-core/commit/10752c778fd734b0c08f2fb11d05d77f81585c88))
* **transfer:** skip destination_amount in payload for same-currency transfers ([5ed9553](https://github.com/pablesite/moneyplanner-core/commit/5ed955363bc1bd5e4df5b8acb362928b87ce1e32))


### Performance Improvements

* **accounting:** use compact API in transaction list fetches ([b47af78](https://github.com/pablesite/moneyplanner-core/commit/b47af780ef7888a70d6e7f3707976831418ec97a))
* **net-worth:** optimize timeline endpoint and progressive frontend loading ([fd014b6](https://github.com/pablesite/moneyplanner-core/commit/fd014b6730414c1331f189777ee8c1d9dcb46808))
* **net-worth:** reduce API calls from 6 to 1 per asset/liability mutation ([962d876](https://github.com/pablesite/moneyplanner-core/commit/962d8764ead63382b1d9b4ed4416376c1de94762))
* **stores:** reduce unnecessary API calls after mutations ([d830166](https://github.com/pablesite/moneyplanner-core/commit/d83016668b22ad008927aeb8e2c979ad3b8a869c))

## Changelog

All notable changes to MoneyPlanner Core are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> This file is updated automatically by [release-please](https://github.com/googleapis/release-please) on each release.
