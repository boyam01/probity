//! SemVer 2.0.0 precedence comparison (semver.org section 11).
//!
//! `compare(a, b)` returns -1 if a < b, 0 if a == b, 1 if a > b, by SemVer precedence.
//!
//! Precedence rules (authoritative — the tests encode these and they are correct):
//!   1. Compare major, minor, patch NUMERICALLY, not as strings: 1.10.0 > 1.2.0.
//!   2. A version WITH a pre-release has LOWER precedence than the same core without one:
//!      1.0.0-alpha < 1.0.0.
//!   3. Pre-release identifiers are compared left to right until a difference is found:
//!        - numeric identifiers compare numerically;
//!        - alphanumeric identifiers compare in ASCII sort order;
//!        - a numeric identifier always has LOWER precedence than an alphanumeric one;
//!        - when all preceding identifiers are equal, a LARGER set of fields ranks higher:
//!          1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta.
//!   4. Build metadata (everything after '+') is IGNORED for precedence: 1.0.0+a == 1.0.0+b.

pub fn compare(a: &str, b: &str) -> i32 {
    // BUG: whole-string comparison. Ignores numeric ordering (rule 1) and the pre-release /
    // build-metadata rules (2, 3, 4) entirely.
    if a == b {
        0
    } else if a < b {
        -1
    } else {
        1
    }
}
