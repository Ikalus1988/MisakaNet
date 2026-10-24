# Changelog

## [0.7.0](https://github.com/Ikalus1988/MisakaNet/compare/misakanet-setup-v0.6.0...misakanet-setup-v0.7.0) (2026-10-24)


### Features

* **setup:** add MiniMax Code (mcode) as a plugin target ([#3798](https://github.com/Ikalus1988/MisakaNet/issues/3798)) ([ad0bf8e](https://github.com/Ikalus1988/MisakaNet/commit/ad0bf8e3aabc2198fb38e69c3b92adc24343d28a)), closes [#3777](https://github.com/Ikalus1988/MisakaNet/issues/3777)


### Bug Fixes

* **setup:** a second run is idempotent, and --verify stops lying ([#3794](https://github.com/Ikalus1988/MisakaNet/issues/3794)) ([5af7c87](https://github.com/Ikalus1988/MisakaNet/commit/5af7c87d55651667ab659d52506d92d37f6abeba)), closes [#3772](https://github.com/Ikalus1988/MisakaNet/issues/3772) [#3775](https://github.com/Ikalus1988/MisakaNet/issues/3775) [#3776](https://github.com/Ikalus1988/MisakaNet/issues/3776) [#3778](https://github.com/Ikalus1988/MisakaNet/issues/3778)
* **setup:** the gate let a 100%-unusable machine through, and the uninstall did not undo ([#3768](https://github.com/Ikalus1988/MisakaNet/issues/3768)) ([f0a62ad](https://github.com/Ikalus1988/MisakaNet/commit/f0a62ad30cec61e6864442b7dacb63c50b212f52))


### Documentation

* **setup:** dsh's rules block is manual — say how to upgrade and remove it ([#3796](https://github.com/Ikalus1988/MisakaNet/issues/3796)) ([e73b60e](https://github.com/Ikalus1988/MisakaNet/commit/e73b60e5333dc35880ce23cd6c17dd7bf3a0f2bb)), closes [#3773](https://github.com/Ikalus1988/MisakaNet/issues/3773)

## 0.6.0 (2026-10-22)


### Features

* **setup:** the install says what it is about to write, before it writes it ([#3690](https://github.com/Ikalus1988/MisakaNet/issues/3690)) ([#3709](https://github.com/Ikalus1988/MisakaNet/issues/3709)) ([5647207](https://github.com/Ikalus1988/MisakaNet/commit/5647207dba3d224eb5ea431369049ec69cb8d68b))


### Bug Fixes

* a degraded read must not be reported as an empty corpus ([#3512](https://github.com/Ikalus1988/MisakaNet/issues/3512)) ([898a63b](https://github.com/Ikalus1988/MisakaNet/commit/898a63b3f833bdbe3b6c1670bc5ceff4439fe441))
* **e2e:** read the documented tool list from AGENTS.md instead of copying it ([#3404](https://github.com/Ikalus1988/MisakaNet/issues/3404)) ([7878a9e](https://github.com/Ikalus1988/MisakaNet/commit/7878a9ea77286a0c77d965838cb3eeb5cca73bdc))
* **setup:** --verify answers two questions, and stops calling a file it cannot write "missing" ([#3743](https://github.com/Ikalus1988/MisakaNet/issues/3743)) ([e7bda00](https://github.com/Ikalus1988/MisakaNet/commit/e7bda00f9351b571ee08553d686bbb8a34829698))
* **setup:** the npm copy of the rule text says redaction is done by code ([#3692](https://github.com/Ikalus1988/MisakaNet/issues/3692)) ([#3708](https://github.com/Ikalus1988/MisakaNet/issues/3708)) ([389c004](https://github.com/Ikalus1988/MisakaNet/commit/389c004ed612009985521cc7dd371eae00fe703d))
* **setup:** the npm description says what it writes, what leaves this machine, and the one opt-in exception ([#3689](https://github.com/Ikalus1988/MisakaNet/issues/3689)) ([#3710](https://github.com/Ikalus1988/MisakaNet/issues/3710)) ([ea2128a](https://github.com/Ikalus1988/MisakaNet/commit/ea2128a7a5ed1e7b890394c2aaf76a737af2b500))
* **setup:** the release moves the version literal, not just the manifest ([#3691](https://github.com/Ikalus1988/MisakaNet/issues/3691)) ([#3738](https://github.com/Ikalus1988/MisakaNet/issues/3738)) ([ba0c813](https://github.com/Ikalus1988/MisakaNet/commit/ba0c813692f758e8ffc370a623be9238df260b6a))


### Documentation

* **dsh:** what the plugin actually gives, and the one step it cannot do for you ([#3398](https://github.com/Ikalus1988/MisakaNet/issues/3398)) ([c8c53aa](https://github.com/Ikalus1988/MisakaNet/commit/c8c53aa063a0d12225d3b008db748dc18e9ab56b))
