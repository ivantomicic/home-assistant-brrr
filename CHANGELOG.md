# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Multi-target delivery from one visual automation action, with concurrent sends and backward compatibility for existing single-target actions.

## [0.1.0] - 2026-08-11

### Added

- UI configuration for shared and device-specific Brrr webhook targets.
- Native visual `brrr.send_notification` automation action.
- Title, subtitle, message, thread, sound, interruption, Focus, expiration, URL, icon, and image fields.
- Opt-in Media Library image export with HTTPS validation, size limits, opaque filenames, and expiry cleanup.
- Automatic hourly media cleanup, randomized public filenames, and a manual cleanup action.
- A per-target test notification button.
- Translated action fields, friendly selector labels, and native action/section icons.
- Bounded retries and specific errors for rate limits, server failures, timeouts, and connection failures.
- Redacted diagnostics and translated configuration forms.
