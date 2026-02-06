# hass-safetec

[![GitHub Release](https://img.shields.io/github/release/sangvikh/hass-safetec.svg?style=flat)](https://github.com/sangvikh/hass-safetec/releases)
[![hassfest](https://img.shields.io/github/actions/workflow/status/sangvikh/hass-safetec/hassfest.yaml?branch=master&label=hassfest)](https://github.com/sangvikh/hass-safetec/actions/workflows/hassfest.yaml)
[![HACS](https://img.shields.io/github/actions/workflow/status/sangvikh/hass-safetec/validate.yaml?branch=master&label=HACS)](https://github.com/sangvikh/hass-safetec/actions/workflows/validate.yaml)

HACS integration for Safetec and SYR water meters

## Features

* Adds sensors for water consumption, water pressure, water temperature +++
* Monitors NeoSoft-specific values such as salt level and regeneration state
* Opening/Closing of water valve

## Supported devices

* Safetec
* SYR Trio
* SYR SafeTech+
* SYR NeoSoft

## Installation

**Recommended:** Install via HACS

### HACS

1. Install [HACS](https://hacs.xyz/docs/configuration/basic/) if needed.
2. In HACS, search for and install the "Safetec" integration.
3. Restart Home Assistant.
4. Add the integration via Home Assistant's Integrations page and follow the configuration steps.

### Manual installation

1. Download or clone this repository.
2. Copy `custom_components/hass_safetec` to your Home Assistant `custom_components` directory.
3. Restart Home Assistant.
4. Add the integration via Home Assistant's Integrations page and follow the configuration steps.
