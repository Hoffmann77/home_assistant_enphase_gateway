[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)


**This is a custom HACS integration for Enphase Gateways with firmware version 7.X.**

Please be aware that this custom integration **does not** overwrite the "enphase_envoy" core integration (see: [Limitations](#limitations)).

# Installation
#### Prerequisites:
- Please ensure that the "enphase_envoy" core integration is disabled.
- Ensure that custom integrations overwriting the core integration are disabled.   
- Running two or more integrations accessing your Enphase gateway will result in unexpected behaviour and errors.

#### Installation:
1. Install [HACS](https://hacs.xyz/) if you haven't already
2. Add this repository as a [custom integration repository](https://hacs.xyz/docs/faq/custom_repositories) in HACS
4. Restart home assistant
5. Add the integration through the home assistant configuration flow


# Supported Gateways

  - Envoy-S Metered (with CT's enabled or disabled)
  - Envoy-S Standard
  - Envoy-C


# Usage

  - Username / Password / Use Enlighten [#73](https://github.com/briancmpbll/home_assistant_custom_envoy/issues/73)\
      When configuring the Envoy with firmware 7 or higher specify your Enphase Enlighten username and password, the envoy serial number and check the 'Use Enlighten' box at the bottom. This will allow the integration to collect a token from the enphase website and use it to access the Envoy locally. It does this at first configuration, at each HA startup or at reload of the integration. The Enphase web-site is known to be slow or satured at times. When an *Unknown Error* is reported during configuration try again until success. [#81](https://github.com/briancmpbll/home_assistant_custom_envoy/issues/81) \
      \
      Upon changing your password on the Enphase web site you will have to update the password information in HA. To update it, delete the envoy integration from the Settings / Integrations window. Restart HA and then in Integrations window configure it again. All data is kept and will show again once it's configured.

  - [#75 Invalid Port and IPV6 autodetect](https://github.com/briancmpbll/home_assistant_custom_envoy/issues/75) \
      HA performs auto discovery for Envoy on the network. When it identifies an Envoy it will use the Envoy serial number 
      to identify a configured Envoy and then update the IP addres of the Envoy. If the auto discovery returns an IPV6 address it will update the Envoy with reported IPv6 address even if it was configured with an IPv4 address before. This causes the integration to fail as IPv6 addresses cause issues in the communication to the Envoy. \
      \
      To solve this and prevent this from happening again, remove the Envoy in the Integrations panel, restart HA and configure the Envoy again with the IPv4 address. This may require to change the IP address to the IPv4 on the auto detected Envoy or add manually an Envoy Integration. \
      \
      Then open the *System options* on the Envoy Integrations menu (3 vertical dots). In the System options panel de-activate the *Enable Newly Added Entities* option to turn it off. This will cause the Envoy Intgeration to ignore autodetect updates and keep the configured IP address. Make sure the Envoy is using a fixed IP address to avoid loosing connection if it changes its IP.


# Limitations
* #### Multiple integrations
  - This custom integration uses a different domain than the "enphase_envoy" core integration.   
  - Thereby it **does not** overwrite the "enphase_envoy" core integration.   
  - Running two or more integrations accessing your Enphase gateway will result in unexpected behaviour and errors.


# Tribute

This integration is based on work done by the following:

*  https://github.com/jesserizzo/envoy_reader by @jesserizzo and contributors
*  https://github.com/DanBeard/enphase_envoy by @DanBeard and contributors
*  https://github.com/briancmpbll/home_assistant_custom_envoy by @briancmpbll and contributors
