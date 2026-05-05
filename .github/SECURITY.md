# Security

## Supported versions

Security fixes land on the default branch (`main`) at the latest commit. Tagged
releases, when they exist, are supported at the tag; older tags are
best effort.

## Reporting a vulnerability

**Do not file a public GitHub issue** for an undisclosed security problem in
this repository (harness, scripts, packaging, or CI). That can put other
users at risk before a fix exists.

**Contact:** [aditya2210.a1@gmail.com](mailto:aditya2210.a1@gmail.com)

Include, when you can:

- Short description and why it matters
- Steps to reproduce, with commit SHA or tag
- Affected files or commands
- Optional patch or mitigation idea

We aim to send an initial response within **5 business days**.

For **vendor product** issues (a specific closed system or model API, not this
repo’s code), also use the vendor’s own security contact. Our 90 day
responsible disclosure practice for novel, high severity, product specific
findings is written in [ETHICS.md](../ETHICS.md).

## Scope (what we treat as a security report for *this* repo)

**In scope**

- Flaws in this repo that can cause unexpected code execution, credential
  theft, or data loss when following the documented install and run path
- CI or release pipeline issues that could ship malware or leak secrets
- Accidental committed secrets in *this* repository (we will rotate and remove)

**Out of scope**

- Generic claim that “LLMs are injectable” or benchmark ASR numbers (that is
  the research subject, not a secret bug in the harness)
- Third party API pricing, rate limits, or ToS
- Attacks on *your* production deployment unless the root cause is a bug in
  *this* repo’s code

Dual use and what we publish are covered in [ETHICS.md](../ETHICS.md) and
[THREAT_MODEL.md](../THREAT_MODEL.md).

## License

The project is under the **MIT License**; see [LICENSE](../LICENSE) in the
repository root. The MIT License applies to the *code*; it does not override
laws, vendor terms, or your own duty of care when running evals against
external services.
