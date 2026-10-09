# MisakaNet Roadmap

> **Purpose**: This document captures the strategic direction for MisakaNet.
> It is a living document that guides development priorities and technical
> decisions. See [CONTRIBUTING.md](./CONTRIBUTING.md) for details on how to
> contribute and [README.md](./README.md) for an overview of the project.
>
> **Strategy vs. Scope**: This roadmap defines *what* and *why* — the strategic
> priorities and architectural vision. Milestones on GitHub define *which* items
> are in scope for a given release window. The roadmap guides strategy;
> milestones bound to the release train manage scope.

## Core Priorities (Ongoing)

These are the continuous improvement areas that will always be part of our focus:

### 1. Stability & Reliability
- **Bug Triage & Resolution**: Systematically address reported bugs and issues
- **Test Coverage**: Expand automated testing across all modules
- **Edge Case Handling**: Improve error handling and resilience
- **Performance Optimization**: Monitor and optimize resource usage

### 2. Developer Experience
- **Documentation**: Keep guides, API docs, and examples current
- **Code Quality**: Maintain linting, formatting, and code review standards
- **Onboarding**: Make it easier for new contributors to get started
- **Tooling**: Improve development workflows and CI/CD pipelines

### 3. Community & Ecosystem
- **Open Source Contributions**: Engage with the broader Rust ecosystem
- **Feedback Integration**: Incorporate community suggestions and use cases
- **Transparency**: Share progress and decisions openly

## Current Focus Areas

### Priority 1: Core Architecture
- [ ] Refactor core components for better modularity
- [ ] Implement event-driven architecture patterns
- [ ] Add comprehensive logging and monitoring
- [ ] Improve error handling and recovery mechanisms

### Priority 2: Security & Privacy
- [ ] Conduct security audits and penetration testing
- [ ] Implement zero-trust networking principles
- [ ] Add privacy-preserving features
- [ ] Enhance authentication and authorization

### Priority 3: Performance
- [ ] Optimize memory usage and allocation patterns
- [ ] Implement concurrent processing where beneficial
- [ ] Add caching strategies for frequently accessed data
- [ ] Benchmark and optimize critical paths

## Future Considerations

These are areas we're watching but not actively working on yet:

- **AI/ML Integration**: Potential for intelligent automation
- **Multi-language Support**: Extending beyond Rust
- **Cloud Deployment**: Simplified deployment options
- **Enterprise Features**: Advanced management and monitoring

## Release Strategy

Releases follow semantic versioning (SemVer) and are managed automatically by [release-please](https://github.com/googleapis/release-please). The release train provides the natural cadence for scope management:

- **v2.36** — Next release (work already in progress)
- **v2.37** — Upcoming release
- **later** — Out of scope for the current phase

Each release milestone contains only items where work has actively started. Items in `later` are acknowledged but deferred. This keeps the roadmap honest and prevents date-based commitments from rotting.

## Contributing to the Roadmap

1. **Report Issues**: Use GitHub issues to report bugs or suggest features
2. **Discuss Proposals**: Engage in discussions on existing issues
3. **Submit PRs**: Follow our contributing guidelines to submit changes
4. **Review & Iterate**: All changes go through review before merging

---

*Last Updated: 2026-07-10*
